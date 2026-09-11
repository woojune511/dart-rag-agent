"""Lossless request addressing, not semantic clause detection or evidence."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence


# Mechanical sentence/line boundaries only. Ambiguous abbreviations can span
# multiple units: assigning the same unit to several outputs is permitted.
_BOUNDARY = re.compile(r'''(?:[.!?。！？]["'”’)\]]*(?=\s|$)\s*|[\r\n]+\s*)''')


@dataclass(frozen=True, slots=True)
class RequestUnitV1:
    request_unit_id: str
    start: int
    end: int
    text: str


def build_request_units(query: str) -> tuple[RequestUnitV1, ...]:
    """Partition the exact query; offsets are Python string indices, not bytes."""
    units: list[RequestUnitV1] = []
    start = 0
    for end in [match.end() for match in _BOUNDARY.finditer(query)] + [len(query)]:
        text = query[start:end]
        if not text.strip():
            continue
        units.append(RequestUnitV1(f"request_{len(units) + 1:03d}", start, end, text))
        start = end
    return tuple(units)


def project_request_units(
    units: Sequence[RequestUnitV1],
    obligations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Copy all units for planning, or only active owners' units for compilation."""
    selected = None if obligations is None else {
        unit_id for row in obligations for unit_id in row.get("request_unit_ids", [])
    }
    return {
        unit.request_unit_id: {"text": unit.text, "span": [unit.start, unit.end]}
        for unit in units if selected is None or unit.request_unit_id in selected
    }


def request_unit_errors(
    units: Sequence[RequestUnitV1], obligations: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Check ID ownership for the whole query. Never infer a missing assignment."""
    known = {unit.request_unit_id for unit in units}
    assigned: set[str] = set()
    errors: list[dict[str, str]] = []

    def error(code: str, owner: str = "", unit_id: str = "") -> None:
        errors.append({
            "code": code, "obligation_id": owner, "owner_id": owner,
            "request_unit_id": unit_id, "candidate_id": "",
            "location": "obligation.request_unit_ids" if owner else "request.units",
            "repair_action": "repair_requirements",
        })

    if not units:
        error("empty_request")
    for row in obligations:
        owner = str(row.get("obligation_id") or "")
        refs = row.get("request_unit_ids")
        if refs is None or refs == []:
            error("missing_request_unit_refs", owner)
            continue
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            error("invalid_request_unit_refs", owner)
            continue
        for ref in dict.fromkeys(refs):
            if ref not in known:
                error("unknown_request_unit_id", owner, ref)
            else:
                assigned.add(ref)
    for unit in units:
        if unit.request_unit_id not in assigned:
            error("unassigned_request_unit", unit_id=unit.request_unit_id)
    return errors
