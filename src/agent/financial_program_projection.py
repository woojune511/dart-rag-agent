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
