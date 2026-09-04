"""Candidate-local fact roles for bounded semantic comparison.

The projection never creates a value or expands candidate visibility.  It
describes what an already-registered candidate represents and keeps semantic
surfaces grounded in that candidate's source text.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence, Tuple


CANDIDATE_FACT_ROLE_SCHEMA = "candidate_fact_role_v1"
CANDIDATE_SEMANTIC_ROLE_SCHEMA = "candidate_semantic_role_v1"
CANDIDATE_SOURCE_VALUE_ROLES = frozenset(
    {
        "unknown",
        "reported_total",
        "component",
        "period_value",
        "rate",
        "derived_display",
        "other",
    }
)
_STRUCTURED_CANDIDATE_KINDS = frozenset(
    {"structured_value", "structured_row", "table_row", "evidence_row"}
)


def _normalise(value: Any) -> str:
    return " ".join(str("" if value is None else value).split())


def _as_values(value: Any) -> Sequence[Any]:
    if isinstance(value, (str, bytes)):
        return [value]
    return value if isinstance(value, Sequence) else []


def _surfaces(values: Sequence[Any]) -> Tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = _normalise(raw_value)
        key = value.casefold()
        if not value or key in {"unknown", "none", "null"} or key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return tuple(ordered)


def _is_grounded(surface: str, source_text: str) -> bool:
    return _normalise(surface).casefold() in _normalise(source_text).casefold()


def _verified_source_span(
    candidate: Mapping[str, Any],
    source_text: str,
) -> tuple[int, int] | None:
    raw_span = candidate.get("source_span")
    if not isinstance(raw_span, Sequence) or isinstance(raw_span, (str, bytes)):
        return None
    try:
        start, end = int(raw_span[0]), int(raw_span[1])
    except (IndexError, TypeError, ValueError):
        return None
    raw_value = _normalise(candidate.get("raw_value"))
    if (
        not raw_value
        or not 0 <= start < end <= len(source_text)
        or _normalise(source_text[start:end]) != raw_value
    ):
        return None
    return start, end


def _candidate_polarity(candidate: Mapping[str, Any]) -> str:
    try:
        value = float(candidate.get("normalized_value"))
    except (TypeError, ValueError):
        value = None
    if value is not None:
        return "negative" if value < 0 else "positive" if value > 0 else "zero"
    raw_value = _normalise(candidate.get("raw_value"))
    if raw_value.startswith("(") and raw_value.endswith(")"):
        return "negative"
    return "unknown"


def _fingerprint(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class CandidateSemanticRoleV1:
    """A source-grounded role that never encodes task-relative operand use."""

    candidate_id: str
    subject_surfaces: Tuple[str, ...]
    relation_surfaces: Tuple[str, ...]
    value_role: str

    @classmethod
    def create(
        cls,
        *,
        candidate_id: str,
        source_text: str,
        subject_surfaces: Sequence[Any] = (),
        relation_surfaces: Sequence[Any] = (),
        value_role: str = "unknown",
    ) -> "CandidateSemanticRoleV1":
        normalized_candidate_id = _normalise(candidate_id)
        if not normalized_candidate_id:
            raise ValueError("candidate semantic role requires candidate_id")
        subjects = _surfaces(subject_surfaces)
        relations = _surfaces(relation_surfaces)
        ungrounded = [
            surface
            for surface in (*subjects, *relations)
            if not _is_grounded(surface, source_text)
        ]
        if ungrounded:
            raise ValueError("candidate semantic role contains ungrounded surfaces")
        normalized_value_role = _normalise(value_role) or "unknown"
        if normalized_value_role not in CANDIDATE_SOURCE_VALUE_ROLES:
            raise ValueError("candidate semantic value role must be source-local")
        return cls(
            candidate_id=normalized_candidate_id,
            subject_surfaces=subjects,
            relation_surfaces=relations,
            value_role=normalized_value_role,
        )

    @classmethod
    def from_projection(
        cls,
        projection: Mapping[str, Any],
        *,
        source_text: str,
        expected_candidate_id: str = "",
    ) -> "CandidateSemanticRoleV1":
        row = dict(projection or {})
        if row.get("schema") != CANDIDATE_SEMANTIC_ROLE_SCHEMA:
            raise ValueError("unsupported candidate semantic role schema")
        candidate_id = _normalise(row.get("candidate_id"))
        if expected_candidate_id and candidate_id != _normalise(
            expected_candidate_id
        ):
            raise ValueError("candidate semantic role id mismatch")
        return cls.create(
            candidate_id=candidate_id,
            source_text=source_text,
            subject_surfaces=_as_values(row.get("subject_surfaces")),
            relation_surfaces=_as_values(row.get("relation_surfaces")),
            value_role=str(row.get("value_role") or "unknown"),
        )

    def to_projection(self) -> dict[str, Any]:
        return {
            "schema": CANDIDATE_SEMANTIC_ROLE_SCHEMA,
            "candidate_id": self.candidate_id,
            "subject_surfaces": list(self.subject_surfaces),
            "relation_surfaces": list(self.relation_surfaces),
            "value_role": self.value_role,
        }


@dataclass(frozen=True, slots=True)
class CandidateFactRoleV1:
    """Immutable candidate-local role plus physical provenance."""

    candidate_id: str
    source_kind: str
    subject_surfaces: Tuple[str, ...]
    relation_surfaces: Tuple[str, ...]
    value_role: str
    statement_type: str
    polarity: str
    period: str
    period_role: str
    period_label_surfaces: Tuple[str, ...]
    value_year: int | None
    physical_table_id: str
    physical_row_id: str
    physical_cell_id: str
    source_span: tuple[int, int] | None
    grounding_state: str

    @classmethod
    def create(
        cls,
        candidate: Mapping[str, Any],
        *,
        source_text: str = "",
        semantic_role: CandidateSemanticRoleV1 | None = None,
    ) -> "CandidateFactRoleV1":
        row = dict(candidate or {})
        candidate_id = _normalise(row.get("candidate_id"))
        if not candidate_id:
            raise ValueError("candidate fact role requires candidate_id")
        if semantic_role is not None and semantic_role.candidate_id != candidate_id:
            raise ValueError("candidate semantic role id mismatch")
        text = str(source_text or row.get("source_text") or "")
        candidate_kind = _normalise(row.get("candidate_kind"))
        structured = bool(
            row.get("physical_table_id") or row.get("table_source_id")
        ) or candidate_kind in _STRUCTURED_CANDIDATE_KINDS
        source_kind = (
            "structured_table"
            if structured
            else "prose"
            if text or candidate_kind == "sentence_value"
            else "unknown"
        )
        structural_subjects = _surfaces(
            [
                *_as_values(row.get("local_entity_surfaces")),
                *_as_values(row.get("row_headers")),
            ]
        )
        structural_relations = (
            _surfaces(
                [
                    row.get("semantic_label"),
                    row.get("row_label"),
                    *_as_values(row.get("row_headers")),
                    *_as_values(row.get("column_headers")),
                    row.get("aggregate_label"),
                ]
            )
            if structured
            else ()
        )
        semantic_subjects = semantic_role.subject_surfaces if semantic_role else ()
        semantic_relations = semantic_role.relation_surfaces if semantic_role else ()
        projected_subjects = (
            semantic_subjects
            if semantic_role is not None and not structured
            else _surfaces([*semantic_subjects, *structural_subjects])
        )
        projected_relations = (
            semantic_relations
            if semantic_role is not None and not structured
            else _surfaces([*semantic_relations, *structural_relations])
        )
        value_role = (
            semantic_role.value_role
            if semantic_role and semantic_role.value_role != "unknown"
            else _normalise(row.get("value_role")) or "unknown"
        )
        raw_value_year = row.get("value_year")
        try:
            value_year = int(raw_value_year) if raw_value_year is not None else None
        except (TypeError, ValueError):
            value_year = None
        return cls(
            candidate_id=candidate_id,
            source_kind=source_kind,
            subject_surfaces=projected_subjects,
            relation_surfaces=projected_relations,
            value_role=value_role,
            statement_type=_normalise(row.get("statement_type")),
            polarity=_candidate_polarity(row),
            period=_normalise(row.get("period")),
            period_role=_normalise(row.get("period_role")),
            period_label_surfaces=_surfaces(
                _as_values(row.get("period_label_surfaces"))
            ),
            value_year=value_year,
            physical_table_id=_normalise(
                row.get("physical_table_id") or row.get("table_source_id")
            ),
            physical_row_id=_normalise(
                row.get("physical_row_id") or row.get("source_row_id")
            ),
            physical_cell_id=_normalise(
                row.get("physical_cell_id") or row.get("physical_value_id")
            ),
            source_span=_verified_source_span(row, text),
            grounding_state=(
                "semantic_grounded"
                if semantic_role is not None
                else "structured_grounded"
                if structured and structural_relations
                else "unresolved"
            ),
        )

    def to_projection(self) -> dict[str, Any]:
        return {
            "schema": CANDIDATE_FACT_ROLE_SCHEMA,
            "candidate_id": self.candidate_id,
            **self.to_semantic_projection(),
            "physical_table_id": self.physical_table_id,
            "physical_row_id": self.physical_row_id,
            "physical_cell_id": self.physical_cell_id,
            "source_span": list(self.source_span) if self.source_span else None,
        }

    def to_semantic_projection(self) -> dict[str, Any]:
        """Return model-relevant role data without candidate identity."""

        return {
            "source_kind": self.source_kind,
            "subject_surfaces": list(self.subject_surfaces),
            "relation_surfaces": list(self.relation_surfaces),
            "value_role": self.value_role,
            "statement_type": self.statement_type,
            "polarity": self.polarity,
            "period": self.period,
            "period_role": self.period_role,
            "period_label_surfaces": list(self.period_label_surfaces),
            "value_year": self.value_year,
            "grounding_state": self.grounding_state,
        }

    @property
    def projection_fingerprint(self) -> str:
        return _fingerprint(self.to_projection())

    @property
    def semantic_fingerprint(self) -> str:
        return _fingerprint(self.to_semantic_projection())

    def render_context(self) -> str:
        fields = [
            ("Candidate source kind", self.source_kind),
            ("Candidate subjects", " / ".join(self.subject_surfaces)),
            ("Candidate relations", " / ".join(self.relation_surfaces)),
            (
                "Candidate value role",
                self.value_role if self.value_role != "unknown" else "",
            ),
            ("Candidate statement type", self.statement_type),
            ("Candidate polarity", self.polarity),
            ("Candidate period role", self.period_role),
            (
                "Candidate period labels",
                " / ".join(self.period_label_surfaces),
            ),
            ("Candidate period", self.period),
            (
                "Candidate value year",
                str(self.value_year) if self.value_year is not None else "",
            ),
        ]
        return ". ".join(
            f"{label}: {value}" for label, value in fields if value
        )

    def render_semantic_context(self) -> str:
        """Render only a source-grounded semantic interpretation for a model."""

        if self.grounding_state != "semantic_grounded":
            return ""
        fields = [
            ("Candidate subjects", " / ".join(self.subject_surfaces)),
            ("Candidate relations", " / ".join(self.relation_surfaces)),
            (
                "Candidate value role",
                self.value_role if self.value_role != "unknown" else "",
            ),
        ]
        return ". ".join(
            f"{label}: {value}" for label, value in fields if value
        )


__all__ = [
    "CANDIDATE_FACT_ROLE_SCHEMA",
    "CANDIDATE_SEMANTIC_ROLE_SCHEMA",
    "CANDIDATE_SOURCE_VALUE_ROLES",
    "CandidateFactRoleV1",
    "CandidateSemanticRoleV1",
]
