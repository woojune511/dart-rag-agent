"""Dependency-light projections shared by program ingress and raw validation."""

from typing import Any, Mapping


def project_narrative_claims(binding: Mapping[str, Any]) -> dict[str, Any]:
    """Claims are the only writer of current narrative text and evidence links.

    Flat historical input may be inspected, but current compilation requires claims.
    Explicit flat projections must agree; never silently discard extra assertions.
    """
    claims = binding.get("claims")
    if not claims:
        return dict(binding)
    if not isinstance(claims, list) or any(not isinstance(row, Mapping) for row in claims):
        raise ValueError("invalid_narrative_claims")
    texts, evidence = [], []
    for claim in claims:
        if not isinstance(claim.get("text"), str):
            raise ValueError("invalid_narrative_claims")
        texts.append(" ".join(claim["text"].split()))
        links = claim.get("evidence_bindings")
        if not isinstance(links, list) or any(not isinstance(row, Mapping) for row in links):
            raise ValueError("invalid_narrative_claims")
        for link in links:
            projected = {key: link.get(key, "") for key in (
                "candidate_id", "source_requirement_id", "row_description_quote")}
            if projected not in evidence:
                evidence.append(projected)
    text = " ".join(texts)
    if "text" in binding and " ".join(str(binding["text"]).split()) != text:
        raise ValueError("narrative_claim_projection_mismatch")
    if "evidence_bindings" in binding:
        explicit = [{key: row.get(key, "") for key in (
            "candidate_id", "source_requirement_id", "row_description_quote")}
            for row in binding["evidence_bindings"] or [] if isinstance(row, Mapping)]
        if explicit != evidence:
            raise ValueError("narrative_claim_projection_mismatch")
    return {**binding, "text": text, "evidence_bindings": evidence}


def narrative_candidate_ids(binding: Mapping[str, Any]) -> list[str]:
    """Derive members once; never widen an explicit historical selection list."""
    if "candidate_ids" in binding:
        return [str(item).strip() for item in binding.get("candidate_ids") or [] if str(item).strip()]
    return list(dict.fromkeys(
        str(item.get("candidate_id") or "").strip()
        for item in project_narrative_claims(binding).get("evidence_bindings") or []
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
