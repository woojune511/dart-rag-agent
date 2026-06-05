"""Report-scoped value cache contract helpers.

This module defines cache-key and cacheability rules only. Runtime callers
should consume these helpers before introducing any cache read/write behavior.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Mapping


REPORT_CACHE_KEY_VERSION = "report-cache-v1"
REPORT_CACHE_KEY_FIELDS = (
    "company",
    "report_type",
    "rcept_no",
    "year",
    "concept_id",
    "metric_label",
    "period",
    "consolidation_scope",
    "statement_type",
    "source_section",
    "source_table_id",
)

REPORT_SCOPE_FIELDS = ("company", "report_type", "rcept_no", "year")
VALUE_IDENTITY_FIELDS = ("concept_id", "metric_label", "period")
PROVENANCE_SCOPE_FIELDS = ("consolidation_scope", "statement_type", "source_section")

CACHE_REUSABLE = "reusable"
CACHE_REQUIRES_EVIDENCE_VERIFICATION = "requires_evidence_verification"
CACHE_NOT_CACHEABLE = "not_cacheable"

UNCERTAIN_TOKENS = {"", "-", "none", "null", "unknown", "n/a"}
UNCACHEABLE_VALUE_KINDS = {
    "synthesized_answer",
    "narrative_summary",
    "llm_interpretation",
    "refusal",
}
STRUCTURED_VALUE_KINDS = {"structured_row", "operand", "calculation_result"}


def _normalise_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if text.lower() in UNCERTAIN_TOKENS:
        return ""
    return text


def _first_text(*values: Any) -> str:
    for value in values:
        text = _normalise_text(value)
        if text:
            return text
    return ""


def _string_list(values: Any) -> List[str]:
    if isinstance(values, str):
        candidates: Iterable[Any] = [values]
    elif isinstance(values, Iterable) and not isinstance(values, Mapping):
        candidates = values
    else:
        candidates = []
    return [text for text in (_normalise_text(value) for value in candidates) if text]


def normalise_report_cache_key(parts: Mapping[str, Any]) -> Dict[str, str]:
    """Return a stable key payload using the reviewed report-cache fields."""
    data = dict(parts or {})
    return {
        "company": _normalise_text(data.get("company")),
        "report_type": _normalise_text(data.get("report_type")),
        "rcept_no": _normalise_text(data.get("rcept_no")),
        "year": _normalise_text(data.get("year")),
        "concept_id": _normalise_text(data.get("concept_id") or data.get("metric_id") or data.get("concept")),
        "metric_label": _normalise_text(data.get("metric_label") or data.get("label") or data.get("metric")),
        "period": _normalise_text(data.get("period") or data.get("period_label") or data.get("year")),
        "consolidation_scope": _normalise_text(data.get("consolidation_scope")),
        "statement_type": _normalise_text(data.get("statement_type")),
        "source_section": _normalise_text(
            data.get("source_section") or data.get("source_section_path") or data.get("section_path")
        ),
        "source_table_id": _normalise_text(
            data.get("source_table_id") or data.get("table_source_id") or data.get("table_id")
        ),
    }


def report_cache_key_id(parts: Mapping[str, Any]) -> str:
    """Return a deterministic string key for local stores or trace output."""
    key = normalise_report_cache_key(parts)
    payload = {field: key.get(field, "") for field in REPORT_CACHE_KEY_FIELDS}
    key_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{REPORT_CACHE_KEY_VERSION}:{key_json}"


def missing_key_fields(parts: Mapping[str, Any]) -> List[str]:
    """Return key fields that must be present before a value can be reused."""
    key = normalise_report_cache_key(parts)
    missing = [field for field in REPORT_SCOPE_FIELDS if not key.get(field)]
    if not (key.get("concept_id") or key.get("metric_label")):
        missing.append("concept_id_or_metric_label")
    if not key.get("period"):
        missing.append("period")
    return missing


def _candidate_value_kind(candidate: Mapping[str, Any]) -> str:
    return _normalise_text(candidate.get("value_kind") or candidate.get("kind") or candidate.get("source")).lower()


def _candidate_has_value(candidate: Mapping[str, Any]) -> bool:
    structured_result = dict(candidate.get("structured_result") or {})
    return bool(
        _first_text(
            candidate.get("value_text"),
            candidate.get("rendered_value"),
            candidate.get("answer_slot_display"),
            structured_result.get("rendered_value"),
            structured_result.get("formatted_value"),
        )
        or candidate.get("normalized_value") is not None
        or structured_result.get("value") is not None
    )


def _candidate_has_provenance(candidate: Mapping[str, Any]) -> bool:
    evidence_refs = _string_list(candidate.get("evidence_refs"))
    source_refs = _string_list(candidate.get("source_row_ids") or candidate.get("source_row_id"))
    return bool(
        evidence_refs
        or source_refs
        or _first_text(
            candidate.get("source_anchor"),
            candidate.get("source_section"),
            candidate.get("source_section_path"),
            candidate.get("table_source_id"),
            candidate.get("source_table_id"),
            candidate.get("chunk_id"),
            candidate.get("doc_id"),
        )
    )


def classify_report_cache_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    """Classify a candidate value before any report-scoped cache write.

    The classifier is intentionally conservative:
    - reusable: complete report key, structured value, and provenance scope
    - requires_evidence_verification: value exists but provenance/key confidence is incomplete
    - not_cacheable: synthesized/refusal/LLM-only material or value-free payload
    """
    payload = dict(candidate or {})
    kind = _candidate_value_kind(payload)
    if kind in UNCACHEABLE_VALUE_KINDS or payload.get("llm_only") is True:
        return {
            "status": CACHE_NOT_CACHEABLE,
            "reasons": ["uncacheable_value_kind"],
            "key": normalise_report_cache_key(payload),
        }

    key_missing = missing_key_fields(payload)
    has_value = _candidate_has_value(payload)
    has_provenance = _candidate_has_provenance(payload)
    key = normalise_report_cache_key(payload)
    reasons: List[str] = []
    if key_missing:
        reasons.extend(f"missing_key:{field}" for field in key_missing)
    if not has_value:
        reasons.append("missing_value")
    if not has_provenance:
        reasons.append("missing_provenance")
    for field in PROVENANCE_SCOPE_FIELDS:
        if not key.get(field):
            reasons.append(f"missing_scope:{field}")

    if not has_value:
        return {"status": CACHE_NOT_CACHEABLE, "reasons": reasons, "key": key}
    if reasons or kind not in STRUCTURED_VALUE_KINDS:
        if kind and kind not in STRUCTURED_VALUE_KINDS:
            reasons.append("non_structured_value_kind")
        return {
            "status": CACHE_REQUIRES_EVIDENCE_VERIFICATION,
            "reasons": list(dict.fromkeys(reasons)),
            "key": key,
        }
    return {"status": CACHE_REUSABLE, "reasons": [], "key": key}
