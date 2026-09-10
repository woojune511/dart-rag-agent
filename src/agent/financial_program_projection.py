"""Dependency-light projections shared by program ingress and raw validation."""

from typing import Any, Mapping


def narrative_candidate_ids(binding: Mapping[str, Any]) -> list[str]:
    """Derive members once; never widen an explicit historical selection list."""
    if "candidate_ids" in binding:
        return [str(item).strip() for item in binding.get("candidate_ids") or [] if str(item).strip()]
    return list(dict.fromkeys(
        str(item.get("candidate_id") or "").strip()
        for item in binding.get("evidence_bindings") or []
        if isinstance(item, Mapping) and str(item.get("candidate_id") or "").strip()
    ))


def narrative_description_only_ids(validation: Mapping[str, Any]) -> set[str]:
    """Validated reading references cannot become scalar operands or evidence."""
    readings_by_owner = {}
    for binding in validation.get("valid_narrative_bindings") or []:
        readings = {item["candidate_id"] for item in binding.get("description_readings") or []}
        ordinary = {str(item.get("candidate_id") or "").strip()
            for item in binding.get("evidence_bindings") or [] if not item.get("row_description_quote")}
        readings_by_owner[binding["obligation_id"]] = readings - ordinary
    reading_ids, other_ids = set(), set()
    for owner_id, candidate_ids in (validation.get("source_candidate_ids_by_obligation") or {}).items():
        reading_ids.update(readings_by_owner.get(owner_id, set()))
        other_ids.update(set(candidate_ids) - readings_by_owner.get(owner_id, set()))
    return reading_ids - other_ids
