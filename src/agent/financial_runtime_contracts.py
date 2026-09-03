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
class EvidenceBundleOptionV1:
    """One jointly selectable physical-row/context option."""

    option_id: str
    physical_table_id: str
    physical_row_id: str
    owners: Tuple[OwnerCandidateVisibility, ...]

    @classmethod
    def create(
        cls,
        *,
        physical_table_id: Any,
        physical_row_id: Any,
        candidate_ids_by_owner: Mapping[str, Sequence[Any]],
    ) -> "EvidenceBundleOptionV1":
        owners = tuple(
            OwnerCandidateVisibility(
                owner_id=str(owner_id),
                selectable_candidate_ids=_ordered_unique(candidate_ids),
            )
            for owner_id, candidate_ids in sorted(
                candidate_ids_by_owner.items(),
                key=lambda item: str(item[0]),
            )
            if str(owner_id) and _ordered_unique(candidate_ids)
        )
        projection = {
            "physical_table_id": str(physical_table_id or ""),
            "physical_row_id": str(physical_row_id or ""),
            "candidate_ids_by_owner": {
                owner.owner_id: list(owner.selectable_candidate_ids)
                for owner in owners
            },
        }
        return cls(
            option_id=f"bundle_option_{_fingerprint(projection)[:20]}",
            physical_table_id=projection["physical_table_id"],
            physical_row_id=projection["physical_row_id"],
            owners=owners,
        )

    @classmethod
    def from_projection(
        cls,
        projection: Mapping[str, Any],
    ) -> "EvidenceBundleOptionV1":
        return cls.create(
            physical_table_id=projection.get("physical_table_id"),
            physical_row_id=projection.get("physical_row_id"),
            candidate_ids_by_owner=dict(
                projection.get("candidate_ids_by_owner") or {}
            ),
        )

    def candidate_ids_by_owner(self) -> Dict[str, list[str]]:
        return {
            owner.owner_id: list(owner.selectable_candidate_ids)
            for owner in self.owners
        }

    def allows(self, owner_id: Any, candidate_ids: Sequence[Any]) -> bool:
        allowed = set(self.candidate_ids_by_owner().get(str(owner_id or ""), []))
        selected = {
            str(candidate_id)
            for candidate_id in candidate_ids
            if str(candidate_id)
        }
        return bool(selected) and selected.issubset(allowed)

    def to_projection(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "physical_table_id": self.physical_table_id,
            "physical_row_id": self.physical_row_id,
            "candidate_ids_by_owner": self.candidate_ids_by_owner(),
        }


@dataclass(frozen=True, slots=True)
class EvidenceBundleConstraintV1:
    """A set of owners that must select one compatible bundle option."""

    constraint_id: str
    owner_ids: Tuple[str, ...]
    options: Tuple[EvidenceBundleOptionV1, ...]
    constraint_kind: str = "physical_row_bundle"

    @classmethod
    def create(
        cls,
        *,
        owner_ids: Sequence[Any],
        options: Sequence[EvidenceBundleOptionV1],
    ) -> "EvidenceBundleConstraintV1":
        normalized_owner_ids = _ordered_unique(owner_ids)
        normalized_options = tuple(options)
        if len(normalized_owner_ids) < 2:
            raise ValueError("an evidence bundle requires at least two owners")
        if not normalized_options:
            raise ValueError("an evidence bundle requires at least one option")
        owner_set = set(normalized_owner_ids)
        for option in normalized_options:
            if set(option.candidate_ids_by_owner()) != owner_set:
                raise ValueError(
                    "every evidence bundle option must cover every owner"
                )
        projection = {
            "constraint_kind": "physical_row_bundle",
            "owner_ids": list(normalized_owner_ids),
            "options": [option.to_projection() for option in normalized_options],
        }
        return cls(
            constraint_id=f"bundle_{_fingerprint(projection)[:20]}",
            owner_ids=normalized_owner_ids,
            options=normalized_options,
        )

    @classmethod
    def from_projection(
        cls,
        projection: Mapping[str, Any],
    ) -> "EvidenceBundleConstraintV1":
        return cls.create(
            owner_ids=projection.get("owner_ids") or (),
            options=tuple(
                EvidenceBundleOptionV1.from_projection(option)
                for option in (projection.get("options") or ())
                if isinstance(option, Mapping)
            ),
        )

    def to_projection(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "constraint_kind": self.constraint_kind,
            "owner_ids": list(self.owner_ids),
            "options": [option.to_projection() for option in self.options],
        }


@dataclass(frozen=True, slots=True)
class CandidateVisibilityV1:
    """The complete compile-time candidate authority for one program."""

    catalog_fingerprint: str
    cohort_fingerprint: str
    visible_candidate_ids: Tuple[str, ...]
    owners: Tuple[OwnerCandidateVisibility, ...]
    evidence_bundle_constraints: Tuple[EvidenceBundleConstraintV1, ...] = ()
    schema_version: str = "candidate_visibility_v1"

    @classmethod
    def create(
        cls,
        *,
        catalog_fingerprint: str,
        visible_candidate_ids: Sequence[Any],
        candidate_ids_by_owner: Mapping[str, Sequence[Any]],
        evidence_bundle_constraints: Sequence[
            EvidenceBundleConstraintV1 | Mapping[str, Any]
        ] = (),
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
        constraints = tuple(
            constraint
            if isinstance(constraint, EvidenceBundleConstraintV1)
            else EvidenceBundleConstraintV1.from_projection(constraint)
            for constraint in evidence_bundle_constraints
        )
        owner_ids = {owner.owner_id for owner in owners}
        selectable_by_owner = {
            owner.owner_id: set(owner.selectable_candidate_ids)
            for owner in owners
        }
        for constraint in constraints:
            missing_owners = sorted(set(constraint.owner_ids) - owner_ids)
            if missing_owners:
                raise ValueError(
                    "evidence bundle contains unknown owners: "
                    + ", ".join(missing_owners)
                )
            hidden_bundle_ids = sorted(
                {
                    candidate_id
                    for option in constraint.options
                    for bundle_owner_id, candidate_ids in (
                        option.candidate_ids_by_owner().items()
                    )
                    for candidate_id in candidate_ids
                    if candidate_id
                    not in selectable_by_owner.get(bundle_owner_id, set())
                }
            )
            if hidden_bundle_ids:
                raise ValueError(
                    "evidence bundle contains IDs outside owner visibility: "
                    + ", ".join(hidden_bundle_ids)
                )
        cohort_projection = {
            "visible_candidate_ids": list(visible_ids),
            "candidate_ids_by_owner": {
                owner.owner_id: list(owner.selectable_candidate_ids)
                for owner in owners
            },
            "evidence_bundle_constraints": [
                constraint.to_projection() for constraint in constraints
            ],
        }
        return cls(
            catalog_fingerprint=str(catalog_fingerprint or ""),
            cohort_fingerprint=_fingerprint(cohort_projection),
            visible_candidate_ids=visible_ids,
            owners=owners,
            evidence_bundle_constraints=constraints,
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
            "evidence_bundle_constraints": [
                constraint.to_projection()
                for constraint in self.evidence_bundle_constraints
            ],
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
    "EvidenceBundleConstraintV1",
    "EvidenceBundleOptionV1",
    "OwnerCandidateVisibility",
]
