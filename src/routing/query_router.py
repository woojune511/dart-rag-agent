from __future__ import annotations

import json
import hashlib
import logging
import math
import os
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from src.config.retrieval_policy import (
    ROUTING_CALC_GUARDRAIL_ENABLED,
    ROUTING_CALC_GUARDRAIL_OPERATION_TERMS,
)
from src.config.query_routing_prompt import QUERY_ROUTING_PROMPT
from src.utils.provider_errors import ProviderAdmissionError

from .format_policy import ROUTER_INTENTS, default_format_preference

if TYPE_CHECKING:
    from .types import QueryRouteResult


logger = logging.getLogger(__name__)


def _query_route_result_model() -> Any:
    from .types import QueryRouteResult

    return QueryRouteResult


def _query_routing_decision_model() -> Any:
    from .types import QueryRoutingDecision

    return QueryRoutingDecision


def _chat_prompt_template_from_template(template: str) -> Any:
    from langchain_core.prompts import ChatPromptTemplate

    return ChatPromptTemplate.from_template(template)

SEMANTIC_FASTPATH_THRESHOLD = 0.76
SEMANTIC_FASTPATH_MARGIN = 0.04
SEMANTIC_CONFUSION_PAIR_MARGIN = 0.10
SEMANTIC_CONFUSION_PAIRS = {
    frozenset({"business_overview", "risk"}),
    frozenset({"business_overview", "numeric_fact"}),
    frozenset({"numeric_fact", "comparison"}),
}

_CANONICAL_EMBEDDING_CACHE: Dict[
    tuple[str, str, str, int],
    tuple[tuple[float, ...], ...],
] = {}
_CANONICAL_EMBEDDING_CACHE_LOCK = threading.Lock()


def default_canonical_queries_path() -> Path:
    override = os.environ.get("QUERY_ROUTING_CANONICAL_PATH")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[1] / "config" / "query_routing_canonical_v1.json"


def cosine_similarity(left: List[float], right: List[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_scale = max(abs(float(value)) for value in left)
    right_scale = max(abs(float(value)) for value in right)
    if left_scale == 0.0 or right_scale == 0.0:
        return 0.0
    left = [float(value) / left_scale for value in left]
    right = [float(value) / right_scale for value in right]
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
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


def _validated_embedding_batch(
    embeddings: Any, *, expected_count: int, expected_dimension: Optional[int],
) -> tuple[tuple[float, ...], ...]:
    vectors = tuple(tuple(float(value) for value in vector) for vector in embeddings)
    if len(vectors) != expected_count:
        raise ValueError("routing embedding count mismatch")
    dimension = expected_dimension or (len(vectors[0]) if vectors else 0)
    if not dimension or any(len(vector) != dimension for vector in vectors):
        raise ValueError("routing embedding dimension mismatch")
    if any(not math.isfinite(value) for vector in vectors for value in vector):
        raise ValueError("routing embedding contains non-finite values")
    if any(not any(vector) for vector in vectors):
        raise ValueError("routing embedding has zero magnitude")
    return vectors


class QueryRouter:
    def __init__(
        self,
        embeddings: Any,
        llm: Any,
        canonical_queries_path: Optional[Path] = None,
        embedding_spec: Optional[Dict[str, Any]] = None,
        enable_semantic_router: bool = True,
        enable_llm_fallback: bool = True,
    ) -> None:
        self.embeddings = embeddings
        self.llm = llm
        self.canonical_queries_path = canonical_queries_path or default_canonical_queries_path()
        self.embedding_spec = dict(embedding_spec or {})
        self.enable_semantic_router = bool(enable_semantic_router)
        self.enable_llm_fallback = bool(enable_llm_fallback)
        self._semantic_router = self._build_semantic_router()

    def _canonical_embedding_cache_key(self) -> Optional[tuple[str, str, str, int]]:
        provider = self.embedding_spec.get("provider")
        model = self.embedding_spec.get("model_name")
        dimension = self.embedding_spec.get("dimension")
        if (
            not isinstance(provider, str) or not provider.strip()
            or provider.strip().lower() == "unknown"
            or not isinstance(model, str) or not model.strip()
            or model.strip().lower() == "unknown"
            or type(dimension) is not int or dimension <= 0
        ):
            # Unknown adapters may still route with their own valid vectors,
            # but cannot grant a process-wide cache identity to another client.
            return None
        file_digest = hashlib.sha256(
            self.canonical_queries_path.read_bytes()
        ).hexdigest()
        return (file_digest, provider.strip().lower(), model.strip(), dimension)

    def _build_semantic_router(self) -> Dict[str, Any]:
        if not self.enable_semantic_router:
            logger.info("[routing] semantic router disabled by runtime config")
            return {
                "enabled": False,
                "examples": [],
                "degraded_reason": "semantic_router_disabled",
            }

        try:
            examples = load_canonical_routing_examples(self.canonical_queries_path)
        except Exception as exc:
            logger.warning("[routing] failed to load canonical routing examples: %s", exc)
            return {
                "enabled": False,
                "examples": [],
                "degraded_reason": f"canonical_examples_unavailable:{exc}",
            }

        if not examples:
            logger.warning("[routing] no canonical routing examples loaded from %s", self.canonical_queries_path)
            return {
                "enabled": False,
                "examples": [],
                "degraded_reason": "canonical_examples_empty",
            }

        queries = [entry["query"] for entry in examples]
        try:
            cache_key = self._canonical_embedding_cache_key()
            with _CANONICAL_EMBEDDING_CACHE_LOCK:
                cached_embeddings = _CANONICAL_EMBEDDING_CACHE.get(cache_key) if cache_key else None
            if cached_embeddings is None:
                generated_embeddings = self.embeddings.embed_documents(queries)
                dimension = self.embedding_spec.get("dimension")
                cached_embeddings = _validated_embedding_batch(
                    generated_embeddings, expected_count=len(queries),
                    expected_dimension=dimension if type(dimension) is int and dimension > 0 else None,
                )
                if cache_key is not None:
                    with _CANONICAL_EMBEDDING_CACHE_LOCK:
                        cached_embeddings = _CANONICAL_EMBEDDING_CACHE.setdefault(cache_key, cached_embeddings)
            embeddings = [list(embedding) for embedding in cached_embeddings]
        except ProviderAdmissionError:
            raise
        except Exception as exc:
            logger.warning("[routing] failed to embed canonical routing queries: %s", exc)
            return {
                "enabled": False,
                "examples": [],
                "degraded_reason": f"canonical_embedding_failed:{exc}",
            }

        enriched: List[Dict[str, Any]] = []
        for entry, embedding in zip(examples, embeddings):
            enriched.append({**entry, "embedding": embedding})

        logger.info("[routing] semantic router loaded %s canonical queries", len(enriched))
        return {"enabled": True, "examples": enriched, "degraded_reason": ""}

    def _blocks_numeric_fast_path(self, query: str, semantic_result: Dict[str, Any]) -> bool:
        if not (
            ROUTING_CALC_GUARDRAIL_ENABLED
            and semantic_result.get("fast_path")
            and semantic_result.get("intent") == "numeric_fact"
        ):
            return False
        return any(term in query for term in ROUTING_CALC_GUARDRAIL_OPERATION_TERMS)

    def semantic_route(self, query: str) -> Dict[str, Any]:
        router = self._semantic_router or {}
        examples = router.get("examples") or []
        degraded_reason = str(router.get("degraded_reason") or "")
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
                "degraded_reason": degraded_reason,
            }

        try:
            query_embedding = _validated_embedding_batch(
                [self.embeddings.embed_query(query)], expected_count=1,
                expected_dimension=len(examples[0]["embedding"]),
            )[0]
        except ProviderAdmissionError:
            raise
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
                "degraded_reason": f"query_embedding_failed:{exc}",
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
                "degraded_reason": degraded_reason,
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
            "degraded_reason": degraded_reason,
        }

    def route(self, query: str) -> QueryRouteResult:
        QueryRouteResult = _query_route_result_model()
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

        _numeric_fast_path_blocked = self._blocks_numeric_fast_path(query, semantic_result)
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
                degraded_reason=str(semantic_result.get("degraded_reason") or "") or None,
            )

        if not self.enable_llm_fallback:
            operation_signal = any(term in query for term in ROUTING_CALC_GUARDRAIL_OPERATION_TERMS)
            semantic_intent = str(semantic_result.get("intent") or "").strip()
            intent = semantic_intent if semantic_intent in ROUTER_INTENTS else ("comparison" if operation_signal else "qa")
            format_preference = str(
                semantic_result.get("format_preference") or default_format_preference(intent)
            )
            logger.info(
                "[routing] heuristic fallback intent=%s format=%s semantic_scores=%s",
                intent,
                format_preference,
                semantic_result.get("scores", {}),
            )
            return QueryRouteResult(
                intent=intent,  # type: ignore[arg-type]
                format_preference=format_preference,  # type: ignore[arg-type]
                routing_source="heuristic_fallback",
                routing_confidence=float(semantic_result.get("confidence") or (0.35 if operation_signal else 0.2)),
                routing_scores=dict(semantic_result.get("scores") or {}),
                second_intent=semantic_result.get("second_intent") or None,  # type: ignore[arg-type]
                margin=float(semantic_result.get("margin") or 0.0),
                required_margin=float(semantic_result.get("required_margin") or SEMANTIC_FASTPATH_MARGIN),
                degraded_reason=str(semantic_result.get("degraded_reason") or "") or None,
            )

        QueryRoutingDecision = _query_routing_decision_model()
        structured_llm = self.llm.with_structured_output(QueryRoutingDecision)
        prompt = _chat_prompt_template_from_template(QUERY_ROUTING_PROMPT)
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
            degraded_reason=str(semantic_result.get("degraded_reason") or "") or None,
        )
