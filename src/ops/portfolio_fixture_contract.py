"""Validate the checked-in portfolio fixture and its cross-surface contract."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List

from src.agent.financial_artifact_contracts import (
    critic_report_runtime_acceptance_state,
)


_NUMERIC_TOKEN_PATTERN = re.compile(
    r"[-+]?(?:\d[\d,]*)(?:\.\d+)?(?:[eE][-+]?\d+)?"
)
_FIXTURE_HASH_NORMALIZATION = "line_endings_lf"


def _read_json_object(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"fixture contract JSON must be an object: {path}")
    return dict(payload)


def _first_mapping(items: Any) -> Dict[str, Any]:
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                return dict(item)
    return {}


def _mapping_list(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def _normalized_lf_sha256_hex(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest()


def _summarize_evidence_manifest(
    *,
    manifest_path: Path,
    payload_path: Path,
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "status": "invalid",
        "manifest_path": str(manifest_path),
        "fixture_path": str(payload_path),
        "fixture_sha256_expected": None,
        "fixture_sha256_actual": None,
        "fixture_sha256_matches": False,
        "fixture_hash_normalization": None,
        "fixture_path_matches": False,
        "evidence_kind": None,
        "upstream_artifact_availability": None,
        "live_runtime_replayed": None,
        "raw_runtime_bundle_checked_in": None,
        "limitations": [],
        "claim_boundary": {},
        "error": None,
    }
    try:
        manifest = _read_json_object(manifest_path)
        binding = dict(manifest.get("fixture_binding") or {})
        source = dict(manifest.get("source_provenance") or {})
        claim_boundary = dict(manifest.get("claim_boundary") or {})
        expected_hash = str(binding.get("sha256") or "").strip().lower()
        hash_normalization = str(binding.get("normalization") or "").strip().lower()
        bound_path = manifest_path.parent / str(binding.get("path") or "")
        actual_hash = _normalized_lf_sha256_hex(payload_path)
        limitations = [
            str(item).strip()
            for item in list(source.get("limitations") or [])
            if str(item).strip()
        ]
        supported_claims = [
            str(item).strip()
            for item in list(claim_boundary.get("supports") or [])
            if str(item).strip()
        ]
        unsupported_claims = [
            str(item).strip()
            for item in list(claim_boundary.get("does_not_support") or [])
            if str(item).strip()
        ]
        path_matches = bool(binding.get("path")) and (
            bound_path.resolve() == payload_path.resolve()
        )
        hash_matches = bool(expected_hash) and expected_hash == actual_hash
        manifest_contract_complete = (
            manifest.get("schema_version") == 2
            and str(binding.get("algorithm") or "").strip().lower() == "sha256"
            and hash_normalization == _FIXTURE_HASH_NORMALIZATION
            and source.get("evidence_kind") == "curated_contract_fixture"
            and source.get("upstream_artifact_availability") == "not_provided"
            and source.get("live_runtime_replayed") is False
            and source.get("raw_runtime_bundle_checked_in") is False
            and bool(limitations)
            and bool(supported_claims)
            and bool(unsupported_claims)
        )
        summary.update(
            {
                "status": (
                    "verified"
                    if path_matches and hash_matches and manifest_contract_complete
                    else "invalid"
                ),
                "fixture_sha256_expected": expected_hash or None,
                "fixture_sha256_actual": actual_hash,
                "fixture_sha256_matches": hash_matches,
                "fixture_hash_normalization": hash_normalization or None,
                "fixture_path_matches": path_matches,
                "evidence_kind": source.get("evidence_kind"),
                "upstream_artifact_availability": source.get(
                    "upstream_artifact_availability"
                ),
                "live_runtime_replayed": source.get("live_runtime_replayed"),
                "raw_runtime_bundle_checked_in": source.get(
                    "raw_runtime_bundle_checked_in"
                ),
                "limitations": limitations,
                "claim_boundary": {
                    "supports": supported_claims,
                    "does_not_support": unsupported_claims,
                },
            }
        )
    except (OSError, TypeError, ValueError) as exc:
        summary["error"] = str(exc)
    return summary


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _display_values(surface: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for key in ("rendered_value", "formatted_value", "display"):
        value = str(surface.get(key) or "").strip()
        if value and value not in values:
            values.append(value)
    answer_slots = dict(surface.get("answer_slots") or {})
    primary_value = dict(answer_slots.get("primary_value") or {})
    for key in ("rendered_value", "formatted_value", "display"):
        value = str(primary_value.get(key) or "").strip()
        if value and value not in values:
            values.append(value)
    return values


def _answer_display_agreement(answer_package: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
    structured_result = dict(answer_package.get("structured_result") or {})
    trace = dict(answer_package.get("resolved_calculation_trace") or {})
    calculation_result = dict(trace.get("calculation_result") or {})
    structured_displays = _display_values(structured_result)
    trace_displays = _display_values(calculation_result)
    normalized = {
        _normalize_text(item) for item in structured_displays + trace_displays if item
    }
    answer = _normalize_text(answer_package.get("answer"))
    display = next(iter(normalized), "") if len(normalized) == 1 else ""
    consistent = bool(structured_displays and trace_displays and display)
    consistent = consistent and display in answer
    return consistent, {
        "structured_displays": structured_displays,
        "trace_displays": trace_displays,
        "agreed_display": (
            structured_displays[0] if consistent and structured_displays else None
        ),
        "answer_contains_display": bool(display and display in answer),
    }


def _semantic_operand_label_agreement(
    answer_package: Dict[str, Any],
) -> tuple[bool, Dict[str, Any]]:
    semantic_plan = dict(answer_package.get("semantic_plan") or {})
    semantic_task = _first_mapping(semantic_plan.get("tasks"))
    semantic_operands = _mapping_list(semantic_task.get("required_operands"))
    trace = dict(answer_package.get("resolved_calculation_trace") or {})
    trace_operands = _mapping_list(trace.get("calculation_operands"))
    semantic_labels = [
        _normalize_text(item.get("label"))
        for item in semantic_operands
        if _normalize_text(item.get("label"))
    ]
    trace_labels = [
        _normalize_text(item.get("label"))
        for item in trace_operands
        if _normalize_text(item.get("label"))
    ]
    consistent = bool(semantic_labels and trace_labels) and (
        Counter(semantic_labels) == Counter(trace_labels)
    )
    return consistent, {
        "semantic_labels": semantic_labels,
        "trace_labels": trace_labels,
    }


def _decimal_from_value(value: Any) -> Decimal | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = _NUMERIC_TOKEN_PATTERN.search(text)
    if match is None:
        return None
    try:
        parsed = Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None
    if text.startswith("(") and text.endswith(")") and parsed > 0:
        parsed = -parsed
    return parsed


def _decimal_text(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _ratio_calculation_consistency(
    answer_package: Dict[str, Any],
) -> tuple[bool, Dict[str, Any]]:
    semantic_plan = dict(answer_package.get("semantic_plan") or {})
    semantic_task = _first_mapping(semantic_plan.get("tasks"))
    semantic_operands = _mapping_list(semantic_task.get("required_operands"))
    trace = dict(answer_package.get("resolved_calculation_trace") or {})
    trace_operands = _mapping_list(trace.get("calculation_operands"))
    calculation_plan = dict(trace.get("calculation_plan") or {})
    calculation_result = dict(trace.get("calculation_result") or {})
    details: Dict[str, Any] = {
        "semantic_operation": semantic_task.get("operation_family"),
        "trace_operation": calculation_plan.get("operation"),
        "computed_ratio": None,
        "result_raw_value": None,
        "result_rendered_value": None,
        "reasons": [],
    }
    semantic_operation = _normalize_text(semantic_task.get("operation_family"))
    trace_operation = _normalize_text(calculation_plan.get("operation"))
    if semantic_operation != "ratio" or trace_operation != "ratio":
        details["reasons"].append("ratio_operation_not_declared_consistently")
        return False, details

    role_labels = {
        _normalize_text(item.get("role")): _normalize_text(item.get("label"))
        for item in semantic_operands
        if _normalize_text(item.get("role")) and _normalize_text(item.get("label"))
    }
    operands_by_label = {
        _normalize_text(item.get("label")): item
        for item in trace_operands
        if _normalize_text(item.get("label"))
    }
    numerator = _decimal_from_value(
        dict(operands_by_label.get(role_labels.get("numerator"), {}) or {}).get(
            "raw_value"
        )
    )
    denominator = _decimal_from_value(
        dict(operands_by_label.get(role_labels.get("denominator"), {}) or {}).get(
            "raw_value"
        )
    )
    if numerator is None or denominator is None:
        details["reasons"].append("ratio_operand_value_missing")
        return False, details
    if denominator == 0:
        details["reasons"].append("ratio_denominator_zero")
        return False, details

    computed_ratio = numerator / denominator
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    primary_value = dict(answer_slots.get("primary_value") or {})
    result_raw_source = primary_value.get("raw_value")
    if result_raw_source is None:
        result_raw_source = calculation_result.get("raw_value")
    result_raw = _decimal_from_value(result_raw_source)
    rendered_values = _display_values(calculation_result)
    rendered = rendered_values[0] if rendered_values else ""
    rendered_numeric = _decimal_from_value(rendered)
    details.update(
        {
            "computed_ratio": _decimal_text(computed_ratio),
            "result_raw_value": _decimal_text(result_raw),
            "result_rendered_value": rendered or None,
        }
    )
    if result_raw is None:
        details["reasons"].append("ratio_result_raw_value_missing")
    if rendered_numeric is None or "%" not in rendered:
        details["reasons"].append("ratio_rendered_percentage_missing")
    if details["reasons"]:
        return False, details

    raw_precision = max(0, -result_raw.as_tuple().exponent)
    raw_quantum = Decimal(1).scaleb(-raw_precision)
    expected_raw = computed_ratio.quantize(raw_quantum, rounding=ROUND_HALF_UP)
    raw_consistent = result_raw == expected_raw

    rendered_token = _NUMERIC_TOKEN_PATTERN.search(rendered)
    rendered_token_text = rendered_token.group(0).replace(",", "")
    rendered_precision = (
        len(rendered_token_text.split(".", 1)[1])
        if "." in rendered_token_text
        else 0
    )
    rendered_quantum = Decimal(1).scaleb(-rendered_precision)
    expected_percentage = (computed_ratio * 100).quantize(
        rendered_quantum,
        rounding=ROUND_HALF_UP,
    )
    rendered_consistent = rendered_numeric == expected_percentage
    if not raw_consistent:
        details["reasons"].append("ratio_raw_value_mismatch")
    if not rendered_consistent:
        details["reasons"].append("ratio_rendered_value_mismatch")
    return raw_consistent and rendered_consistent, details


def _source_evidence_citation_coherence(
    answer_package: Dict[str, Any],
) -> tuple[bool, Dict[str, Any]]:
    citations = [
        _normalize_text(item)
        for item in list(answer_package.get("citations") or [])
        if _normalize_text(item)
    ]
    evidence_items = _mapping_list(answer_package.get("evidence_items"))
    trace = dict(answer_package.get("resolved_calculation_trace") or {})
    operands = _mapping_list(trace.get("calculation_operands"))
    retrieval_trace = dict(answer_package.get("retrieval_debug_trace") or {})
    selected_chunks = _mapping_list(retrieval_trace.get("selected_chunks"))

    def evidence_matches_operand(evidence: Dict[str, Any], operand: Dict[str, Any]) -> bool:
        evidence_anchor = _normalize_text(evidence.get("source_anchor"))
        operand_anchor = _normalize_text(operand.get("source_anchor"))
        evidence_row = _normalize_text(dict(evidence.get("metadata") or {}).get("source_row_id"))
        operand_row = _normalize_text(operand.get("source_row_id"))
        return bool(
            (evidence_anchor and evidence_anchor == operand_anchor)
            or (evidence_row and evidence_row == operand_row)
        )

    def evidence_matches_selected(evidence: Dict[str, Any]) -> bool:
        evidence_anchor = _normalize_text(evidence.get("source_anchor"))
        evidence_row = _normalize_text(dict(evidence.get("metadata") or {}).get("source_row_id"))
        for selected in selected_chunks:
            selected_anchor = _normalize_text(selected.get("source_anchor"))
            section_path = _normalize_text(selected.get("section_path"))
            chunk_uid = _normalize_text(selected.get("chunk_uid"))
            if selected_anchor and selected_anchor == evidence_anchor:
                return True
            if section_path and (
                evidence_anchor == section_path
                or evidence_anchor.startswith(f"{section_path}::")
            ):
                return True
            if evidence_row and evidence_row == chunk_uid:
                return True
        return False

    operands_backed = bool(operands) and all(
        any(evidence_matches_operand(evidence, operand) for evidence in evidence_items)
        for operand in operands
    )
    evidence_anchors = [
        _normalize_text(evidence.get("source_anchor")) for evidence in evidence_items
    ]
    evidence_cited = bool(evidence_anchors and citations)
    evidence_cited = evidence_cited and all(evidence_anchors)
    evidence_cited = evidence_cited and all(
        any(evidence_anchor in citation for citation in citations)
        for evidence_anchor in evidence_anchors
    )
    evidence_selected = bool(evidence_items and selected_chunks) and all(
        evidence_matches_selected(evidence) for evidence in evidence_items
    )
    coherent = operands_backed and evidence_cited and evidence_selected
    return coherent, {
        "operand_count": len(operands),
        "evidence_count": len(evidence_items),
        "citation_count": len(citations),
        "selected_chunk_count": len(selected_chunks),
        "operands_backed_by_evidence": operands_backed,
        "evidence_anchors_cited": evidence_cited,
        "evidence_backed_by_selected_source": evidence_selected,
    }


def _summarize_task_artifact_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    tasks = _mapping_list(trace.get("tasks"))
    artifacts = _mapping_list(trace.get("artifacts"))
    task_ids = sorted(
        {
            str(task.get("task_id") or "").strip()
            for task in tasks
            if str(task.get("task_id") or "").strip()
        }
    )
    artifact_ids = {
        str(artifact.get("artifact_id") or "").strip()
        for artifact in artifacts
        if str(artifact.get("artifact_id") or "").strip()
    }
    for task in tasks:
        artifact_ids.update(
            str(item).strip()
            for item in list(task.get("artifact_ids") or [])
            if str(item).strip()
        )
        latest_artifact_id = str(task.get("latest_artifact_id") or "").strip()
        if latest_artifact_id:
            artifact_ids.add(latest_artifact_id)
    return {
        "integrity_status": trace.get("integrity_status"),
        "integrity_issue_count": int(trace.get("integrity_issue_count") or 0),
        "task_count": int(trace.get("task_count") or 0),
        "artifact_count": int(trace.get("artifact_count") or 0),
        "missing_artifact_ids": list(trace.get("missing_artifact_ids") or []),
        "orphan_artifact_ids": list(trace.get("orphan_artifact_ids") or []),
        "integrity_issues": list(trace.get("integrity_issues") or []),
        "task_ids": task_ids,
        "artifact_ids": sorted(artifact_ids),
    }


def _summarize_critic_acceptance(report: Dict[str, Any]) -> Dict[str, Any]:
    acceptance = critic_report_runtime_acceptance_state(dict(report))
    blocking_issues = list(report.get("blocking_issues") or [])
    target_artifact_ids = list(report.get("target_artifact_ids") or [])
    return {
        "status": acceptance.get("runtime_acceptance_status"),
        "verdict": report.get("verdict"),
        "target_task_id": report.get("target_task_id"),
        "target_artifact_ids": target_artifact_ids,
        "target_refs": list(acceptance.get("target_refs") or []),
        "acceptance_reason": str(report.get("acceptance_reason") or ""),
        "blocking_issues": blocking_issues,
        "runtime_acceptance_reasons": list(acceptance.get("reasons") or []),
        "deterministic_score": acceptance.get("deterministic_score"),
        "deterministic_score_used_for_acceptance": bool(
            acceptance.get("deterministic_score_used_for_acceptance")
        ),
    }


def _critic_target_references_exist(
    *,
    task_artifact: Dict[str, Any],
    critic_acceptance: Dict[str, Any],
) -> tuple[bool, Dict[str, Any]]:
    known_task_ids = {
        str(item).strip()
        for item in task_artifact.get("task_ids") or []
        if str(item).strip()
    }
    known_artifact_ids = {
        str(item).strip()
        for item in task_artifact.get("artifact_ids") or []
        if str(item).strip()
    }
    target_task_id = str(critic_acceptance.get("target_task_id") or "").strip()
    target_artifact_ids = {
        str(item).strip()
        for item in critic_acceptance.get("target_artifact_ids") or []
        if str(item).strip()
    }
    missing_task_ids = (
        [target_task_id]
        if target_task_id and target_task_id not in known_task_ids
        else []
    )
    missing_artifact_ids = sorted(target_artifact_ids - known_artifact_ids)
    references_exist = bool(target_task_id and target_artifact_ids)
    references_exist = (
        references_exist and not missing_task_ids and not missing_artifact_ids
    )
    return references_exist, {
        "known_task_ids": sorted(known_task_ids),
        "known_artifact_ids": sorted(known_artifact_ids),
        "target_task_id": target_task_id or None,
        "target_artifact_ids": sorted(target_artifact_ids),
        "missing_target_task_ids": missing_task_ids,
        "missing_target_artifact_ids": missing_artifact_ids,
    }


def _checks(
    *,
    answer_package: Dict[str, Any],
    task_artifact: Dict[str, Any],
    critic_acceptance: Dict[str, Any],
    evidence_manifest: Dict[str, Any],
) -> Dict[str, Any]:
    semantic_plan = dict(answer_package.get("semantic_plan") or {})
    retrieval_trace = dict(answer_package.get("retrieval_debug_trace") or {})
    trace = dict(answer_package.get("resolved_calculation_trace") or {})
    calculation_result = dict(trace.get("calculation_result") or {})
    display_agreement, display_details = _answer_display_agreement(answer_package)
    operand_label_agreement, operand_label_details = (
        _semantic_operand_label_agreement(answer_package)
    )
    ratio_consistency, ratio_details = _ratio_calculation_consistency(answer_package)
    source_coherence, source_details = _source_evidence_citation_coherence(
        answer_package
    )
    critic_targets_exist, critic_target_details = _critic_target_references_exist(
        task_artifact=task_artifact,
        critic_acceptance=critic_acceptance,
    )
    checks = {
        "fixture_evidence_manifest_verified": evidence_manifest.get("status")
        == "verified",
        "answer_present": bool(str(answer_package.get("answer") or "").strip()),
        "citations_present": bool(answer_package.get("citations") or []),
        "semantic_plan_present": bool(semantic_plan.get("tasks") or []),
        "retrieval_trace_present": bool(retrieval_trace.get("query_bundle") or [])
        and int(retrieval_trace.get("selected_count") or 0) > 0,
        "calculation_trace_ok": calculation_result.get("status") == "ok",
        "ratio_calculation_consistent": ratio_consistency,
        "answer_structured_trace_display_agree": display_agreement,
        "semantic_operand_labels_match_trace": operand_label_agreement,
        "source_evidence_citation_coherent": source_coherence,
        "task_artifact_integrity_ok": task_artifact.get("integrity_status") == "ok",
        "critic_accepted": critic_acceptance.get("status") == "accepted",
        "critic_targets_exist": critic_targets_exist,
    }
    return {
        "status": (
            "fixture_contract_ready" if all(checks.values()) else "needs_review"
        ),
        "scope": "fixture_contract",
        "checks": checks,
        "details": {
            "ratio_calculation_consistency": ratio_details,
            "answer_display_agreement": display_details,
            "semantic_operand_label_agreement": operand_label_details,
            "source_evidence_citation_coherence": source_details,
            "critic_target_references": critic_target_details,
        },
    }


def evaluate_fixture_contract(
    *,
    answer_package: Dict[str, Any],
    manifest_path: Path,
    payload_path: Path,
) -> Dict[str, Any]:
    """Return the evidence, integrity, critic, and readiness projections."""
    evidence_manifest = _summarize_evidence_manifest(
        manifest_path=manifest_path,
        payload_path=payload_path,
    )
    task_artifact = _summarize_task_artifact_trace(
        dict(answer_package.get("task_artifact_trace") or {})
    )
    critic_acceptance = _summarize_critic_acceptance(
        _first_mapping(answer_package.get("critic_reports"))
    )
    return {
        "fixture_evidence": evidence_manifest,
        "task_artifact_integrity": task_artifact,
        "critic_acceptance": critic_acceptance,
        "readiness": _checks(
            answer_package=answer_package,
            task_artifact=task_artifact,
            critic_acceptance=critic_acceptance,
            evidence_manifest=evidence_manifest,
        ),
    }
