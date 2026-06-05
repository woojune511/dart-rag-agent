"""Report-scoped value cache contract helpers.

This module defines cache-key and cacheability rules only. Runtime callers
should consume these helpers before introducing any cache read/write behavior.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Mapping


REPORT_CACHE_KEY_VERSION = "report-cache-v1"
REPORT_CACHE_ENTRY_VERSION = "report-cache-entry-v1"
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
CACHE_CONSUMER_ELIGIBLE = "eligible"
CACHE_CONSUMER_BLOCKED = "blocked"
CACHE_CONSUMER_TRACE_ONLY = "trace_only"
CACHE_CONSUMER_ADMISSIBLE_FOR_DESIGN = "admissible_for_design"
CACHE_CONSUMER_FALLBACK_REQUIRED = "normal_retrieval_fallback"
CACHE_PROJECTION_VALID_FOR_CONTRACT = "valid_for_contract"
CACHE_ENTRY_READABLE = "readable"
CACHE_ENTRY_BLOCKED = "blocked"
CACHE_REHYDRATION_READY = "ready"
CACHE_REHYDRATION_BLOCKED = "blocked"

CACHE_ENTRY_SOURCE_LOCAL_INDEX = "local_cache_index"
CACHE_ENTRY_SOURCE_RUNTIME_TRACE = "runtime_trace_projection"
CACHE_ENTRY_SOURCE_ARTIFACT_STORE = "artifact_store"
CACHE_ENTRY_READ_SOURCES = {CACHE_ENTRY_SOURCE_LOCAL_INDEX}

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


def _first_mapping(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _mapping_list(values: Any) -> List[Dict[str, Any]]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes, Mapping)):
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


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


def classify_report_cache_consumer_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    """Assess whether a read-only projection is safe to consider for cache consumption.

    This does not enable cache reads. It only marks future retrieval-bypass
    eligibility for observability and keeps the runtime path trace-only.
    """
    payload = dict(candidate or {})
    key = normalise_report_cache_key(payload.get("key") if isinstance(payload.get("key"), Mapping) else payload)
    reasons: List[str] = []
    if not payload:
        reasons.append("missing_candidate")

    status = _normalise_text(payload.get("status")).lower()
    if status != CACHE_REUSABLE:
        reasons.append("candidate_not_reusable")
    if payload.get("read_only") is not True:
        reasons.append("missing_read_only_projection")

    candidate_reasons = [str(reason) for reason in list(payload.get("reasons") or []) if str(reason or "").strip()]
    if candidate_reasons:
        reasons.append("candidate_has_reasons")

    for field in missing_key_fields(key):
        reasons.append(f"missing_key:{field}")
    for field in PROVENANCE_SCOPE_FIELDS:
        if not key.get(field):
            reasons.append(f"missing_scope:{field}")
    if not key.get("source_table_id"):
        reasons.append("missing_scope:source_table_id")

    expected_key_id = report_cache_key_id(key)
    supplied_key_id = _normalise_text(payload.get("key_id"))
    if supplied_key_id and supplied_key_id != expected_key_id:
        reasons.append("key_id_mismatch")

    eligible = not reasons
    return {
        "status": CACHE_CONSUMER_ELIGIBLE if eligible else CACHE_CONSUMER_BLOCKED,
        "eligible": eligible,
        "enabled": False,
        "mode": CACHE_CONSUMER_TRACE_ONLY,
        "reasons": list(dict.fromkeys(reasons)),
        "key": key,
        "key_id": expected_key_id,
    }


def normalise_report_cache_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the reviewed persisted-entry shape for a future cache index.

    Runtime trace projections and MAS artifacts may produce candidates, but a
    readable cache hit must come from a persisted cache index entry.
    """
    payload = dict(entry or {})
    key_payload = payload.get("key") if isinstance(payload.get("key"), Mapping) else payload
    key = normalise_report_cache_key(key_payload)
    value_payload = _first_mapping(payload.get("value"), payload.get("structured_result"))
    provenance_payload = _first_mapping(payload.get("provenance"))
    source_row_ids = _string_list(
        provenance_payload.get("source_row_ids")
        or provenance_payload.get("source_row_id")
        or payload.get("source_row_ids")
        or payload.get("source_row_id")
    )
    evidence_refs = _string_list(
        provenance_payload.get("evidence_refs")
        or provenance_payload.get("evidence_ref")
        or payload.get("evidence_refs")
        or payload.get("evidence_ref")
    )
    rendered_value = _first_text(
        value_payload.get("rendered_value"),
        value_payload.get("value_text"),
        payload.get("rendered_value"),
        payload.get("value_text"),
    )
    normalized_value = (
        value_payload.get("normalized_value")
        if value_payload.get("normalized_value") is not None
        else payload.get("normalized_value")
    )
    return {
        "entry_version": _normalise_text(payload.get("entry_version") or payload.get("version")),
        "source": _normalise_text(payload.get("source") or payload.get("entry_source")),
        "key": key,
        "key_id": _normalise_text(payload.get("key_id")) or report_cache_key_id(key),
        "value": {
            "kind": _normalise_text(
                value_payload.get("kind") or value_payload.get("value_kind") or payload.get("value_kind")
            ),
            "rendered_value": rendered_value,
            "normalized_value": normalized_value,
            "normalized_unit": _normalise_text(value_payload.get("normalized_unit") or payload.get("normalized_unit")),
            "result_unit": _normalise_text(value_payload.get("result_unit") or payload.get("result_unit")),
            "answer_slots": _first_mapping(value_payload.get("answer_slots"), payload.get("answer_slots")),
            "calculation_trace": _first_mapping(
                value_payload.get("calculation_trace"),
                value_payload.get("resolved_calculation_trace"),
                payload.get("calculation_trace"),
                payload.get("resolved_calculation_trace"),
            ),
            "citations": _string_list(value_payload.get("citations") or payload.get("citations")),
            "evidence_items": _mapping_list(value_payload.get("evidence_items") or payload.get("evidence_items")),
        },
        "provenance": {
            "source_row_ids": source_row_ids,
            "evidence_refs": evidence_refs,
            "source_anchor": _first_text(provenance_payload.get("source_anchor"), payload.get("source_anchor")),
        },
    }


def classify_report_cache_rehydration_candidate(entry: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate whether a readable entry has enough payload to rebuild an answer.

    This is still a disabled consumer contract. Passing this classifier does
    not enable cache serving; it only defines the minimum material a future
    consumer would need before considering retrieval bypass.
    """
    entry_classification = classify_report_cache_entry(entry)
    normalised = dict(entry_classification.get("entry") or {})
    value = dict(normalised.get("value") or {})
    provenance = dict(normalised.get("provenance") or {})
    answer_slots = dict(value.get("answer_slots") or {})
    primary_slot = dict(answer_slots.get("primary_value") or {})
    calculation_trace = dict(value.get("calculation_trace") or {})
    citations = _string_list(value.get("citations"))
    evidence_items = _mapping_list(value.get("evidence_items"))
    reasons: List[str] = []

    if not bool(entry_classification.get("readable")):
        reasons.append("entry_not_readable")
        reasons.extend(f"entry:{reason}" for reason in list(entry_classification.get("reasons") or []))

    if not answer_slots:
        reasons.append("missing_answer_slots")
    if not primary_slot:
        reasons.append("missing_primary_answer_slot")
    elif not _first_text(
        primary_slot.get("display"),
        primary_slot.get("rendered_value"),
        primary_slot.get("raw_value"),
        primary_slot.get("value"),
    ):
        reasons.append("missing_primary_answer_slot_display")

    if not (citations or provenance.get("source_anchor")):
        reasons.append("missing_citation_or_source_anchor")
    if not (evidence_items or provenance.get("evidence_refs") or provenance.get("source_row_ids")):
        reasons.append("missing_rehydratable_evidence")

    if not calculation_trace:
        reasons.append("missing_calculation_trace")
    else:
        if not isinstance(calculation_trace.get("calculation_result"), Mapping):
            reasons.append("missing_trace_calculation_result")
        if not isinstance(calculation_trace.get("calculation_operands"), list):
            reasons.append("missing_trace_calculation_operands")

    ready = not reasons
    return {
        "status": CACHE_REHYDRATION_READY if ready else CACHE_REHYDRATION_BLOCKED,
        "ready": ready,
        "enabled": False,
        "serving_enabled": False,
        "reasons": list(dict.fromkeys(reasons)),
        "entry_status": entry_classification.get("status"),
        "key": entry_classification.get("key"),
        "key_id": entry_classification.get("key_id"),
        "entry": normalised,
    }


def classify_report_cache_guarded_consumer_candidate(
    entry: Mapping[str, Any],
    *,
    expected_key: Mapping[str, Any] | None = None,
    selected_match_count: int = 1,
) -> Dict[str, Any]:
    """Assess future guarded-consumer admissibility without enabling cache reads.

    This is a design contract helper, not a serving path. It classifies whether
    a local-index entry has enough structure to be considered by a future
    schema-backed cache consumer, while keeping the runtime mode trace-only.
    """
    rehydration = classify_report_cache_rehydration_candidate(entry)
    key = dict(rehydration.get("key") or {})
    expected = normalise_report_cache_key(expected_key or key)
    reasons: List[str] = []

    if selected_match_count < 1:
        reasons.append("no_readable_match")
    elif selected_match_count > 1:
        reasons.append("ambiguous_rehydration_match")

    if not bool(rehydration.get("ready")):
        reasons.append("rehydration_not_ready")
        reasons.extend(str(reason) for reason in list(rehydration.get("reasons") or []) if str(reason))

    for field in REPORT_CACHE_KEY_FIELDS:
        expected_value = expected.get(field, "")
        if expected_value and key.get(field, "") != expected_value:
            reasons.append(f"scope_mismatch:{field}")

    admissible = not reasons
    return {
        "status": CACHE_CONSUMER_ADMISSIBLE_FOR_DESIGN if admissible else CACHE_CONSUMER_FALLBACK_REQUIRED,
        "admissible": admissible,
        "fallback_required": not admissible,
        "enabled": False,
        "serving_enabled": False,
        "mode": CACHE_CONSUMER_TRACE_ONLY,
        "reasons": list(dict.fromkeys(reasons)),
        "key": key,
        "key_id": str(rehydration.get("key_id") or ""),
        "rehydration_status": rehydration.get("status"),
        "rehydration_ready": bool(rehydration.get("ready")),
    }


def build_report_cache_rehydrated_candidate_artifact(
    entry: Mapping[str, Any],
    *,
    task_id: str = "",
    artifact_id: str = "",
) -> Dict[str, Any]:
    """Project a rehydration-ready entry into a non-serving answer artifact.

    This helper is intentionally not a cache read path. It only defines the
    payload a future consumer would need to validate before any retrieval
    bypass could be considered.
    """
    rehydration = classify_report_cache_rehydration_candidate(entry)
    consumer_admissibility = classify_report_cache_guarded_consumer_candidate(entry)
    consumer_contract = {
        "status": consumer_admissibility.get("status"),
        "admissible": bool(consumer_admissibility.get("admissible")),
        "fallback_required": bool(consumer_admissibility.get("fallback_required")),
        "enabled": False,
        "serving_enabled": False,
        "mode": consumer_admissibility.get("mode"),
        "reasons": [str(reason) for reason in list(consumer_admissibility.get("reasons") or [])],
    }
    base = {
        "status": rehydration.get("status"),
        "ready": bool(rehydration.get("ready")),
        "enabled": False,
        "serving_enabled": False,
        "reasons": [str(reason) for reason in list(rehydration.get("reasons") or [])],
        "key": dict(rehydration.get("key") or {}),
        "key_id": str(rehydration.get("key_id") or ""),
        "consumer_admissibility": dict(consumer_contract),
        "artifact": None,
    }
    if not bool(rehydration.get("ready")):
        return base

    normalised = dict(rehydration.get("entry") or {})
    value = dict(normalised.get("value") or {})
    provenance = dict(normalised.get("provenance") or {})
    calculation_trace = dict(value.get("calculation_trace") or {})
    calculation_result = dict(calculation_trace.get("calculation_result") or {})
    answer_slots = dict(value.get("answer_slots") or {})
    primary_slot = dict(answer_slots.get("primary_value") or {})
    rendered_value = _first_text(
        primary_slot.get("display"),
        primary_slot.get("rendered_value"),
        primary_slot.get("raw_value"),
        primary_slot.get("value"),
        calculation_result.get("rendered_value"),
        calculation_result.get("formatted_result"),
        value.get("rendered_value"),
    )
    citations = _string_list(value.get("citations"))
    evidence_items = _mapping_list(value.get("evidence_items"))
    evidence_refs = _string_list(
        citations
        + _string_list(provenance.get("evidence_refs"))
        + _string_list(provenance.get("source_row_ids"))
        + [provenance.get("source_anchor")]
    )
    structured_result = {
        **calculation_result,
        "rendered_value": _first_text(calculation_result.get("rendered_value"), rendered_value),
        "formatted_result": _first_text(calculation_result.get("formatted_result"), rendered_value),
        "answer_slots": answer_slots,
    }
    payload = {
        "answer": rendered_value,
        "citations": citations,
        "evidence_items": evidence_items,
        "resolved_calculation_trace": calculation_trace,
        "structured_result": structured_result,
        "report_cache_key": dict(rehydration.get("key") or {}),
        "report_cache_key_id": str(rehydration.get("key_id") or ""),
        "cache_origin": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
        "report_cache_rehydration": {
            "status": rehydration.get("status"),
            "ready": bool(rehydration.get("ready")),
            "enabled": False,
            "serving_enabled": False,
            "reasons": [],
        },
        "consumer_admissibility": dict(consumer_contract),
    }
    base["artifact"] = {
        "artifact_id": str(artifact_id or f"report_cache_rehydrated::{rehydration.get('key_id') or ''}").strip(),
        "task_id": str(task_id or "").strip(),
        "creator": "ReportCacheIndex",
        "kind": "calculation_result",
        "status": "candidate",
        "summary": rendered_value,
        "content": dict(payload),
        "payload": dict(payload),
        "evidence_links": evidence_refs,
        "evidence_refs": evidence_refs,
        "metadata": {
            "source": "report_cache_rehydration",
            "cache_origin": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
            "report_cache_key_id": str(rehydration.get("key_id") or ""),
            "rehydration_status": str(rehydration.get("status") or ""),
            "consumer_admissibility_status": str(consumer_admissibility.get("status") or ""),
            "enabled": False,
            "serving_enabled": False,
            "ledger_insertion_enabled": False,
        },
    }
    return base


def build_report_cache_calculation_contract_projection(
    entry: Mapping[str, Any],
    *,
    task_id: str = "",
) -> Dict[str, Any]:
    """Project a rehydrated cache candidate onto calculation ledger surfaces.

    This is a disabled schema contract helper. It does not insert anything into
    the task/artifact ledger and does not enable cache serving; it only shows
    the exact calculation task/artifact surfaces a future producer policy would
    need to validate.
    """
    candidate = build_report_cache_rehydrated_candidate_artifact(entry, task_id=task_id)
    base = {
        "status": candidate.get("status"),
        "ready": bool(candidate.get("ready")),
        "enabled": False,
        "serving_enabled": False,
        "ledger_insertion_enabled": False,
        "reasons": [str(reason) for reason in list(candidate.get("reasons") or [])],
        "key": dict(candidate.get("key") or {}),
        "key_id": str(candidate.get("key_id") or ""),
        "consumer_admissibility": dict(candidate.get("consumer_admissibility") or {}),
        "projection": None,
    }
    artifact = candidate.get("artifact") if isinstance(candidate.get("artifact"), Mapping) else None
    if not artifact:
        return base

    resolved_task_id = str(task_id or artifact.get("task_id") or "report_cache_candidate_task").strip()
    payload = dict(artifact.get("payload") or {})
    trace = dict(payload.get("resolved_calculation_trace") or {})
    calculation_operands = list(trace.get("calculation_operands") or [])
    calculation_plan = dict(trace.get("calculation_plan") or {})
    calculation_result = dict(payload.get("structured_result") or trace.get("calculation_result") or {})
    if not any(str(calculation_result.get(key) or "").strip() for key in ("rendered_value", "formatted_result")):
        rendered_value = str(payload.get("answer") or "").strip()
        if rendered_value:
            calculation_result["rendered_value"] = rendered_value
            calculation_result["formatted_result"] = rendered_value
    if not calculation_plan:
        calculation_plan = {
            "mode": "cache_rehydrated_candidate",
            "source": "report_cache_rehydration",
        }

    common_metadata = {
        "source": "report_cache_rehydration",
        "cache_origin": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
        "report_cache_key_id": str(candidate.get("key_id") or ""),
        "rehydration_status": str(candidate.get("status") or ""),
        "consumer_admissibility_status": str(
            (candidate.get("consumer_admissibility") or {}).get("status") or ""
        ),
        "enabled": False,
        "serving_enabled": False,
        "ledger_insertion_enabled": False,
    }
    evidence_refs = _string_list(artifact.get("evidence_refs") or artifact.get("evidence_links"))
    artifact_ids = {
        "operand": f"{resolved_task_id}::operand_set",
        "plan": f"{resolved_task_id}::calculation_plan",
        "result": resolved_task_id,
    }
    artifacts = {
        artifact_ids["operand"]: {
            "task_id": resolved_task_id,
            "creator": "ReportCacheIndex",
            "artifact_id": artifact_ids["operand"],
            "kind": "operand_set",
            "status": "candidate",
            "summary": f"{len(calculation_operands)} operands",
            "content": {"calculation_operands": calculation_operands},
            "payload": {"calculation_operands": calculation_operands},
            "evidence_links": evidence_refs,
            "evidence_refs": evidence_refs,
            "metadata": dict(common_metadata),
        },
        artifact_ids["plan"]: {
            "task_id": resolved_task_id,
            "creator": "ReportCacheIndex",
            "artifact_id": artifact_ids["plan"],
            "kind": "calculation_plan",
            "status": "candidate",
            "summary": str(calculation_plan.get("operation") or calculation_plan.get("mode") or "").strip(),
            "content": {"calculation_plan": calculation_plan},
            "payload": {"calculation_plan": calculation_plan},
            "evidence_links": evidence_refs,
            "evidence_refs": evidence_refs,
            "metadata": dict(common_metadata),
        },
        artifact_ids["result"]: {
            "task_id": resolved_task_id,
            "creator": "ReportCacheIndex",
            "artifact_id": artifact_ids["result"],
            "kind": "calculation_result",
            "status": "candidate",
            "summary": str(artifact.get("summary") or payload.get("answer") or "").strip(),
            "content": {
                "answer": payload.get("answer", ""),
                "citations": list(payload.get("citations") or []),
                "evidence_items": list(payload.get("evidence_items") or []),
                "resolved_calculation_trace": trace,
                "structured_result": dict(payload.get("structured_result") or {}),
                "report_cache_key": dict(payload.get("report_cache_key") or {}),
                "report_cache_key_id": str(payload.get("report_cache_key_id") or ""),
                "cache_origin": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
                "consumer_admissibility": dict(payload.get("consumer_admissibility") or {}),
            },
            "payload": {
                "answer": payload.get("answer", ""),
                "structured_result": dict(payload.get("structured_result") or {}),
                "resolved_calculation_trace": trace,
                "calculation_result": calculation_result,
                "report_cache_key_id": str(payload.get("report_cache_key_id") or ""),
                "cache_origin": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
                "consumer_admissibility": dict(payload.get("consumer_admissibility") or {}),
            },
            "evidence_links": evidence_refs,
            "evidence_refs": evidence_refs,
            "metadata": dict(common_metadata),
        },
    }
    base["projection"] = {
        "task": {
            "task_id": resolved_task_id,
            "kind": "calculation",
            "status": "candidate",
            "artifact_ids": [
                artifact_ids["operand"],
                artifact_ids["plan"],
                artifact_ids["result"],
            ],
            "artifact_kinds": ["operand_set", "calculation_plan", "calculation_result"],
            "metadata": dict(common_metadata),
        },
        "artifacts": artifacts,
        "metadata": dict(common_metadata),
    }
    return base


def validate_report_cache_calculation_contract_projection(
    entry: Mapping[str, Any],
    *,
    task_id: str = "",
) -> Dict[str, Any]:
    """Validate the candidate calculation projection without ledger insertion."""
    projection_result = build_report_cache_calculation_contract_projection(entry, task_id=task_id)
    projection_payload = projection_result.get("projection")
    projection = projection_payload if isinstance(projection_payload, Mapping) else None
    reasons: List[str] = []
    required_kinds = ["operand_set", "calculation_plan", "calculation_result"]

    if not projection:
        reasons.append("projection_not_available")
        reasons.extend(str(reason) for reason in list(projection_result.get("reasons") or []) if str(reason))
        valid = False
        return {
            "status": CACHE_CONSUMER_FALLBACK_REQUIRED,
            "valid_for_contract": valid,
            "fallback_required": True,
            "enabled": False,
            "serving_enabled": False,
            "ledger_insertion_enabled": False,
            "reasons": list(dict.fromkeys(reasons)),
            "projection": None,
            "required_artifact_kinds": required_kinds,
            "key": dict(projection_result.get("key") or {}),
            "key_id": str(projection_result.get("key_id") or ""),
        }

    task = dict(projection.get("task") or {})
    artifacts = dict(projection.get("artifacts") or {})
    artifact_ids = [
        str(value).strip()
        for value in list(task.get("artifact_ids") or [])
        if str(value).strip()
    ]
    artifact_kinds = [
        str(value).strip()
        for value in list(task.get("artifact_kinds") or [])
        if str(value).strip()
    ]

    if str(task.get("kind") or "").strip() != "calculation":
        reasons.append("task_kind_not_calculation")
    if str(task.get("status") or "").strip() != "candidate":
        reasons.append("task_status_not_candidate")
    if bool((task.get("metadata") or {}).get("serving_enabled")):
        reasons.append("task_serving_enabled")
    if bool((task.get("metadata") or {}).get("ledger_insertion_enabled")):
        reasons.append("task_ledger_insertion_enabled")

    for required_kind in required_kinds:
        if required_kind not in artifact_kinds:
            reasons.append(f"missing_required_artifact_kind:{required_kind}")

    attached_artifacts = [
        dict(artifacts.get(artifact_id) or {})
        for artifact_id in artifact_ids
        if isinstance(artifacts.get(artifact_id), Mapping)
    ]
    present_artifact_ids = {
        str(artifact.get("artifact_id") or "").strip()
        for artifact in attached_artifacts
        if str(artifact.get("artifact_id") or "").strip()
    }
    for artifact_id in artifact_ids:
        if artifact_id not in present_artifact_ids:
            reasons.append(f"missing_artifact:{artifact_id}")

    for artifact in attached_artifacts:
        artifact_kind = str(artifact.get("kind") or "").strip()
        payload = artifact.get("payload") if isinstance(artifact.get("payload"), Mapping) else {}
        metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), Mapping) else {}
        if str(artifact.get("status") or "").strip() != "candidate":
            reasons.append(f"artifact_status_not_candidate:{artifact_kind or 'unknown'}")
        if bool(metadata.get("serving_enabled")):
            reasons.append(f"artifact_serving_enabled:{artifact_kind or 'unknown'}")
        if bool(metadata.get("ledger_insertion_enabled")):
            reasons.append(f"artifact_ledger_insertion_enabled:{artifact_kind or 'unknown'}")
        if artifact_kind == "operand_set":
            if (
                not isinstance(payload.get("calculation_operands"), list)
                or not payload.get("calculation_operands")
            ):
                reasons.append("missing_required_artifact_payload:operand_set.calculation_operands")
        elif artifact_kind == "calculation_plan":
            plan = payload.get("calculation_plan") if isinstance(payload.get("calculation_plan"), Mapping) else {}
            if not plan or not _first_text(plan.get("operation"), plan.get("mode")):
                reasons.append("missing_required_artifact_payload:calculation_plan.calculation_plan")
        elif artifact_kind == "calculation_result":
            result_payload = (
                payload.get("calculation_result")
                if isinstance(payload.get("calculation_result"), Mapping)
                else {}
            )
            if not (
                _first_text(result_payload.get("rendered_value"), result_payload.get("formatted_result"))
                or bool(result_payload.get("answer_slots"))
            ):
                reasons.append("missing_required_artifact_payload:calculation_result.calculation_result")

    has_evidence_ref = any(
        _string_list(artifact.get("evidence_refs") or artifact.get("evidence_links"))
        for artifact in attached_artifacts
    )
    if not has_evidence_ref:
        reasons.append("missing_required_evidence_ref")

    valid = not reasons
    return {
        "status": CACHE_PROJECTION_VALID_FOR_CONTRACT if valid else CACHE_CONSUMER_FALLBACK_REQUIRED,
        "valid_for_contract": valid,
        "fallback_required": not valid,
        "enabled": False,
        "serving_enabled": False,
        "ledger_insertion_enabled": False,
        "reasons": list(dict.fromkeys(reasons)),
        "projection": projection,
        "required_artifact_kinds": required_kinds,
        "key": dict(projection_result.get("key") or {}),
        "key_id": str(projection_result.get("key_id") or ""),
    }


def classify_report_cache_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate whether a persisted entry may be read as a cache hit."""
    normalised = normalise_report_cache_entry(entry)
    key = dict(normalised.get("key") or {})
    value = dict(normalised.get("value") or {})
    provenance = dict(normalised.get("provenance") or {})
    reasons: List[str] = []

    if normalised.get("entry_version") != REPORT_CACHE_ENTRY_VERSION:
        reasons.append("invalid_entry_version")
    if normalised.get("source") not in CACHE_ENTRY_READ_SOURCES:
        reasons.append("non_read_source")
    for field in missing_key_fields(key):
        reasons.append(f"missing_key:{field}")
    for field in PROVENANCE_SCOPE_FIELDS:
        if not key.get(field):
            reasons.append(f"missing_scope:{field}")
    if not key.get("source_table_id"):
        reasons.append("missing_scope:source_table_id")

    expected_key_id = report_cache_key_id(key)
    if normalised.get("key_id") != expected_key_id:
        reasons.append("key_id_mismatch")

    if not (value.get("rendered_value") or value.get("normalized_value") is not None):
        reasons.append("missing_value")
    if not (provenance.get("source_row_ids") or provenance.get("evidence_refs") or provenance.get("source_anchor")):
        reasons.append("missing_provenance")

    readable = not reasons
    return {
        "status": CACHE_ENTRY_READABLE if readable else CACHE_ENTRY_BLOCKED,
        "readable": readable,
        "reasons": list(dict.fromkeys(reasons)),
        "entry": normalised,
        "key": key,
        "key_id": expected_key_id,
    }
