"""Task/artifact ledger contract helpers.

This module owns artifact payload integrity rules so the graph helper module can
focus on runtime trace assembly and projection.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, TypedDict

from src.schema.runtime_enums import ArtifactKind, TaskKind


class CriticRuntimeAcceptance(TypedDict):
    accepted: bool
    runtime_acceptance_status: str
    reasons: List[str]
    target_refs: List[str]
    deterministic_score: float
    deterministic_score_used_for_acceptance: bool

REQUIRED_ARTIFACT_KINDS_BY_TASK_KIND = {
    TaskKind.CALCULATION.value: {
        ArtifactKind.OPERAND_SET.value,
        ArtifactKind.CALCULATION_PLAN.value,
        ArtifactKind.CALCULATION_RESULT.value,
    },
    TaskKind.RECONCILIATION.value: {
        ArtifactKind.RECONCILIATION_RESULT.value,
    },
    TaskKind.REFLECTION.value: {
        ArtifactKind.REFLECTION_REPORT.value,
    },
    TaskKind.RETRIEVAL.value: {
        ArtifactKind.RETRIEVAL_BUNDLE.value,
    },
    TaskKind.SYNTHESIS.value: {
        ArtifactKind.AGGREGATED_ANSWER.value,
    },
    TaskKind.CRITIC.value: {
        ArtifactKind.CRITIC_REPORT.value,
    },
}

ARTIFACT_PROVENANCE_KEYS = {
    "evidence_ref",
    "evidence_refs",
    "evidence_id",
    "evidence_ids",
    "source_evidence_id",
    "source_evidence_ids",
    "source_row_id",
    "source_row_ids",
    "row_id",
    "row_ids",
    "candidate_id",
    "candidate_ids",
    "chunk_id",
    "chunk_ids",
    "doc_id",
    "doc_ids",
    "source_anchor",
    "source_anchors",
    "source_artifact_id",
    "source_artifact_ids",
    "source_task_id",
    "source_task_ids",
    "target_artifact_id",
    "target_artifact_ids",
    "target_task_id",
    "target_task_ids",
    "checked_artifact_id",
    "checked_artifact_ids",
    "checked_task_id",
    "checked_task_ids",
}


def payload_missing_contract(artifact_kind: str, payload: Mapping[str, Any]) -> str:
    if artifact_kind == ArtifactKind.OPERAND_SET.value:
        operands = payload.get("calculation_operands")
        if not isinstance(operands, list) or not operands:
            return "calculation_operands"
    elif artifact_kind == ArtifactKind.CALCULATION_PLAN.value:
        plan = payload.get("calculation_plan")
        if not isinstance(plan, Mapping):
            return "calculation_plan"
        if not str(plan.get("operation") or plan.get("mode") or "").strip():
            return "calculation_plan.operation"
    elif artifact_kind == ArtifactKind.CALCULATION_RESULT.value:
        result = payload.get("calculation_result")
        if not isinstance(result, Mapping):
            return "calculation_result"
        answer_slots = result.get("answer_slots")
        has_answer_slots = isinstance(answer_slots, Mapping) and bool(answer_slots)
        has_rendered = bool(str(result.get("rendered_value") or result.get("formatted_result") or "").strip())
        if not has_rendered and not has_answer_slots:
            return "calculation_result.rendered_value_or_answer_slots"
    elif artifact_kind == ArtifactKind.RECONCILIATION_RESULT.value:
        result = payload.get("reconciliation_result")
        if not isinstance(result, Mapping):
            return "reconciliation_result"
        if not str(result.get("status") or "").strip():
            return "reconciliation_result.status"
    elif artifact_kind == ArtifactKind.REFLECTION_REPORT.value:
        return _missing_reflection_report_payload_contract(payload)
    elif artifact_kind == ArtifactKind.RETRIEVAL_BUNDLE.value:
        return _missing_retrieval_bundle_payload_contract(payload)
    elif artifact_kind == ArtifactKind.AGGREGATED_ANSWER.value:
        return _missing_aggregated_answer_payload_contract(payload)
    elif artifact_kind == ArtifactKind.CRITIC_REPORT.value:
        return _missing_critic_report_payload_contract(payload)
    return ""


def _missing_reflection_report_payload_contract(payload: Mapping[str, Any]) -> str:
    report = payload.get("reflection_report")
    if not isinstance(report, Mapping):
        return "reflection_report"
    action_taken = str(report.get("action_taken") or "").strip()
    if not str(report.get("outcome") or "").strip():
        return "reflection_report.outcome"
    if not action_taken:
        return "reflection_report.action_taken"
    if "budget_consumed" not in report:
        return "reflection_report.budget_consumed"
    action = payload.get("reflection_action")
    if action_taken in {"retry_retrieval", "synthesize_from_task_outputs"}:
        if not isinstance(action, Mapping):
            return "reflection_action"
        action_type = str(action.get("action_type") or "").strip()
        if action_type != action_taken:
            return "reflection_action.action_type"
    if action_taken == "retry_retrieval":
        retry_queries = action.get("retry_queries") if isinstance(action, Mapping) else []
        if not isinstance(retry_queries, list) or not any(str(item).strip() for item in retry_queries):
            return "reflection_action.retry_queries"
    elif action_taken == "synthesize_from_task_outputs":
        synthesis_source_ids = action.get("synthesis_source_ids") if isinstance(action, Mapping) else []
        if not isinstance(synthesis_source_ids, list) or not any(str(item).strip() for item in synthesis_source_ids):
            return "reflection_action.synthesis_source_ids"
    return ""


def _missing_retrieval_bundle_payload_contract(payload: Mapping[str, Any]) -> str:
    bundle = payload.get("retrieval_bundle") if isinstance(payload.get("retrieval_bundle"), Mapping) else {}
    candidate_lists = [
        payload.get("retrieved_docs"),
        payload.get("seed_retrieved_docs"),
        payload.get("evidence_items"),
        payload.get("documents"),
        bundle.get("retrieved_docs"),
        bundle.get("seed_retrieved_docs"),
        bundle.get("evidence_items"),
        bundle.get("documents"),
    ]
    if not any(isinstance(items, list) and bool(items) for items in candidate_lists):
        return "retrieval_bundle.items"
    return ""


def _missing_aggregated_answer_payload_contract(payload: Mapping[str, Any]) -> str:
    final_answer = str(payload.get("final_answer") or payload.get("answer") or "").strip()
    if not final_answer:
        return "aggregated_answer.final_answer"
    source_lists = [
        payload.get("subtask_results"),
        payload.get("source_artifact_ids"),
        payload.get("source_task_ids"),
    ]
    source_maps = [
        payload.get("resolved_calculation_trace"),
        payload.get("structured_result"),
        payload.get("calculation_result"),
    ]
    has_source_list = any(isinstance(items, list) and bool(items) for items in source_lists)
    has_source_map = any(isinstance(item, Mapping) and bool(item) for item in source_maps)
    if not has_source_list and not has_source_map:
        return "aggregated_answer.source_material"
    return ""


def _missing_critic_report_payload_contract(payload: Mapping[str, Any]) -> str:
    report = payload.get("critic_report") if isinstance(payload.get("critic_report"), Mapping) else payload
    acceptance_state = critic_report_acceptance_state(dict(report))
    reasons = set(acceptance_state.get("reasons") or [])
    if (
        "missing_verdict" in reasons
        or "unknown_verdict" in reasons
        or "conflicting_verdict_signal" in reasons
    ):
        return "critic_report.verdict"
    if "missing_target_refs" in reasons:
        return "critic_report.target_refs"
    if "missing_acceptance_reason" in reasons or "missing_blocking_issues" in reasons:
        return "critic_report.acceptance_reason_or_issues"
    return ""


def _dedupe_strings(values: List[str]) -> List[str]:
    seen: set[str] = set()
    normalized: List[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _list_strings(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _critic_verdict_signal(report: Mapping[str, Any]) -> tuple[str, bool]:
    has_passed_value = isinstance(report.get("passed"), bool)
    bool_signal = "passed" if bool(report.get("passed")) else "rejected" if has_passed_value else ""
    text_signal = str(report.get("verdict") or report.get("status") or "").strip().lower()
    if text_signal in {"passed", "accepted", "ok", "success"}:
        text_signal = "passed"
    elif text_signal in {"rejected", "blocked", "failed", "error"}:
        text_signal = "rejected"
    elif text_signal:
        text_signal = "unknown"
    if bool_signal and text_signal and bool_signal != text_signal:
        return bool_signal, True
    return bool_signal or text_signal, False


def critic_report_runtime_acceptance_state(report: Mapping[str, Any]) -> CriticRuntimeAcceptance:
    verdict, conflicting_verdict_signal = _critic_verdict_signal(report)
    passed = verdict == "passed"
    target_refs = _dedupe_strings(
        [
            str(report.get("target_task_id") or "").strip(),
            str(report.get("target_artifact_id") or "").strip(),
            *_list_strings(report.get("target_task_ids")),
            *_list_strings(report.get("target_artifact_ids")),
            *_list_strings(report.get("checked_task_ids")),
            *_list_strings(report.get("checked_artifact_ids")),
            *_list_strings(report.get("source_task_ids")),
            *_list_strings(report.get("source_artifact_ids")),
        ]
    )
    acceptance_reason = str(
        report.get("acceptance_reason")
        or report.get("rationale")
        or report.get("feedback")
        or report.get("llm_feedback")
        or ""
    ).strip()
    blocking_issues = _dedupe_strings(
        [
            *_list_strings(report.get("blocking_issues")),
            *_list_strings(report.get("issues")),
            *_list_strings(report.get("findings")),
        ]
    )
    reasons: List[str] = []
    if not verdict:
        reasons.append("missing_verdict")
    elif verdict == "unknown":
        reasons.append("unknown_verdict")
    if conflicting_verdict_signal:
        reasons.append("conflicting_verdict_signal")
    if not target_refs:
        reasons.append("missing_target_refs")
    if passed:
        if not acceptance_reason:
            reasons.append("missing_acceptance_reason")
        if blocking_issues:
            reasons.append("passed_report_has_blocking_issues")
    else:
        if verdict == "rejected":
            reasons.append("critic_rejected")
        if verdict == "rejected" and not blocking_issues:
            reasons.append("missing_blocking_issues")

    accepted = passed and not reasons
    return {
        "accepted": accepted,
        "runtime_acceptance_status": "accepted" if accepted else "blocked",
        "reasons": _dedupe_strings(reasons),
        "target_refs": target_refs,
        "deterministic_score": float(report.get("deterministic_score") or 0.0),
        "deterministic_score_used_for_acceptance": False,
    }


def critic_report_acceptance_state(report: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(critic_report_runtime_acceptance_state(report))


def reconciliation_result_status(artifacts_for_task: Sequence[Mapping[str, Any]]) -> str:
    for artifact in artifacts_for_task:
        if str(artifact.get("kind") or "").strip() != ArtifactKind.RECONCILIATION_RESULT.value:
            continue
        payload = artifact.get("payload") if isinstance(artifact.get("payload"), Mapping) else {}
        result = payload.get("reconciliation_result") if isinstance(payload, Mapping) else {}
        if isinstance(result, Mapping):
            return str(result.get("status") or "").strip().lower()
    return ""


def payload_has_provenance(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).strip() in ARTIFACT_PROVENANCE_KEYS:
                if isinstance(nested, list):
                    if any(str(item).strip() for item in nested):
                        return True
                elif isinstance(nested, Mapping):
                    if nested:
                        return True
                elif str(nested).strip():
                    return True
            if payload_has_provenance(nested):
                return True
    elif isinstance(value, list):
        for nested in value:
            if payload_has_provenance(nested):
                return True
    return False
