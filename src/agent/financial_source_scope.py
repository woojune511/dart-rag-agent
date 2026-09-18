"""Explicit query section authority, separate from soft retrieval relevance.

Only located section metadata (or the canonical legacy source anchor) can
establish membership. Body text and attached context never grant authority.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from src.agent.financial_request_units import build_request_units, owned_request_unit_span


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


def _document_identity(metadata: Mapping[str, Any]) -> str:
    # Same explicit provenance representation as catalog ingress. Never infer
    # a filing identity from its company/year, title or local chunk number.
    for key in ("rcept_no", "document_id"):
        value = str(metadata.get(key) or "").strip()
        if value and value not in {"unknown", "?"}:
            return f"{key}:{value}"
    value = str(metadata.get("source_document_id") or "").strip()
    return value if value not in {"unknown", "?"} else ""


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _section_id(document_id: str, path: Sequence[str]) -> str:
    return "section_" + hashlib.sha256(_json_bytes([document_id, list(path)])).hexdigest()[:24]


def build_source_section_inventory(
    metadata_rows: Sequence[Mapping[str, Any]], *, max_sections: int = 256, max_bytes: int = 65536,
) -> dict[str, Any]:
    """Index observed filing-qualified paths, not body mentions or inferred titles.

    Prefixes are located ancestors of observed paths. Capacity is deterministic
    and observable; an omitted path is not proof that a section does not exist.
    """
    records: dict[str, dict[str, Any]] = {}
    unlocated = 0
    for metadata in metadata_rows:
        document_id, path = _document_identity(metadata), candidate_section_path(metadata)
        if not document_id or not path:
            unlocated += 1
            continue
        for end in range(1, len(path) + 1):
            prefix = list(path[:end])
            key = _section_id(document_id, prefix)
            records[key] = {"section_id": key, "document_id": document_id, "path": prefix}
    ordered = sorted(records.values(), key=lambda row: (row["document_id"], row["path"]))
    visible = []
    for row in ordered:
        if len(visible) >= max_sections or len(_json_bytes([*visible, row])) > max_bytes:
            break
        visible.append(row)
    return {"schema": "source_section_inventory_v1", "sections": visible,
        "fingerprint": hashlib.sha256(_json_bytes(visible)).hexdigest(),
        "observed_section_count": len(ordered), "visible_section_count": len(visible),
        "omitted_section_count": len(ordered) - len(visible), "unlocated_metadata_count": unlocated,
        "coverage": "observed_paths_only", "truncated": len(visible) != len(ordered)}


def _request_span(binding: Mapping[str, Any], query: str, owner: Mapping[str, Any]) -> list[int]:
    if "first_request_unit_id" in binding or "last_request_unit_id" in binding:
        if "request_unit_id" in binding:
            return []  # Mixed declarations never fall back to a legacy quote.
        span = owned_request_unit_span(query, owner.get("request_unit_ids") or [],
            binding.get("first_request_unit_id"), binding.get("last_request_unit_id"))
        if span and ("requested_text" not in binding or binding["requested_text"] == query[slice(*span)]):
            return span
        return []
    unit_id, text = binding.get("request_unit_id"), binding.get("requested_text")
    if not isinstance(text, str) or not text.strip() or unit_id not in (owner.get("request_unit_ids") or []):
        return []
    unit = next((unit for unit in build_request_units(query) if unit.request_unit_id == unit_id), None)
    if unit is None:
        return []
    start = unit.text.find(text)
    if start < 0 or unit.text.find(text, start + 1) >= 0:
        return []
    return [unit.start + start, unit.start + start + len(text)]


def resolve_source_section_bindings(
    obligations: Sequence[Mapping[str, Any]], *, query: str, inventory: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Copy planner references into source-qualified authority, without inference.

    Generation supplies whole request-range endpoints and selected section IDs.
    Code copies text, offsets, paths and inventory fingerprint. Legacy internal
    excerpts keep their strict checks and are never converted or repaired.
    """
    result = deepcopy(list(obligations))
    known = {row["section_id"]: row for row in inventory.get("sections") or []}
    for obligation in result:
        for owner in [obligation, *(obligation.get("evidence_requirements") or [])]:
            for binding in owner.get("source_section_bindings") or []:
                ids = binding.get("section_ids") or []
                span = _request_span(binding, query, obligation)
                if span and "first_request_unit_id" in binding:
                    binding["requested_text"] = query[slice(*span)]
                binding.update(request_span=span, resolved_sections=[deepcopy(known[key]) for key in dict.fromkeys(ids) if key in known],
                    inventory_fingerprint=str(inventory.get("fingerprint") or ""))
                if not span:
                    binding["resolution_error"] = "invalid_source_section_request"
                elif not ids:
                    binding["resolution_error"] = "unresolved_source_section_request"
                elif any(key not in known for key in ids):
                    binding["resolution_error"] = "unknown_source_section_id"
                else:
                    # An explicitly named, observed literal path cannot resolve
                    # to a foreign path merely because a model selects its ID.
                    requested = _path(binding["requested_text"])
                    exact = [row for row in known.values() if _path_matches(tuple(row["path"]), requested)]
                    if exact and any(not _path_matches(tuple(known[key]["path"]), requested) for key in ids):
                        binding["resolution_error"] = "explicit_source_section_conflict"
    return result


def _binding_valid(binding: Any) -> bool:
    if not isinstance(binding, Mapping) or binding.get("resolution_error"):
        return False
    ids, resolved = binding.get("section_ids"), binding.get("resolved_sections")
    if (not isinstance(ids, list) or not ids or any(not isinstance(key, str) for key in ids)
            or not isinstance(resolved, list) or not binding.get("inventory_fingerprint")):
        return False
    if any(not isinstance(row, Mapping) or not row.get("document_id") or not _path(row.get("path"))
           or row.get("section_id") != _section_id(row["document_id"], row["path"]) for row in resolved):
        return False
    return list(dict.fromkeys(ids)) == [row["section_id"] for row in resolved]


def _resolved_matches(candidate: Mapping[str, Any], path: tuple[str, ...], binding: Mapping[str, Any]) -> bool:
    document_id = _document_identity(candidate)
    return any(document_id == row["document_id"] and len(path) >= len(row["path"])
        and all(_surface(a) == _surface(b) for a, b in zip(path, row["path"]))
        for row in binding["resolved_sections"])


def _clauses(owner: Mapping[str, Any], parent_owner: Mapping[str, Any] | None = None) -> list[Any]:
    return [row["source_sections"] for row in (parent_owner or {}, owner)
            if "source_sections" in row and row["source_sections"] not in ([], ())]


def has_source_section_constraint(owner: Mapping[str, Any], parent_owner: Mapping[str, Any] | None = None) -> bool:
    return bool(_clauses(owner, parent_owner)) or any(
        "source_section_bindings" in row and row["source_section_bindings"] not in ([], ())
        for row in (parent_owner or {}, owner))


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
    raw_bindings = [row.get("source_section_bindings", []) for row in (parent_owner or {}, owner)]
    valid_shape = all(isinstance(rows, (list, tuple)) for rows in raw_bindings)
    bindings = [binding for rows in raw_bindings for binding in rows] if valid_shape else []
    path = candidate_section_path(candidate)
    if not valid_shape or any(not _binding_valid(binding) for binding in bindings):
        state = "invalid"
    elif not clauses and not bindings:
        state = "unrestricted"
    elif not all(_valid_clause(clause) for clause in clauses):
        state = "invalid"
    elif not path:
        state = "unknown"
    elif bindings and not _document_identity(candidate):
        state = "unknown"
    elif (all(any(_path_matches(path, _path(requested)) for requested in clause) for clause in clauses)
          and all(_resolved_matches(candidate, path, binding) for binding in bindings)):
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
            owner_id = str(owner.get("requirement_id") or obligation_id)
            raw_bindings = owner.get("source_section_bindings", [])
            bindings = raw_bindings if isinstance(raw_bindings, (list, tuple)) else [raw_bindings]
            for index, binding in enumerate(bindings):
                if (_binding_valid(binding) and (span := _request_span(binding, query, obligation))
                        and span == binding.get("request_span")
                        and query[slice(*span)] == binding.get("requested_text")):
                    continue
                errors.append({"code": str(binding.get("resolution_error") or "invalid_source_section_binding")
                    if isinstance(binding, Mapping) else "invalid_source_section_binding",
                    "obligation_id": obligation_id, "owner_id": owner_id, "candidate_id": "",
                    "location": f"source_section_bindings[{index}]", "repair_action": "repair_requirements",
                    "detail": "Use an owned contiguous request-unit range and section IDs from the observed inventory; unresolved restrictions cannot be dropped."})
            clauses = _clauses(owner)
            if not clauses:
                continue
            clause = clauses[0]
            if _valid_clause(clause) and all(_surface(part) in query_surface
                    for requested in clause for part in _path(requested)):
                continue
            errors.append({
                "code": "invalid_requested_source_section", "obligation_id": obligation_id,
                "owner_id": owner_id, "candidate_id": "",
                "location": "requirement.source_sections" if owner_id != obligation_id else "obligation.source_sections",
                "repair_action": "repair_requirements",
                "detail": "Section paths must contain non-empty title components copied from the query.",
            })
    return errors
