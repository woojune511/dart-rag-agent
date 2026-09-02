"""Immutable runtime contracts shared by compilation and execution.

These contracts intentionally depend only on the Python standard library.  They
form the authority boundary between semantic-program compilation, validation,
and deterministic execution.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, Mapping, Sequence, Tuple


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _ordered_unique(values: Sequence[Any]) -> Tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


@dataclass(frozen=True, slots=True)
class OwnerCandidateVisibility:
    """Candidate IDs that one obligation or requirement may select."""

    owner_id: str
    selectable_candidate_ids: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.owner_id:
            raise ValueError("owner_id must be non-empty")
        normalized = _ordered_unique(self.selectable_candidate_ids)
        object.__setattr__(self, "selectable_candidate_ids", normalized)

    def to_projection(self) -> Dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "selectable_candidate_ids": list(self.selectable_candidate_ids),
        }


@dataclass(frozen=True, slots=True)
class CandidateVisibilityV1:
    """The complete compile-time candidate authority for one program."""

    catalog_fingerprint: str
    cohort_fingerprint: str
    visible_candidate_ids: Tuple[str, ...]
    owners: Tuple[OwnerCandidateVisibility, ...]
    schema_version: str = "candidate_visibility_v1"

    @classmethod
    def create(
        cls,
        *,
        catalog_fingerprint: str,
        visible_candidate_ids: Sequence[Any],
        candidate_ids_by_owner: Mapping[str, Sequence[Any]],
    ) -> "CandidateVisibilityV1":
        visible_ids = _ordered_unique(visible_candidate_ids)
        visible_set = set(visible_ids)
        owners = tuple(
            OwnerCandidateVisibility(
                owner_id=str(owner_id),
                selectable_candidate_ids=_ordered_unique(candidate_ids),
            )
            for owner_id, candidate_ids in sorted(
                candidate_ids_by_owner.items(),
                key=lambda item: str(item[0]),
            )
            if str(owner_id)
        )
        hidden_owner_ids = sorted(
            {
                candidate_id
                for owner in owners
                for candidate_id in owner.selectable_candidate_ids
                if candidate_id not in visible_set
            }
        )
        if hidden_owner_ids:
            raise ValueError(
                "owner visibility contains IDs outside the visible catalog: "
                + ", ".join(hidden_owner_ids)
            )
        cohort_projection = {
            "visible_candidate_ids": list(visible_ids),
            "candidate_ids_by_owner": {
                owner.owner_id: list(owner.selectable_candidate_ids)
                for owner in owners
            },
        }
        return cls(
            catalog_fingerprint=str(catalog_fingerprint or ""),
            cohort_fingerprint=_fingerprint(cohort_projection),
            visible_candidate_ids=visible_ids,
            owners=owners,
        )

    def candidate_ids_by_owner(self) -> Dict[str, list[str]]:
        return {
            owner.owner_id: list(owner.selectable_candidate_ids)
            for owner in self.owners
        }

    def allows(self, owner_id: Any, candidate_id: Any) -> bool:
        owner_key = str(owner_id or "")
        candidate_key = str(candidate_id or "")
        return any(
            owner.owner_id == owner_key
            and candidate_key in owner.selectable_candidate_ids
            for owner in self.owners
        )

    def to_projection(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "catalog_fingerprint": self.catalog_fingerprint,
            "cohort_fingerprint": self.cohort_fingerprint,
            "visible_candidate_ids": list(self.visible_candidate_ids),
            "owners": [owner.to_projection() for owner in self.owners],
            "candidate_ids_by_owner": self.candidate_ids_by_owner(),
        }


@dataclass(frozen=True, slots=True)
class CompilationEnvelopeV1:
    """Immutable program, validation, and visibility accepted at compile time."""

    visibility: CandidateVisibilityV1
    program_json: str
    program_fingerprint: str
    validation_json: str
    validation_fingerprint: str
    schema_version: str = "compilation_envelope_v1"

    @classmethod
    def create(
        cls,
        *,
        visibility: CandidateVisibilityV1,
        program: Mapping[str, Any],
        validation: Mapping[str, Any],
    ) -> "CompilationEnvelopeV1":
        program_projection = dict(program)
        validation_projection = dict(validation)
        return cls(
            visibility=visibility,
            program_json=_canonical_json(program_projection),
            program_fingerprint=_fingerprint(program_projection),
            validation_json=_canonical_json(validation_projection),
            validation_fingerprint=_fingerprint(validation_projection),
        )

    def program_projection(self) -> Dict[str, Any]:
        return dict(json.loads(self.program_json))

    def validation_projection(self) -> Dict[str, Any]:
        return dict(json.loads(self.validation_json))

    def matches_program(self, program: Mapping[str, Any]) -> bool:
        return _fingerprint(dict(program)) == self.program_fingerprint

    def matches_validation(self, validation: Mapping[str, Any]) -> bool:
        return _fingerprint(dict(validation)) == self.validation_fingerprint

    def to_projection(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "visibility": self.visibility.to_projection(),
            "program": self.program_projection(),
            "program_fingerprint": self.program_fingerprint,
            "validation": self.validation_projection(),
            "validation_fingerprint": self.validation_fingerprint,
        }


__all__ = [
    "CandidateVisibilityV1",
    "CompilationEnvelopeV1",
    "OwnerCandidateVisibility",
]
