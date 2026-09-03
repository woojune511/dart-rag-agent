"""Deterministic semantic matching between one owner and candidate facts.

The compiler receives only the candidates admitted here.  Matching is
factorized so repeated words in a large source row cannot compensate for a
subject or unit conflict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from src.agent.financial_row_surfaces import strip_financial_label_annotations
from src.agent.financial_runtime_normalization import (
    _normalise_operand_value,
    _normalise_spaces,
)
from src.agent.financial_runtime_contracts import (
    EvidenceBundleConstraintV1,
    EvidenceBundleOptionV1,
)
from src.config import get_financial_ontology


_STRUCTURED_CANDIDATE_KINDS = frozenset(
    {"structured_value", "structured_row", "table_row", "evidence_row"}
)
_VALID_UNIT_FAMILIES = frozenset({"KRW", "USD", "COUNT", "PERCENT"})


def _ordered_surfaces(values: Iterable[Any]) -> Tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_value in values or ():
        value = _normalise_spaces(str(raw_value or ""))
        key = value.casefold()
        if not value or key in {"unknown", "none", "null"} or key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return tuple(ordered)


def _compact(value: Any) -> str:
    return "".join(
        character.casefold()
        for character in _normalise_spaces(str(value or ""))
        if character.isalnum()
    )


def _identity_matches(expected: str, observed: str) -> bool:
    left = _compact(strip_financial_label_annotations(expected))
    right = _compact(strip_financial_label_annotations(observed))
    if not left or not right:
        return False
    if left == right or (
        min(len(left), len(right)) >= 4 and (left in right or right in left)
    ):
        return True
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    if (
        len(shorter) < 3
        or len(shorter) / len(longer) < 0.5
        or shorter[:2] != longer[:2]
        or shorter[-1] != longer[-1]
    ):
        return False
    iterator = iter(longer)
    return all(
        any(character == current for current in iterator)
        for character in shorter
    )


def _surface_contains(surface: str, target: str) -> bool:
    haystack = _compact(surface)
    needle = _compact(target)
    if not haystack or not needle:
        return False
    return needle == haystack or (len(needle) >= 2 and needle in haystack)


def _without_scope_surfaces(
    value: str,
    *,
    local_subjects: Sequence[str],
    scope: Mapping[str, Any],
) -> str:
    cleaned = _normalise_spaces(value)
    removable = [
        *local_subjects,
        *[
            str(scope.get(field) or "")
            for field in ("company", "period", "consolidation_scope", "segment", "basis")
        ],
    ]
    for raw_surface in sorted(
        (item for item in removable if _normalise_spaces(item)),
        key=len,
        reverse=True,
    ):
        cleaned = re.sub(
            re.escape(_normalise_spaces(raw_surface)),
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
    return _normalise_spaces(cleaned)


@dataclass(frozen=True, slots=True)
class ResolvedOwnerTargetV1:
    local_subjects: Tuple[str, ...]
    document_company: str
    concept_keys: Tuple[str, ...]
    concept_aliases: Tuple[str, ...]
    metric_surfaces: Tuple[str, ...]
    expected_unit_family: str


@dataclass(frozen=True, slots=True)
class CandidateFactViewV1:
    candidate_id: str
    kind: str
    candidate_kind: str
    identity_surfaces: Tuple[str, ...]
    subject_surfaces: Tuple[str, ...]
    cell_metric_surfaces: Tuple[str, ...]
    row_metric_surfaces: Tuple[str, ...]
    text_metric_surfaces: Tuple[str, ...]
    normalized_unit: str
    physical_table_id: str
    physical_row_id: str
    physical_cell_id: str
    source_key: str
    structured: bool


@dataclass(frozen=True, slots=True)
class CandidateMatchV1:
    candidate_id: str
    state: str
    scope_state: str
    subject_state: str
    document_subject_state: str
    owner_kind_state: str
    metric_state: str
    unit_state: str
    rank_vector: Tuple[int, int, int, int, int, int, int]
    target_concept_keys: Tuple[str, ...]
    target_local_subjects: Tuple[str, ...]


def project_candidate_match(match: CandidateMatchV1) -> Dict[str, Any]:
    """Return the explicit prompt/diagnostic projection for an immutable match."""

    return {
        "state": match.state,
        "scope_state": match.scope_state,
        "subject_state": match.subject_state,
        "document_subject_state": match.document_subject_state,
        "owner_kind_state": match.owner_kind_state,
        "metric_state": match.metric_state,
        "unit_state": match.unit_state,
        "rank_vector": list(match.rank_vector),
        "target_concept_keys": list(match.target_concept_keys),
        "target_local_subjects": list(match.target_local_subjects),
    }


def resolve_owner_target(
    owner: Mapping[str, Any],
    *,
    parent_owner: Optional[Mapping[str, Any]] = None,
) -> ResolvedOwnerTargetV1:
    """Resolve a typed target, inheriting only missing requirement dimensions."""

    ontology = get_financial_ontology()
    owner_row = dict(owner or {})
    parent_row = dict(parent_owner or {})
    target = dict(owner_row.get("semantic_target") or {})
    parent_target = dict(parent_row.get("semantic_target") or {})
    scope = {
        **dict(parent_row.get("scope") or {}),
        **dict(owner_row.get("scope") or {}),
    }

    local_subjects = _ordered_surfaces(
        target.get("local_subjects")
        or parent_target.get("local_subjects")
        or [scope.get("segment")]
    )
    raw_concept_keys = _ordered_surfaces(
        target.get("concept_keys")
        or owner_row.get("concept_hints")
    )
    concept_keys = tuple(
        key for key in raw_concept_keys if ontology.has_concept_key(key)
    )
    if not concept_keys:
        lookup_text = _normalise_spaces(
            " ".join(
                [
                    str(owner_row.get("label") or ""),
                    *[str(item) for item in (owner_row.get("retrieval_hints") or [])],
                ]
            )
        )
        concept_keys = tuple(
            str(item.get("concept") or "")
            for item in ontology.concept_specs(lookup_text)
            if str(item.get("concept") or "")
        )

    spec_by_key = {
        str(spec.get("concept") or ""): spec
        for spec in ontology.all_concept_specs()
        if str(spec.get("concept") or "")
    }
    specs = [spec_by_key[key] for key in concept_keys if key in spec_by_key]
    concept_aliases = _ordered_surfaces(
        value
        for spec in specs
        for value in (
            spec.get("name"),
            *(spec.get("aliases") or []),
            *(spec.get("keywords") or []),
        )
    )

    metric_surfaces = _ordered_surfaces(
        target.get("metric_surfaces")
        or [owner_row.get("label")]
    )
    metric_surfaces = _ordered_surfaces(
        _without_scope_surfaces(
            value,
            local_subjects=local_subjects,
            scope=scope,
        )
        for value in metric_surfaces
    )

    declared_units = {
        str(spec.get("unit_family") or "").upper()
        for spec in specs
        if str(spec.get("unit_family") or "").upper() in _VALID_UNIT_FAMILIES
    }
    _value, display_unit = _normalise_operand_value(
        "1", str(owner_row.get("display_unit") or "")
    )
    expected_unit = (
        display_unit
        if display_unit in _VALID_UNIT_FAMILIES
        else next(iter(declared_units))
        if len(declared_units) == 1
        else "UNKNOWN"
    )

    return ResolvedOwnerTargetV1(
        local_subjects=local_subjects,
        document_company=_normalise_spaces(str(scope.get("company") or "")),
        concept_keys=concept_keys,
        concept_aliases=concept_aliases,
        metric_surfaces=metric_surfaces,
        expected_unit_family=expected_unit,
    )


def project_candidate_fact(candidate: Mapping[str, Any]) -> CandidateFactViewV1:
    row = dict(candidate or {})
    candidate_kind = str(row.get("candidate_kind") or "")
    structured = bool(row.get("physical_table_id")) or candidate_kind in _STRUCTURED_CANDIDATE_KINDS
    identity_surfaces = _ordered_surfaces(
        [
            *(row.get("local_entity_surfaces") or []),
            row.get("segment"),
        ]
    )
    subject_surfaces = _ordered_surfaces(
        [
            *(row.get("local_entity_surfaces") or []),
            row.get("row_label"),
            *(row.get("row_headers") or []),
            row.get("segment"),
        ]
    )
    cell_metric_surfaces = _ordered_surfaces(
        [
            *(row.get("column_headers") or []),
            row.get("aggregate_label"),
        ]
    )
    row_metric_surfaces = _ordered_surfaces(
        [
            row.get("semantic_label"),
            row.get("row_label"),
            *(row.get("row_headers") or []),
        ]
    )
    text_metric_surfaces = () if structured else _ordered_surfaces([row.get("source_text")])
    normalized_unit = str(row.get("normalized_unit") or "UNKNOWN").upper()
    if normalized_unit not in _VALID_UNIT_FAMILIES:
        normalized_unit = "UNKNOWN"
    physical_table_id = str(
        row.get("physical_table_id") or row.get("table_source_id") or ""
    )
    physical_row_id = str(row.get("physical_row_id") or row.get("source_row_id") or "")
    source_key = str(
        physical_table_id
        or row.get("source_candidate_id")
        or row.get("evidence_id")
        or row.get("context_fingerprint")
        or row.get("candidate_id")
        or ""
    )
    return CandidateFactViewV1(
        candidate_id=str(row.get("candidate_id") or ""),
        kind=str(row.get("kind") or ""),
        candidate_kind=candidate_kind,
        identity_surfaces=identity_surfaces,
        subject_surfaces=subject_surfaces,
        cell_metric_surfaces=cell_metric_surfaces,
        row_metric_surfaces=row_metric_surfaces,
        text_metric_surfaces=text_metric_surfaces,
        normalized_unit=normalized_unit,
        physical_table_id=physical_table_id,
        physical_row_id=physical_row_id,
        physical_cell_id=str(
            row.get("physical_cell_id") or row.get("physical_value_id") or ""
        ),
        source_key=source_key,
        structured=structured,
    )


def _best_metric_state(
    fact: CandidateFactViewV1,
    target: ResolvedOwnerTargetV1,
) -> tuple[str, int]:
    def any_match(surfaces: Sequence[str], targets: Sequence[str]) -> bool:
        return any(
            _surface_contains(surface, wanted)
            for surface in surfaces
            for wanted in targets
        )

    if target.concept_aliases and any_match(
        fact.cell_metric_surfaces, target.concept_aliases
    ):
        return "concept_cell", 800
    if target.metric_surfaces and any_match(
        fact.cell_metric_surfaces, target.metric_surfaces
    ):
        return "surface_cell", 700
    if target.concept_aliases and any_match(
        fact.row_metric_surfaces, target.concept_aliases
    ):
        return "concept_row", 600
    if target.metric_surfaces and any_match(
        fact.row_metric_surfaces, target.metric_surfaces
    ):
        return "surface_row", 500
    if target.concept_aliases and any_match(
        fact.text_metric_surfaces, target.concept_aliases
    ):
        return "concept_text", 400
    if target.metric_surfaces and any_match(
        fact.text_metric_surfaces, target.metric_surfaces
    ):
        return "surface_text", 300
    text_surface = " ".join(fact.text_metric_surfaces)
    best_coverage = (0, 0, 0)
    if text_surface:
        compact_text = _compact(text_surface)
        for metric_surface in target.metric_surfaces:
            tokens = tuple(
                dict.fromkeys(
                    token
                    for token in re.findall(
                        r"[^\W_]+",
                        _normalise_spaces(metric_surface),
                        flags=re.UNICODE,
                    )
                    if len(_compact(token)) >= 2
                )
            )
            if len(tokens) < 2:
                continue
            covered = sum(_compact(token) in compact_text for token in tokens)
            if covered < 2:
                continue
            ratio = covered / len(tokens)
            score = int(round(ratio * 100))
            best_coverage = max(best_coverage, (score, covered, len(tokens)))
    if best_coverage[0]:
        score, covered, total = best_coverage
        return f"token_text:{covered}/{total}", 100 + score
    return "unknown", 0


def build_candidate_matches(
    catalog: Sequence[Mapping[str, Any]],
    *,
    owner: Mapping[str, Any],
    base_applicability_by_id: Mapping[str, Mapping[str, Any]],
    parent_owner: Optional[Mapping[str, Any]] = None,
) -> Dict[str, CandidateMatchV1]:
    """Build immutable factor matches for every catalog candidate."""

    target = resolve_owner_target(owner, parent_owner=parent_owner)
    owner_kind = str(owner.get("kind") or (parent_owner or {}).get("kind") or "")
    facts = [project_candidate_fact(candidate) for candidate in catalog]
    if not target.local_subjects:
        owner_text = _normalise_spaces(
            " ".join(
                [
                    str(owner.get("label") or ""),
                    *[str(item) for item in (owner.get("retrieval_hints") or [])],
                ]
            )
        )
        scope_company = _normalise_spaces(
            str(
                dict(owner.get("scope") or {}).get("company")
                or dict((parent_owner or {}).get("scope") or {}).get("company")
                or ""
            )
        )
        grounded_subjects = _ordered_surfaces(
            observed
            for fact in facts
            for observed in fact.identity_surfaces
            if len(_compact(observed)) >= 3
            and any(character.isalpha() for character in observed)
            and _surface_contains(owner_text, observed)
            and not any(
                _identity_matches(alias, observed)
                for alias in target.concept_aliases
            )
            and not (
                scope_company and _identity_matches(scope_company, observed)
            )
        )
        if grounded_subjects:
            target = replace(target, local_subjects=grounded_subjects)
    matching_rows_by_table: Dict[str, set[str]] = {}
    if target.local_subjects:
        for fact in facts:
            if not fact.physical_table_id or not fact.physical_row_id:
                continue
            if any(
                _identity_matches(expected, observed)
                for expected in target.local_subjects
                for observed in fact.subject_surfaces
            ):
                matching_rows_by_table.setdefault(fact.physical_table_id, set()).add(
                    fact.physical_row_id
                )

    matches: Dict[str, CandidateMatchV1] = {}
    for fact in facts:
        if not fact.candidate_id:
            continue
        base = dict(base_applicability_by_id.get(fact.candidate_id) or {})
        scope_state = str(base.get("state") or "unknown_only")
        if scope_state not in {"compatible", "unknown_only", "explicit_conflict"}:
            scope_state = "unknown_only"

        subject_surfaces = (
            fact.subject_surfaces
            if fact.structured
            else _ordered_surfaces(
                [*fact.subject_surfaces, *fact.text_metric_surfaces]
            )
        )
        if not target.local_subjects:
            subject_state, subject_rank = "unspecified", 2
        elif any(
            _identity_matches(expected, observed)
            for expected in target.local_subjects
            for observed in subject_surfaces
        ):
            subject_state, subject_rank = "match", 3
        elif (
            fact.structured
            and fact.physical_table_id
            and matching_rows_by_table.get(fact.physical_table_id)
            and fact.physical_row_id
            not in matching_rows_by_table[fact.physical_table_id]
        ):
            subject_state, subject_rank = "conflict", 0
        else:
            subject_state, subject_rank = "unknown", 1

        if target.document_company and any(
            _identity_matches(target.document_company, observed)
            for observed in fact.identity_surfaces
        ):
            document_subject_state, document_subject_rank = "local_match", 2
        else:
            document_subject_state, document_subject_rank = "unknown", 1

        if owner_kind == "narrative":
            owner_kind_state = "narrative" if fact.kind == "narrative" else "structured_fact"
            owner_kind_rank = 2 if fact.kind == "narrative" else 1
        else:
            owner_kind_state = "numeric" if fact.kind == "numeric" else "context"
            owner_kind_rank = 2 if fact.kind == "numeric" else 1

        if target.expected_unit_family == "UNKNOWN":
            unit_state, unit_rank = "unspecified", 1
        elif fact.normalized_unit == target.expected_unit_family:
            unit_state, unit_rank = "match", 2
        elif fact.normalized_unit == "UNKNOWN":
            unit_state, unit_rank = "unknown", 1
        else:
            unit_state, unit_rank = "conflict", 0

        metric_state, metric_rank = _best_metric_state(fact, target)
        metric_is_declared = bool(
            target.concept_aliases or target.metric_surfaces
        )
        explicit_conflict = (
            scope_state == "explicit_conflict"
            or subject_state == "conflict"
            or unit_state == "conflict"
        )
        if explicit_conflict:
            state = "explicit_conflict"
        elif (
            scope_state == "compatible"
            and subject_state != "unknown"
            and unit_state != "unknown"
            and (not metric_is_declared or metric_state != "unknown")
        ):
            state = "compatible"
        else:
            state = "unknown_only"
        state_rank = 2 if state == "compatible" else 1 if state == "unknown_only" else 0
        locality_rank = (
            3
            if fact.structured and fact.physical_cell_id
            else 2
            if fact.structured
            else 1
            if fact.candidate_kind == "chunk"
            else 0
        )
        matches[fact.candidate_id] = CandidateMatchV1(
            candidate_id=fact.candidate_id,
            state=state,
            scope_state=scope_state,
            subject_state=subject_state,
            document_subject_state=document_subject_state,
            owner_kind_state=owner_kind_state,
            metric_state=metric_state,
            unit_state=unit_state,
            rank_vector=(
                state_rank,
                subject_rank,
                owner_kind_rank,
                document_subject_rank,
                unit_rank,
                metric_rank,
                locality_rank,
            ),
            target_concept_keys=target.concept_keys,
            target_local_subjects=target.local_subjects,
        )
    return matches


def rank_candidate_matches(
    catalog: Sequence[Mapping[str, Any]],
    matches_by_id: Mapping[str, CandidateMatchV1],
    *,
    allowed_kinds: Sequence[str],
    limit: int,
    excluded_candidate_ids: Sequence[str] = (),
) -> list[Dict[str, Any]]:
    """Select stronger factor tiers first, diversifying sources within a tie."""

    excluded = {str(item) for item in excluded_candidate_ids if str(item)}
    allowed = {str(item) for item in allowed_kinds}
    candidate_by_id = {
        str(item.get("candidate_id") or ""): dict(item)
        for item in catalog
        if str(item.get("candidate_id") or "")
        and str(item.get("kind") or "") in allowed
    }
    eligible = [
        match
        for candidate_id, match in matches_by_id.items()
        if candidate_id in candidate_by_id
        and candidate_id not in excluded
        and match.state != "explicit_conflict"
    ]
    tier_vectors = sorted(
        {match.rank_vector for match in eligible},
        reverse=True,
    )
    selected: list[Dict[str, Any]] = []
    bounded_limit = max(0, int(limit))
    for tier_vector in tier_vectors:
        tier = sorted(
            (match for match in eligible if match.rank_vector == tier_vector),
            key=lambda item: item.candidate_id,
        )
        by_source: Dict[str, list[CandidateMatchV1]] = {}
        for match in tier:
            source_key = project_candidate_fact(candidate_by_id[match.candidate_id]).source_key
            by_source.setdefault(source_key, []).append(match)
        source_keys = sorted(by_source)
        while source_keys and len(selected) < bounded_limit:
            next_source_keys: list[str] = []
            for source_key in source_keys:
                rows = by_source[source_key]
                if not rows:
                    continue
                match = rows.pop(0)
                selected.append(candidate_by_id[match.candidate_id])
                if rows:
                    next_source_keys.append(source_key)
                if len(selected) >= bounded_limit:
                    break
            source_keys = next_source_keys
        if len(selected) >= bounded_limit:
            break
    return selected


def _bundle_scope_is_compatible(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    left_scope = dict(left.get("scope") or {})
    right_scope = dict(right.get("scope") or {})
    for field in ("company", "consolidation_scope", "basis"):
        left_value = _normalise_spaces(str(left_scope.get(field) or ""))
        right_value = _normalise_spaces(str(right_scope.get(field) or ""))
        if left_value.casefold() in {"", "unknown", "none", "null"}:
            continue
        if right_value.casefold() in {"", "unknown", "none", "null"}:
            continue
        if field == "company":
            if not _identity_matches(left_value, right_value):
                return False
        elif _compact(left_value) != _compact(right_value):
            return False
    return True


def _owners_share_local_subject(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    left_subjects = resolve_owner_target(left).local_subjects
    right_subjects = resolve_owner_target(right).local_subjects
    return bool(
        left_subjects
        and right_subjects
        and any(
            _identity_matches(left_subject, right_subject)
            for left_subject in left_subjects
            for right_subject in right_subjects
        )
    )


def _candidate_context_value(
    candidate: Mapping[str, Any],
    field: str,
) -> str:
    if field == "company":
        value = candidate.get("document_company") or candidate.get("company")
    else:
        value = candidate.get(field)
    normalized = _normalise_spaces(str(value or ""))
    return "" if normalized.casefold() in {"unknown", "none", "null"} else normalized


def _candidate_bundle_context_state(
    anchors: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, Any],
) -> str:
    missing_explicit_dimension = False
    for field in ("company", "year", "consolidation_scope", "basis"):
        expected = tuple(
            dict.fromkeys(
                value
                for anchor in anchors
                for value in [_candidate_context_value(anchor, field)]
                if value
            )
        )
        if not expected:
            continue
        observed = _candidate_context_value(candidate, field)
        if not observed:
            missing_explicit_dimension = True
            continue
        matches = (
            any(_identity_matches(value, observed) for value in expected)
            if field == "company"
            else any(_compact(value) == _compact(observed) for value in expected)
        )
        if not matches:
            return "explicit_conflict"
    return "unknown_only" if missing_explicit_dimension else "compatible"


def build_physical_evidence_bundle_constraints(
    catalog: Sequence[Mapping[str, Any]],
    obligations: Sequence[Mapping[str, Any]],
    *,
    cohorts: Sequence[Mapping[str, Any]],
    candidate_match_by_id: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> Tuple[EvidenceBundleConstraintV1, ...]:
    """Infer complete same-row bundles for related multi-output facts.

    Only explicitly compatible candidates participate.  A source-defined
    narrative may join a direct-value bundle across tables when its report,
    company, consolidation, and basis context is compatible with that row.
    """

    obligation_rows = [
        dict(item)
        for item in obligations
        if isinstance(item, Mapping)
        and str(item.get("obligation_id") or "").strip()
    ]
    obligation_by_id = {
        str(item.get("obligation_id") or "").strip(): item
        for item in obligation_rows
    }
    owner_order = {owner_id: index for index, owner_id in enumerate(obligation_by_id)}
    output_candidate_ids = {
        str(cohort.get("owner_id") or "").strip(): [
            str(candidate_id)
            for candidate_id in (cohort.get("candidate_ids") or [])
            if str(candidate_id)
        ]
        for cohort in cohorts
        if str(cohort.get("owner_type") or "") == "obligation"
        and str(cohort.get("owner_id") or "").strip()
    }
    candidate_by_id = {
        str(item.get("candidate_id") or ""): dict(item)
        for item in catalog
        if isinstance(item, Mapping) and str(item.get("candidate_id") or "")
    }
    fact_by_id = {
        candidate_id: project_candidate_fact(candidate)
        for candidate_id, candidate in candidate_by_id.items()
    }
    direct_ids = [
        owner_id
        for owner_id, obligation in obligation_by_id.items()
        if str(obligation.get("kind") or "") == "direct_value"
        and bool(resolve_owner_target(obligation).local_subjects)
    ]
    adjacency = {owner_id: set() for owner_id in direct_ids}
    for left_index, left_id in enumerate(direct_ids):
        for right_id in direct_ids[left_index + 1 :]:
            if (
                _owners_share_local_subject(
                    obligation_by_id[left_id], obligation_by_id[right_id]
                )
                and _bundle_scope_is_compatible(
                    obligation_by_id[left_id], obligation_by_id[right_id]
                )
            ):
                adjacency[left_id].add(right_id)
                adjacency[right_id].add(left_id)

    components: list[list[str]] = []
    seen: set[str] = set()
    for owner_id in direct_ids:
        if owner_id in seen:
            continue
        pending = [owner_id]
        component: set[str] = set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(adjacency[current] - component)
        seen.update(component)
        if len(component) >= 2:
            components.append(sorted(component, key=owner_order.__getitem__))

    constraints: list[EvidenceBundleConstraintV1] = []
    for component in components:
        row_candidates: Dict[tuple[str, str], Dict[str, list[str]]] = {}
        positions_by_owner = {
            owner_id: {
                candidate_id: index
                for index, candidate_id in enumerate(
                    output_candidate_ids.get(owner_id, [])
                )
            }
            for owner_id in component
        }
        for owner_id in component:
            for candidate_id in output_candidate_ids.get(owner_id, []):
                candidate = candidate_by_id.get(candidate_id)
                fact = fact_by_id.get(candidate_id)
                match = dict(
                    candidate_match_by_id.get(candidate_id, {}).get(owner_id, {})
                )
                if (
                    not candidate
                    or str(candidate.get("kind") or "") != "numeric"
                    or not fact
                    or not fact.physical_table_id
                    or not fact.physical_row_id
                    or str(match.get("state") or "") != "compatible"
                ):
                    continue
                row_candidates.setdefault(
                    (fact.physical_table_id, fact.physical_row_id), {}
                ).setdefault(owner_id, []).append(candidate_id)
        remaining_owner_ids = set(component)
        while remaining_owner_ids:
            observed_owner_sets = {
                tuple(
                    owner_id
                    for owner_id in component
                    if owner_id in remaining_owner_ids
                    and candidate_ids_by_owner.get(owner_id)
                )
                for candidate_ids_by_owner in row_candidates.values()
            }
            bundle_owner_sets = [
                owner_ids
                for owner_ids in observed_owner_sets
                if len(owner_ids) >= 2
            ]
            if not bundle_owner_sets:
                break
            bundle_owner_ids = min(
                bundle_owner_sets,
                key=lambda owner_ids: (
                    -len(owner_ids),
                    tuple(owner_order[owner_id] for owner_id in owner_ids),
                ),
            )
            complete_rows = [
                (row_key, candidate_ids_by_owner)
                for row_key, candidate_ids_by_owner in row_candidates.items()
                if all(
                    candidate_ids_by_owner.get(owner_id)
                    for owner_id in bundle_owner_ids
                )
            ]
            complete_rows.sort(
                key=lambda item: (
                    sum(
                        min(
                            positions_by_owner[owner_id].get(candidate_id, 10**6)
                            for candidate_id in item[1][owner_id]
                        )
                        for owner_id in bundle_owner_ids
                    ),
                    max(
                        min(
                            positions_by_owner[owner_id].get(candidate_id, 10**6)
                            for candidate_id in item[1][owner_id]
                        )
                        for owner_id in bundle_owner_ids
                    ),
                    item[0],
                )
            )
            options = [
                EvidenceBundleOptionV1.create(
                    physical_table_id=row_key[0],
                    physical_row_id=row_key[1],
                    candidate_ids_by_owner={
                        owner_id: candidate_ids_by_owner[owner_id]
                        for owner_id in bundle_owner_ids
                    },
                )
                for row_key, candidate_ids_by_owner in complete_rows
            ]
            constraint_owner_ids = list(bundle_owner_ids)

            narrative_ids = [
                owner_id
                for owner_id, obligation in obligation_by_id.items()
                if str(obligation.get("kind") or "") == "narrative"
                and str(obligation.get("evidence_mode") or "declared_inputs")
                == "source_defined_group"
                and bool(obligation.get("required", True))
                and all(
                    _owners_share_local_subject(
                        obligation, obligation_by_id[direct_id]
                    )
                    and _bundle_scope_is_compatible(
                        obligation, obligation_by_id[direct_id]
                    )
                    for direct_id in bundle_owner_ids
                )
            ]
            for narrative_id in narrative_ids:
                narrative_candidates = output_candidate_ids.get(narrative_id, [])
                extended_options: list[EvidenceBundleOptionV1] = []
                for option in options:
                    option_map = option.candidate_ids_by_owner()
                    anchors = [
                        candidate_by_id[candidate_id]
                        for direct_id in bundle_owner_ids
                        for candidate_id in option_map.get(direct_id, [])
                        if candidate_id in candidate_by_id
                    ]
                    compatible: list[str] = []
                    fallback: list[str] = []
                    for candidate_id in narrative_candidates:
                        candidate = candidate_by_id.get(candidate_id)
                        if not candidate:
                            continue
                        match_state = str(
                            candidate_match_by_id.get(candidate_id, {})
                            .get(narrative_id, {})
                            .get("state")
                            or ""
                        )
                        if match_state == "explicit_conflict":
                            continue
                        context_state = _candidate_bundle_context_state(
                            anchors, candidate
                        )
                        if context_state == "explicit_conflict":
                            continue
                        fallback.append(candidate_id)
                        if (
                            match_state == "compatible"
                            and context_state == "compatible"
                        ):
                            compatible.append(candidate_id)
                    allowed = compatible or fallback
                    if not allowed:
                        continue
                    extended_options.append(
                        EvidenceBundleOptionV1.create(
                            physical_table_id=option.physical_table_id,
                            physical_row_id=option.physical_row_id,
                            candidate_ids_by_owner={
                                **option_map,
                                narrative_id: allowed,
                            },
                        )
                    )
                if extended_options:
                    options = extended_options
                    constraint_owner_ids.append(narrative_id)

            constraints.append(
                EvidenceBundleConstraintV1.create(
                    owner_ids=constraint_owner_ids,
                    options=options,
                )
            )
            remaining_owner_ids.difference_update(bundle_owner_ids)
    return tuple(constraints)


def candidate_cell_local_source_text(candidate: Mapping[str, Any]) -> str:
    """Project only the physical cell and its axes for structured candidates."""

    fact = project_candidate_fact(candidate)
    if not fact.structured:
        return _normalise_spaces(str(candidate.get("source_text") or ""))
    return _normalise_spaces(
        " | ".join(
            _ordered_surfaces(
                [
                    *fact.subject_surfaces,
                    *fact.cell_metric_surfaces,
                    candidate.get("raw_value"),
                    candidate.get("raw_unit"),
                ]
            )
        )
    )
