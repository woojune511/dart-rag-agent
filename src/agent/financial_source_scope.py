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


def _table_heading_hints(
    metadata_rows: Sequence[Mapping[str, Any]], sections: Sequence[Mapping[str, Any]], *,
    max_hints: int, max_bytes: int,
) -> dict[str, Any]:
    """Read attached nearest ancestor titles as hints for existing parent IDs.

    Physical attachment and content identity are checked without opening a store.
    Neither these titles nor their context IDs establish section membership.
    """
    tables: dict[str, Any] = {}
    records: dict[bytes, dict[str, Any]] = {}
    for metadata in metadata_rows:
        document_id, path = _document_identity(metadata), candidate_section_path(metadata)
        raw = metadata.get("table_object_json")
        if not document_id or not path or not isinstance(raw, (str, Mapping)) or not raw:
            continue
        key = raw if isinstance(raw, str) else _json_bytes(raw).decode("utf-8")
        if key not in tables:
            try:
                tables[key] = json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, ValueError):
                tables[key] = None
        table = tables[key]
        if not isinstance(table, Mapping) or _path(table.get("source_section_path")) != path:
            continue
        table_id, locator, digest = (table.get(field) for field in
            ("table_id", "source_table_locator", "source_document_sha256"))
        if (not isinstance(table_id, str) or table_id.strip().casefold() in {"", "unknown", "?"}
                or not isinstance(locator, str) or not locator.startswith("/")
                or not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or any(metadata.get(field) and metadata[field] != table_id
                    for field in ("table_source_id", "source_table_id", "table_id"))
                or any(metadata.get(field) and metadata[field] != table[field]
                    for field in ("source_table_locator", "source_document_sha256"))):
            continue
        contexts = table.get("source_contexts")
        if not isinstance(contexts, list):
            continue
        attached = []
        for context in contexts:
            if not isinstance(context, Mapping) or context.get("relation") != "ancestor_heading":
                continue
            text, span = context.get("source_text"), context.get("source_span")
            parent, source = context.get("parent_locator"), context.get("source_locator")
            if (context.get("document_sha256") != digest or not isinstance(text, str) or not text.strip()
                    or not isinstance(span, list) or len(span) != 2 or any(type(n) is not int for n in span)
                    or span[0] < 0 or span[1] - span[0] != len(text)
                    or not isinstance(parent, str) or not parent.startswith("/")
                    or not isinstance(source, str) or source.rsplit("/", 1)[0] != parent
                    or re.fullmatch(r"TITLE(?:\[[1-9][0-9]*\])?", source.rsplit("/", 1)[-1]) is None
                    or not locator.startswith(parent + "/")):
                continue
            identity = {field: context[field] for field in
                ("document_sha256", "source_locator", "source_span", "source_text")}
            # Match parser context identity; do not invent/rekey old fragments.
            encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
            if context.get("context_id") != "ctx_" + hashlib.sha256(encoded).hexdigest()[:24]:
                continue
            attached.append(context)
        depth = max((context["parent_locator"].count("/") for context in attached), default=-1)
        for context in attached:
            if (context["parent_locator"].count("/") != depth
                    or _surface(context["source_text"]) in {_surface(part) for part in path}):
                continue
            section_id = _section_id(document_id, path)
            reference = {field: deepcopy(context[field]) for field in
                ("context_id", "document_sha256", "source_locator", "parent_locator", "source_span", "relation")}
            reference.update(table_source_id=table_id, source_table_locator=locator)
            key = _json_bytes([section_id, context["context_id"]])
            row = {"section_id": section_id, "heading": context["source_text"], "example_reference": reference}
            old = records.get(key)
            if old is None or _json_bytes(reference) < _json_bytes(old["example_reference"]):
                records[key] = row
    # Round-robin over visible parents prevents a large section from consuming
    # every hint slot. Keep one deterministic example per located title.
    groups = []
    for section in sections:
        rows = [row for row in records.values() if row["section_id"] == section["section_id"]]
        rows.sort(key=lambda row: (row["example_reference"]["source_locator"],
            row["example_reference"]["source_span"], row["heading"]))
        if rows:
            groups.append(rows)
    ordered = [rows[index] for index in range(max(map(len, groups), default=0)) for rows in groups if index < len(rows)]
    visible = []
    for row in ordered:
        if len(visible) >= max_hints or len(_json_bytes([*visible, row])) > max_bytes:
            break
        visible.append(row)
    encoded = _json_bytes(visible)
    return {"schema": "source_table_heading_hints_v1", "authority": "planning_hint_only", "headings": visible,
        "fingerprint": hashlib.sha256(encoded).hexdigest(), "serialized_heading_bytes": len(encoded),
        "observed_heading_count": len(records), "visible_heading_count": len(visible),
        "omitted_heading_count": len(records) - len(visible), "truncated": len(records) != len(visible),
        "coverage": "observed_nearest_ancestor_headings_only"}


def build_source_section_inventory(
    metadata_rows: Sequence[Mapping[str, Any]], *, max_sections: int = 256, max_bytes: int = 65536,
    max_heading_hints: int = 64, max_heading_bytes: int = 16384,
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
        "coverage": "observed_paths_only", "truncated": len(visible) != len(ordered),
        "table_heading_hints": _table_heading_hints(metadata_rows, visible,
            max_hints=max_heading_hints, max_bytes=max_heading_bytes)}


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
