"""Explicit query section authority, separate from soft retrieval relevance.

Only located section metadata (or the canonical legacy source anchor) can
establish membership. Body text and attached context never grant authority.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


_ORDINAL = re.compile(r"^(?:[IVXLCDM]+|[0-9]+(?:\.[0-9]+)*|[A-Z])[.)]\s+", re.I)


def _surface(value: str) -> str:
    return " ".join(value.split()).casefold()


def _path(value: Any) -> tuple[str, ...]:
    parts = value.split(">") if isinstance(value, str) else value
    if not isinstance(parts, (list, tuple)) or not parts:
        return ()
    if any(not isinstance(part, str) or _surface(part) in {"", "?", "unknown"} for part in parts):
        return ()
    return tuple(" ".join(part.split()) for part in parts)


def candidate_section_path(candidate: Mapping[str, Any]) -> tuple[str, ...]:
    section = candidate.get("section_path") or candidate.get("section")
    if not section:
        anchor = str(candidate.get("source_anchor") or "").strip()
        if anchor.startswith("[") and anchor.endswith("]"):
            parts = anchor[1:-1].split("|")
            if len(parts) in (3, 4):
                section = parts[2].strip()  # The fourth field is a graph relation.
    return _path(section)


def _clauses(owner: Mapping[str, Any], parent_owner: Mapping[str, Any] | None = None) -> list[Any]:
    return [row["source_sections"] for row in (parent_owner or {}, owner)
            if "source_sections" in row and row["source_sections"] not in ([], ())]


def has_source_section_constraint(owner: Mapping[str, Any], parent_owner: Mapping[str, Any] | None = None) -> bool:
    return bool(_clauses(owner, parent_owner))


def _valid_clause(clause: Any) -> bool:
    return (isinstance(clause, (list, tuple)) and bool(clause)
            and all(isinstance(item, str) and bool(_path(item)) for item in clause))


def _title_matches(observed: str, requested: str) -> bool:
    observed, requested = _surface(observed), _surface(requested)
    return observed == requested or (
        not _ORDINAL.match(requested) and _ORDINAL.sub("", observed) == requested
    )


def _path_matches(observed: tuple[str, ...], requested: tuple[str, ...]) -> bool:
    return any(all(_title_matches(actual, target) for actual, target in zip(
        observed[start:start + len(requested)], requested
    )) for start in range(len(observed) - len(requested) + 1))


def source_section_applicability(
    candidate: Mapping[str, Any], owner: Mapping[str, Any],
    parent_owner: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    clauses = _clauses(owner, parent_owner)
    path = candidate_section_path(candidate)
    if not clauses:
        state = "unrestricted"
    elif not all(_valid_clause(clause) for clause in clauses):
        state = "invalid"
    elif not path:
        state = "unknown"
    elif all(any(_path_matches(path, _path(requested)) for requested in clause) for clause in clauses):
        state = "match"
    else:
        state = "conflict"
    return {"state": state, "source_section_path": list(path)}


def source_section_allowed_for_query(candidate: Mapping[str, Any], obligations: Sequence[Mapping[str, Any]]) -> bool:
    # Retrieval is shared. Any unrestricted output keeps the shared search open;
    # per-output/required-input authority is enforced again at compilation.
    return not obligations or any(source_section_applicability(candidate, owner)["state"]
                                 in {"unrestricted", "match"} for owner in obligations)


def source_section_requirement_errors(obligations: Sequence[Mapping[str, Any]], query: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    query_surface = _surface(query)
    for obligation in obligations:
        obligation_id = str(obligation.get("obligation_id") or "")
        for owner in [obligation, *(obligation.get("evidence_requirements") or [])]:
            if not isinstance(owner, Mapping):
                continue
            clauses = _clauses(owner)
            if not clauses:
                continue
            clause = clauses[0]
            if _valid_clause(clause) and all(_surface(part) in query_surface
                    for requested in clause for part in _path(requested)):
                continue
            owner_id = str(owner.get("requirement_id") or obligation_id)
            errors.append({
                "code": "invalid_requested_source_section", "obligation_id": obligation_id,
                "owner_id": owner_id, "candidate_id": "",
                "location": "requirement.source_sections" if owner_id != obligation_id else "obligation.source_sections",
                "repair_action": "repair_requirements",
                "detail": "Section paths must contain non-empty title components copied from the query.",
            })
    return errors
