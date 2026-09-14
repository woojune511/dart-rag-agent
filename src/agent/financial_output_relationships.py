"""Request-grounded output relationships, not shared free-form grouping keys."""

from __future__ import annotations

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
                    or not quote.strip() or quote not in units[ref].text):
                error("ungrounded_output_relationship")
                continue
            row = {"kind": "shared_basis", "output_ids": sorted(members, key=order.__getitem__),
                   "request_unit_id": ref, "request_text": quote}
            digest = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            groups["relation_" + digest[:20]] = row
    return groups, errors
