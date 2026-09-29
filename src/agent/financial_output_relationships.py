"""Request-grounded output relationships, not shared free-form grouping keys."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping, Sequence

from src.agent.financial_request_units import build_request_units


def output_relationships(obligations: Sequence[Mapping[str, Any]], query: str):
    order = {row["obligation_id"]: index for index, row in enumerate(obligations)}
    units = {unit.request_unit_id: unit for unit in build_request_units(query)}
    groups, errors = {}, []
    for owner in obligations:
        owner_id = owner["obligation_id"]

        def error(code):
            errors.append({"code": code, "obligation_id": owner_id, "owner_id": owner_id,
                "candidate_id": "", "location": "output_relationships", "repair_action": "repair_requirements", "detail": ""})

        if owner.get("coupling_key"):
            error("legacy_coupling_key_unsupported")
        for relation in owner.get("output_relationships") or []:
            if not isinstance(relation, Mapping):
                error("invalid_output_relationship")
                continue
            members = relation.get("output_ids")
            ref, quote = relation.get("request_unit_id"), relation.get("request_text")
            if (relation.get("kind") != "shared_basis" or not isinstance(members, list)
                    or len(members) < 2 or any(not isinstance(item, str) or item not in order for item in members)
                    or len(set(members)) != len(members) or owner_id not in members):
                error("invalid_output_relationship")
                continue
            if (not isinstance(ref, str) or ref not in units or not isinstance(quote, str)
                    or not quote.strip() or quote not in units[ref].text
                    or any(ref not in obligations[order[member]].get("request_unit_ids", []) for member in members)):
                error("ungrounded_output_relationship")
                continue
            row = {"kind": "shared_basis", "output_ids": sorted(members, key=order.__getitem__),
                   "request_unit_id": ref, "request_text": quote}
            digest = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            groups["relation_" + digest[:20]] = row
    return groups, errors


def relationship_proof_projection(program, owner_ids):
    """Keep explicitly authored links for these outputs and their declarations."""
    if not owner_ids:
        return {}
    bindings = {key: deepcopy(value) for key, value in (program.get("relationship_bindings") or {}).items()
                if key in owner_ids}
    referenced = {ref for values in bindings.values() for ref in values}
    declarations = {key: deepcopy(value) for key, value in (program.get("relationship_declarations") or {}).items()
                    if key in referenced}
    return {"relationship_declarations": declarations, "relationship_bindings": bindings} if bindings else {}


def validated_relationship_proofs(validation, owner_ids):
    return relationship_proof_projection({key: validation.get("valid_" + key, {})
        for key in ("relationship_declarations", "relationship_bindings")}, owner_ids)


def validate_relationship_proofs(program, relationships, produced, owner_ids):
    """Validate explicit declaration ownership, never textual/semantic equivalence."""
    errors, invalid = [], set()

    def fail(code, owners, location, detail=""):
        for owner in owners:
            errors.append({"code": code, "obligation_id": owner, "owner_id": owner,
                "candidate_id": "", "location": location, "repair_action": "repair_program", "detail": detail})
            invalid.add(owner)

    declarations = program.get("relationship_declarations", {})
    bindings = program.get("relationship_bindings", {})
    if not isinstance(declarations, Mapping) or not isinstance(bindings, Mapping):
        fail("invalid_relationship_proof", owner_ids, "relationship_declarations/relationship_bindings")
        return errors, invalid
    for key in declarations:
        if key not in relationships:
            fail("unknown_relationship_declaration", owner_ids, "relationship_declarations", str(key))
    for key in bindings:
        if key not in owner_ids:
            fail("unknown_relationship_binding_owner", owner_ids, "relationship_bindings", str(key))
    for key, relation in relationships.items():
        members = relation["output_ids"]
        value = declarations.get(key)
        if value is None and not produced.intersection(members):
            continue  # An abstaining group needs no invented common interpretation.
        if key not in declarations or value is None:
            fail("relationship_declaration_missing", members, "relationship_declarations", key)
        elif not isinstance(value, str) or not value.strip():
            fail("invalid_relationship_declaration", members, "relationship_declarations", key)
    for owner in owner_ids:
        expected = {key for key, row in relationships.items() if owner in row["output_ids"]}
        if owner in invalid or (owner not in produced and owner not in bindings):
            continue
        refs = bindings.get(owner, [])
        if (not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs)
                or len(set(refs)) != len(refs) or set(refs) != expected):
            affected = {owner, *(member for key in expected for member in relationships[key]["output_ids"])}
            fail("relationship_reference_missing_or_invalid", [key for key in owner_ids if key in affected],
                 "relationship_bindings", owner)
    return errors, invalid
