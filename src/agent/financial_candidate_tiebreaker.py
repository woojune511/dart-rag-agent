"""Local semantic tie-breaking for already-shortlisted candidate facts.

The cross-encoder is deliberately lazy and optional.  Candidate applicability,
factor tiers, visibility, and physical-row bundles remain owned by deterministic
runtime code; this module only scores pairs supplied from one strongest tied
tier.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable, Mapping, Protocol, Sequence, Tuple


logger = logging.getLogger(__name__)


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _string_list(values: Any) -> list[str]:
    if isinstance(values, (str, bytes)):
        values = [values]
    if not isinstance(values, Sequence):
        return []
    return list(
        dict.fromkeys(
            text
            for value in values
            if (text := _normalized_text(value))
        )
    )


def _projection_text(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _labeled_text(items: Sequence[tuple[str, Any]]) -> str:
    parts: list[str] = []
    for label, raw_value in items:
        if isinstance(raw_value, Sequence) and not isinstance(
            raw_value,
            (str, bytes),
        ):
            value = ", ".join(_string_list(raw_value))
        else:
            value = _normalized_text(raw_value)
        if value:
            parts.append(f"{label}: {value}")
    return " | ".join(parts)


def _candidate_period_surface(candidate: Mapping[str, Any]) -> str:
    period = _normalized_text(candidate.get("period"))
    value_year = _normalized_text(candidate.get("value_year"))
    period_source = _normalized_text(candidate.get("period_source"))
    if value_year and period_source == "source_surface_unresolved":
        return value_year
    return period or value_year or _normalized_text(
        candidate.get("source_period_surface")
    )


@dataclass(frozen=True, slots=True)
class SemanticTieBreakPairV1:
    """One owner/candidate pair that is eligible for semantic tie-breaking."""

    cohort_id: str
    owner_id: str
    candidate_id: str
    target_text: str
    evidence_text: str
    pair_fingerprint: str

    @classmethod
    def create(
        cls,
        *,
        cohort_id: str,
        owner_id: str,
        candidate_id: str,
        query: str,
        owner: Mapping[str, Any],
        parent_owner: Mapping[str, Any] | None,
        resolved_target: Mapping[str, Any],
        candidate: Mapping[str, Any],
        candidate_text: str,
        query_text_limit: int = 320,
        candidate_text_limit: int = 240,
    ) -> "SemanticTieBreakPairV1":
        parent = dict(parent_owner or {})
        row = dict(candidate or {})
        owner_label = _normalized_text(owner.get("label"))
        parent_label = _normalized_text(parent.get("label"))
        if parent_label == owner_label:
            parent_label = ""
        scope = {
            key: _normalized_text(value)
            for key, value in {
                **dict(parent.get("scope") or {}),
                **dict(owner.get("scope") or {}),
            }.items()
            if _normalized_text(value)
        }
        target_text = _labeled_text(
            [
                ("task", owner_label),
                ("parent task", parent_label),
                ("subject", resolved_target.get("local_subjects")),
                ("metric", resolved_target.get("metric_surfaces")),
                ("concept", resolved_target.get("concept_keys")),
                ("unit", resolved_target.get("expected_unit_family")),
                (
                    "scope",
                    [f"{key}={value}" for key, value in scope.items()],
                ),
                (
                    "question",
                    _normalized_text(query)[: max(0, int(query_text_limit))],
                ),
            ]
        )
        evidence_text = _labeled_text(
            [
                (
                    "evidence",
                    _normalized_text(candidate_text)[
                        : max(0, int(candidate_text_limit))
                    ],
                ),
                (
                    "period",
                    _candidate_period_surface(row),
                ),
                ("period source", row.get("period_source")),
                ("scope", row.get("consolidation_scope")),
                ("segment", row.get("segment")),
                ("basis", row.get("basis")),
            ]
        )
        serialized = _projection_text(
            {
                "schema": "semantic_tie_break_pair_v1",
                "target_text": target_text,
                "evidence_text": evidence_text,
            }
        )
        return cls(
            cohort_id=_normalized_text(cohort_id),
            owner_id=_normalized_text(owner_id),
            candidate_id=_normalized_text(candidate_id),
            target_text=target_text,
            evidence_text=evidence_text,
            pair_fingerprint=hashlib.sha256(
                serialized.encode("utf-8")
            ).hexdigest(),
        )


@dataclass(frozen=True, slots=True)
class SemanticTieBreakScoreV1:
    cohort_id: str
    candidate_id: str
    score: float


@dataclass(frozen=True, slots=True)
class SemanticTieBreakBatchV1:
    status: str
    scorer_id: str
    scores: Tuple[SemanticTieBreakScoreV1, ...] = ()
    requested_pair_count: int = 0
    unique_inference_pair_count: int = 0
    cache_hit_count: int = 0
    error_code: str = ""

    def scores_by_cohort(self) -> dict[str, dict[str, float]]:
        rows: dict[str, dict[str, float]] = {}
        for item in self.scores:
            rows.setdefault(item.cohort_id, {})[item.candidate_id] = item.score
        return rows

    def to_projection(self) -> dict[str, Any]:
        return {
            "schema": "semantic_tie_break_batch_v1",
            "status": self.status,
            "scorer_id": self.scorer_id,
            "requested_pair_count": self.requested_pair_count,
            "unique_inference_pair_count": self.unique_inference_pair_count,
            "cache_hit_count": self.cache_hit_count,
            "error_code": self.error_code,
            "scores": [
                {
                    "cohort_id": item.cohort_id,
                    "candidate_id": item.candidate_id,
                    "score": item.score,
                }
                for item in self.scores
            ],
        }


class SemanticCandidateTieBreaker(Protocol):
    def score_pairs(
        self,
        pairs: Sequence[SemanticTieBreakPairV1],
    ) -> SemanticTieBreakBatchV1: ...


class LocalCrossEncoderTieBreaker:
    """Lazy, process-local CrossEncoder with a bounded pair-score cache."""

    def __init__(
        self,
        *,
        model_name: str,
        revision: str = "",
        code_revision: str = "",
        max_length: int = 256,
        batch_size: int = 32,
        cache_size: int = 2048,
        device: str = "",
        local_files_only: bool = False,
        trust_remote_code: bool = False,
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.model_name = _normalized_text(model_name)
        self.revision = _normalized_text(revision)
        self.code_revision = _normalized_text(code_revision)
        self.max_length = max(32, int(max_length))
        self.batch_size = max(1, int(batch_size))
        self.cache_size = max(0, int(cache_size))
        self.device = _normalized_text(device)
        self.local_files_only = bool(local_files_only)
        self.trust_remote_code = bool(trust_remote_code)
        self._model_factory = model_factory
        self._model: Any = None
        self._resolved_device = ""
        self._load_error_code = ""
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._lock = Lock()

    @property
    def scorer_id(self) -> str:
        payload = _projection_text(
            {
                "kind": "local_cross_encoder",
                "pair_schema": "semantic_tie_break_pair_v1",
                "model_name": self.model_name,
                "revision": self.revision,
                "code_revision": self.code_revision,
                "max_length": self.max_length,
            }
        )
        return "cross_encoder_" + hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()[:16]

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        if self._load_error_code:
            return None
        try:
            factory = self._model_factory
            if factory is None:
                from sentence_transformers import CrossEncoder

                factory = CrossEncoder
            kwargs: dict[str, Any] = {
                "max_length": self.max_length,
                "trust_remote_code": self.trust_remote_code,
                "local_files_only": self.local_files_only,
            }
            if self.revision:
                kwargs["revision"] = self.revision
            resolved_device = self.device
            if not resolved_device:
                import torch

                resolved_device = "cuda" if torch.cuda.is_available() else "cpu"
            self._resolved_device = resolved_device
            kwargs["device"] = resolved_device
            model_kwargs: dict[str, Any] = {}
            if self.code_revision:
                model_kwargs["code_revision"] = self.code_revision
            if resolved_device == "cpu":
                model_kwargs["dtype"] = "float32"
            if model_kwargs:
                kwargs["model_kwargs"] = model_kwargs
            self._model = factory(self.model_name, **kwargs)
            self._repair_invalid_position_id_buffers(self._model)
        except Exception as exc:  # optional model failure keeps deterministic order
            self._load_error_code = type(exc).__name__
            logger.warning(
                "Semantic candidate tie-breaker unavailable: %s",
                self._load_error_code,
            )
        return self._model

    @staticmethod
    def _repair_invalid_position_id_buffers(cross_encoder: Any) -> None:
        """Repair buffers left uninitialized by some custom HF model loaders."""

        model = getattr(cross_encoder, "model", None)
        modules = getattr(model, "modules", None)
        if not callable(modules):
            return
        for module in modules():
            position_ids = getattr(module, "position_ids", None)
            if position_ids is None or not hasattr(position_ids, "reshape"):
                continue
            try:
                flattened = position_ids.reshape(-1)
                if not int(flattened.numel()):
                    continue
                probe_size = min(8, int(flattened.numel()))
                probe = flattened[:probe_size].detach().cpu().tolist()
                lower_bound = int(flattened.min().detach().cpu().item())
                upper_bound = int(flattened.max().detach().cpu().item())
            except (AttributeError, RuntimeError, TypeError, ValueError):
                continue
            if probe == list(range(probe_size)):
                continue
            if lower_bound >= 0 and upper_bound < int(flattened.numel()):
                continue
            import torch

            replacement = torch.arange(
                int(flattened.numel()),
                device=position_ids.device,
                dtype=position_ids.dtype,
            ).reshape(position_ids.shape)
            module.register_buffer(
                "position_ids",
                replacement,
                persistent=False,
            )

    @staticmethod
    def _score_values(raw_scores: Any) -> list[float]:
        if hasattr(raw_scores, "detach"):
            raw_scores = raw_scores.detach().cpu()
        if hasattr(raw_scores, "tolist"):
            raw_scores = raw_scores.tolist()
        values: list[float] = []
        for raw_value in raw_scores:
            value = raw_value
            while isinstance(value, (tuple, list)) and len(value) == 1:
                value = value[0]
            if isinstance(value, (tuple, list)):
                value = value[-1]
            values.append(float(value))
        if not all(math.isfinite(value) for value in values):
            raise ValueError("cross_encoder_non_finite_score")
        return values

    def score_pairs(
        self,
        pairs: Sequence[SemanticTieBreakPairV1],
    ) -> SemanticTieBreakBatchV1:
        rows = tuple(pairs)
        if not rows:
            return SemanticTieBreakBatchV1(
                status="not_needed",
                scorer_id=self.scorer_id,
            )

        with self._lock:
            scores_by_fingerprint: dict[str, float] = {}
            missing_by_fingerprint: OrderedDict[
                str, SemanticTieBreakPairV1
            ] = OrderedDict()
            cache_hit_count = 0
            for pair in rows:
                cached = self._cache.get(pair.pair_fingerprint)
                if cached is not None:
                    cache_hit_count += 1
                    scores_by_fingerprint[pair.pair_fingerprint] = cached
                    self._cache.move_to_end(pair.pair_fingerprint)
                else:
                    missing_by_fingerprint.setdefault(
                        pair.pair_fingerprint,
                        pair,
                    )

            if missing_by_fingerprint:
                model = self._load_model()
                if model is None:
                    return SemanticTieBreakBatchV1(
                        status="unavailable",
                        scorer_id=self.scorer_id,
                        requested_pair_count=len(rows),
                        unique_inference_pair_count=len(missing_by_fingerprint),
                        cache_hit_count=cache_hit_count,
                        error_code=self._load_error_code or "model_unavailable",
                    )
                inference_rows = list(missing_by_fingerprint.values())
                try:
                    raw_scores = model.predict(
                        [
                            (pair.target_text, pair.evidence_text)
                            for pair in inference_rows
                        ],
                        batch_size=self.batch_size,
                        show_progress_bar=False,
                        convert_to_numpy=True,
                    )
                    values = self._score_values(raw_scores)
                    if len(values) != len(inference_rows):
                        raise ValueError("cross_encoder_score_count_mismatch")
                except Exception as exc:
                    return SemanticTieBreakBatchV1(
                        status="unavailable",
                        scorer_id=self.scorer_id,
                        requested_pair_count=len(rows),
                        unique_inference_pair_count=len(inference_rows),
                        cache_hit_count=cache_hit_count,
                        error_code=type(exc).__name__,
                    )
                for pair, score in zip(inference_rows, values):
                    scores_by_fingerprint[pair.pair_fingerprint] = score
                    if self.cache_size:
                        self._cache[pair.pair_fingerprint] = score
                        self._cache.move_to_end(pair.pair_fingerprint)
                        while len(self._cache) > self.cache_size:
                            self._cache.popitem(last=False)

            scores = tuple(
                SemanticTieBreakScoreV1(
                    cohort_id=pair.cohort_id,
                    candidate_id=pair.candidate_id,
                    score=round(
                        scores_by_fingerprint[pair.pair_fingerprint],
                        8,
                    ),
                )
                for pair in rows
            )
            return SemanticTieBreakBatchV1(
                status="applied",
                scorer_id=self.scorer_id,
                scores=scores,
                requested_pair_count=len(rows),
                unique_inference_pair_count=len(missing_by_fingerprint),
                cache_hit_count=cache_hit_count,
            )


__all__ = [
    "LocalCrossEncoderTieBreaker",
    "SemanticCandidateTieBreaker",
    "SemanticTieBreakBatchV1",
    "SemanticTieBreakPairV1",
    "SemanticTieBreakScoreV1",
]
