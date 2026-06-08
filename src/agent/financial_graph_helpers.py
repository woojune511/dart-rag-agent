"""
Shared helper functions for the financial graph agent.

The helpers in this file are intentionally grouped by responsibility so the
reader can scan them in chunks:
1. text and ledger utilities
2. numeric parsing / normalization
3. semantic numeric planning helpers
4. reconciliation and operand matching helpers
5. retrieval hint helpers

`financial_graph.py` and the mixin modules import these helpers rather than
re-implementing small pieces of logic in each phase module.
"""

import ast
from functools import lru_cache
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

from src.config import get_financial_ontology
from src.config.report_scoped_cache import (
    classify_report_cache_candidate,
    classify_report_cache_consumer_candidate,
    report_cache_key_id,
)
from src.config.retrieval_policy import (
    CONSOLIDATION_SCOPE_POLICY,
    CONCEPT_RATIO_RESULT_UNIT_POLICY,
    EXPLICIT_RATIO_DEFINITION_POLICY,
    FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES,
    FINANCIAL_NUMERIC_STATEMENT_HINT_POLICIES,
    FINANCIAL_SEGMENT_SECTION_HINT_POLICY,
    CONCEPT_METRIC_LABEL_POLICY,
    GENERIC_METRIC_ALIAS_SUBSTITUTIONS,
    GENERIC_OPERAND_LABEL_POLICY,
    GENERIC_PERIOD_OPERAND_POLICY,
    GENERIC_UNIT_FAMILY_POLICY,
    HELPER_RUNTIME_POLICY,
    KOREAN_WON_COMPACT_FORMAT_POLICY,
    KOREAN_COUNT_SCALE_PREFIXES,
    KOREAN_COUNT_UNIT_RE_FRAGMENT,
    KOREAN_COUNT_UNITS,
    KOREAN_PERCENT_METRIC_HINT_TERMS,
    KOREAN_PERIOD_COMPARISON_RE_FRAGMENT,
    KOREAN_PERIOD_PREFIX_RE_FRAGMENT,
    KOREAN_PERIOD_RATE_METRIC_SUFFIX_RE_FRAGMENT,
    KOREAN_SEGMENT_LABEL_ANCHORS,
    KOREAN_SEGMENT_LABEL_BLOCKED_EXACT_LABELS,
    KOREAN_SEGMENT_LABEL_BLOCKED_TOKENS,
    KOREAN_SEGMENT_LABEL_BOUNDARIES,
    KOREAN_SEGMENT_LABEL_MARKERS,
    KOREAN_SEGMENT_LABEL_PAREN_RE_FRAGMENT,
    KOREAN_SEGMENT_LABEL_PERIOD_PREFIX_RE_FRAGMENT,
    KOREAN_SEGMENT_LABEL_PERIOD_RE_FRAGMENT,
    KOREAN_SEGMENT_LABEL_REPORT_TERMS,
    KOREAN_SEGMENT_LABEL_SCOPE_TOKENS,
    KOREAN_SEGMENT_LABEL_SPLIT_RE_FRAGMENT,
    KOREAN_SEGMENT_LABEL_TOKEN_PATTERNS,
    KOREAN_SEGMENT_LABEL_TRAILING_PERIOD_RE_FRAGMENT,
    METRIC_TOPIC_EXTRACTION_TERMS,
    METRIC_TASK_QUERY_POLICY,
    NUMERIC_UNIT_NORMALIZATION_POLICY,
    OPERATION_FAMILY_QUERY_POLICIES,
    OPERAND_CANDIDATE_SCORING_POLICY,
    PERIOD_FOCUS_POLICY,
    PERCENT_POINT_DIFFERENCE_POLICY,
    RATIO_PERCENT_QUERY_POLICY,
    STRUCTURED_CELL_AFFINITY_POLICY,
    STRUCTURED_CELL_PERIOD_SCORING_POLICY,
    TASK_CONSTRAINT_POLICY,
    VALUE_NEAR_MATCH_POLICY,
    active_numeric_section_hint_policies,
    active_narrative_policies,
    narrative_policy_preferred_sections,
    narrative_policy_terms,
    numeric_section_policy_preferred_sections,
    numeric_section_policy_statement_types,
)
from src.agent.mas_types import critic_report_runtime_acceptance_state
from src.agent.financial_graph_models import RuntimeCalculationTrace, validate_answer_slots_payload
from src.schema import ArtifactKind, ArtifactRecord, TaskKind, TaskRecord, TaskStatus

__all__ = [
    '_tokenize_terms',
    '_normalise_spaces',
    '_split_sentences',
    '_strip_anchor_text',
    '_clean_source_row_ids',
    '_section_hint_alias',
    '_append_artifact',
    '_upsert_task',
    '_project_task_artifact_trace',
    '_extract_artifact_payload_value',
    '_find_task_record_in_list',
    '_latest_artifact_value_for_task_records',
    '_project_task_trace_from_runtime',
    '_project_task_trace_from_state',
    '_build_aggregate_calculation_projection',
    '_resolve_runtime_calculation_trace',
    '_build_runtime_calculation_trace',
    '_runtime_trace_state_update',
    '_candidate_row_block_signature',
    '_resolve_candidate_local_unit_hint',
    '_parse_number_text',
    '_safe_eval_formula',
    '_extract_composite_krw',
    '_normalise_operand_value',
    '_coerce_lookup_magnitude_record',
    '_extract_period_sort_key',
    '_format_korean_won_compact',
    '_display_operand_label',
    '_strip_rerank_metadata',
    '_metric_terms_from_topic',
    '_is_ratio_percent_query',
    '_desired_statement_types',
    '_desired_consolidation_scope',
    '_metadata_period_match_strength',
    '_prioritize_candidate_items',
    '_should_apply_strict_company_scope',
    '_query_mentions_metric',
    '_clean_metric_label',
    '_extract_quoted_metric_labels',
    '_extract_generic_operand_labels',
    '_label_implies_percent_metric',
    '_is_single_metric_period_comparison',
    '_query_requests_narrative_context',
    '_requires_direct_numeric_grounding',
    '_extract_year_tokens',
    '_build_generic_metric_aliases',
    '_infer_statement_and_section_hints',
    '_build_generic_required_operands',
    '_infer_generic_metric_label',
    '_infer_generic_concept_spec',
    '_build_generic_retrieval_queries',
    '_planner_intent_cues',
    '_infer_operation_family_from_query',
    '_build_concept_required_operands',
    '_build_concept_metric_label',
    '_build_concept_task_constraints',
    '_build_heuristic_numeric_task',
    '_infer_period_focus',
    '_build_task_constraints',
    '_build_retrieval_query_bundle',
    '_build_metric_task_query',
    '_annotate_task_dependencies',
    '_build_semantic_numeric_plan',
    '_build_reconciliation_candidate',
    '_query_years_from_state',
    '_structured_cell_period_text',
    '_select_structured_cell',
    '_operand_target_years',
    '_operand_period_focus',
    '_score_structured_cell',
    '_operand_needles',
    '_text_has_positive_surface',
    '_text_has_negative_surface',
    '_operand_text_match',
    '_extract_numeric_value_after_operand_text',
    '_operand_row_matches_requirement',
    '_missing_required_operands',
    '_merge_operand_rows',
    '_extract_table_row_label',
    '_parse_unstructured_table_row_cells',
    '_build_table_value_reconciliation_candidates',
    '_build_table_row_reconciliation_candidates',
    '_candidate_has_numeric_value_signal',
    '_candidate_is_descriptor_row',
    '_candidate_is_direct_grounding_candidate',
    '_candidate_satisfies_direct_acceptance_contract',
    '_is_balance_sheet_aggregate_operand',
    '_candidate_matches_operand',
    '_score_operand_candidate',
    '_build_reconciliation_retry_queries',
    '_deterministic_reconcile_task',
    '_preferred_calc_sections',
    '_is_percent_point_difference_query',
    '_should_coerce_percent_point_unit',
    '_extract_value_near_match',
    '_supplement_section_terms_for_query',
    '_active_preferred_sections',
    '_active_preferred_statement_types',
    '_retrieval_hint_from_topic'
]

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_REPORT_ROOT = _PROJECT_ROOT / "data" / "reports"
_UNIT_HINT_HTML_PATTERN = re.compile(r"\(\s*단위\s*:\s*([^)]+?)\s*\)")

# ---------------------------------------------------------------------------
# Text and ledger utilities
# ---------------------------------------------------------------------------

def _tokenize_terms(text: str) -> set[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", text or "")
    return {token.lower() for token in tokens if len(token) >= 2}


def _normalise_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _clean_source_row_ids(values: Sequence[Any]) -> List[str]:
    blocked = {"none", "null", "nan"}
    cleaned: List[str] = []

    def _append(value: Any) -> None:
        if isinstance(value, (list, tuple, set)):
            for item in value:
                _append(item)
            return
        text = str(value).strip()
        if not text or text.lower() in blocked:
            return
        cleaned.append(text)

    for value in values or []:
        _append(value)
    return list(dict.fromkeys(cleaned))


def _extract_source_evidence_ids_from_records(records: Sequence[Any]) -> List[str]:
    values: List[Any] = []
    for record in records or []:
        if not isinstance(record, Mapping):
            continue
        values.extend(
            [
                record.get("evidence_id"),
                record.get("source_evidence_id"),
                record.get("source_evidence_ids"),
            ]
        )
    return _clean_source_row_ids(values)


def _extract_subtask_source_evidence_ids(
    row: Mapping[str, Any],
    calculation_result: Mapping[str, Any],
    answer_slots: Mapping[str, Any],
    source_row_ids: Sequence[Any],
) -> List[str]:
    values: List[Any] = [
        row.get("evidence_id"),
        row.get("evidence_ids"),
        row.get("source_evidence_id"),
        row.get("source_evidence_ids"),
        calculation_result.get("evidence_id"),
        calculation_result.get("evidence_ids"),
        calculation_result.get("source_evidence_id"),
        calculation_result.get("source_evidence_ids"),
        answer_slots.get("evidence_id"),
        answer_slots.get("evidence_ids"),
        answer_slots.get("source_evidence_id"),
        answer_slots.get("source_evidence_ids"),
    ]
    if not _clean_source_row_ids(source_row_ids):
        values.extend(
            [
                _extract_source_evidence_ids_from_records(row.get("runtime_evidence") or []),
                _extract_source_evidence_ids_from_records(row.get("evidence_items") or []),
                _extract_source_evidence_ids_from_records(calculation_result.get("runtime_evidence") or []),
                _extract_source_evidence_ids_from_records(calculation_result.get("evidence_items") or []),
            ]
        )
    return _clean_source_row_ids(values)


def _operand_row_has_material_numeric_payload(row: Mapping[str, Any]) -> bool:
    status = _normalise_spaces(str(row.get("status") or "")).lower()
    if status == "missing":
        return False
    raw_unit = _normalise_spaces(str(row.get("raw_unit") or row.get("unit") or ""))
    normalized_unit = _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
    raw_value = _normalise_spaces(
        str(
            row.get("raw_value")
            or row.get("value")
            or row.get("rendered_value")
            or row.get("display_value")
            or ""
        )
    )
    raw_digit_count = len(re.findall(r"\d", raw_value))
    if normalized_unit in {"", "UNKNOWN"} and not raw_unit and raw_digit_count < 4:
        return False
    if row.get("normalized_value") is not None:
        return True
    return bool(raw_value)


def _split_sentences(text: str) -> List[str]:
    cleaned = _normalise_spaces(text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+|(?<=다)\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _strip_anchor_text(text: str) -> str:
    cleaned = re.sub(r"\[[^\]]+\]", " ", text or "")
    cleaned = re.sub(r"^[*\-\u2022]+\s*", "", cleaned)
    return _normalise_spaces(cleaned)


def _section_hint_alias(section: str) -> str:
    text = _normalise_spaces(section)
    if not text:
        return ""
    if ">" in text:
        text = text.split(">")[-1].strip()
    text = re.sub(r"^\d+\.\s*", "", text)
    return text


def _append_artifact(
    artifact_list: List[Dict[str, Any]],
    *,
    artifact_id: str,
    task_id: str,
    kind: ArtifactKind,
    status: str = "ok",
    summary: str = "",
    payload: Optional[Dict[str, Any]] = None,
    evidence_refs: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    updated = [dict(item) for item in (artifact_list or [])]
    updated.append(
        ArtifactRecord(
            artifact_id=artifact_id,
            task_id=task_id,
            kind=kind,
            status=status,
            summary=summary,
            payload=dict(payload or {}),
            evidence_refs=[str(value) for value in (evidence_refs or []) if str(value).strip()],
        ).model_dump(mode="json")
    )
    return updated


def _upsert_task(
    task_list: List[Dict[str, Any]],
    *,
    task_id: str,
    kind: TaskKind,
    label: str,
    status: TaskStatus,
    query: str = "",
    metric_family: str = "",
    constraints: Optional[Dict[str, Any]] = None,
    artifact_id: Optional[str] = None,
    notes: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    updated = [dict(item) for item in (task_list or [])]
    for index, item in enumerate(updated):
        if str(item.get("task_id") or "") != task_id:
            continue
        artifact_ids = list(item.get("artifact_ids") or [])
        if artifact_id and artifact_id not in artifact_ids:
            artifact_ids.append(artifact_id)
        updated[index] = TaskRecord(
            task_id=task_id,
            kind=kind,
            label=label,
            status=status,
            query=query or str(item.get("query") or ""),
            metric_family=metric_family or str(item.get("metric_family") or ""),
            constraints=dict(constraints or item.get("constraints") or {}),
            artifact_ids=artifact_ids,
            notes=list(notes or item.get("notes") or []),
        ).model_dump(mode="json")
        return updated

    updated.append(
        TaskRecord(
            task_id=task_id,
            kind=kind,
            label=label,
            status=status,
            query=query,
            metric_family=metric_family,
            constraints=dict(constraints or {}),
            artifact_ids=[artifact_id] if artifact_id else [],
            notes=list(notes or []),
        ).model_dump(mode="json")
    )
    return updated


def _normalise_ledger_records(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, dict):
        raw_items = list(value.values())
    elif isinstance(value, list):
        raw_items = list(value)
    else:
        raw_items = []
    return [dict(item) for item in raw_items if isinstance(item, dict)]


def _project_task_artifact_trace(
    tasks: Any,
    artifacts: Any,
) -> Dict[str, Any]:
    """Return a compact caller-facing projection of the task/artifact ledger."""

    required_artifact_kinds_by_task_kind = {
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
    provenance_keys = {
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

    def _payload_missing_contract(artifact_kind: str, payload: Mapping[str, Any]) -> str:
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
            has_rendered = bool(
                str(result.get("rendered_value") or result.get("formatted_result") or "").strip()
            )
            if not has_rendered and not has_answer_slots:
                return "calculation_result.rendered_value_or_answer_slots"
        elif artifact_kind == ArtifactKind.RECONCILIATION_RESULT.value:
            result = payload.get("reconciliation_result")
            if not isinstance(result, Mapping):
                return "reconciliation_result"
            if not str(result.get("status") or "").strip():
                return "reconciliation_result.status"
        elif artifact_kind == ArtifactKind.REFLECTION_REPORT.value:
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
                if not isinstance(retry_queries, list) or not any(
                    str(item).strip() for item in retry_queries
                ):
                    return "reflection_action.retry_queries"
            elif action_taken == "synthesize_from_task_outputs":
                synthesis_source_ids = (
                    action.get("synthesis_source_ids") if isinstance(action, Mapping) else []
                )
                if not isinstance(synthesis_source_ids, list) or not any(
                    str(item).strip() for item in synthesis_source_ids
                ):
                    return "reflection_action.synthesis_source_ids"
        elif artifact_kind == ArtifactKind.RETRIEVAL_BUNDLE.value:
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
        elif artifact_kind == ArtifactKind.AGGREGATED_ANSWER.value:
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
        elif artifact_kind == ArtifactKind.CRITIC_REPORT.value:
            report = payload.get("critic_report") if isinstance(payload.get("critic_report"), Mapping) else payload
            acceptance_state = critic_report_runtime_acceptance_state(dict(report))
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

    def _reconciliation_result_status(artifacts_for_task: Sequence[Mapping[str, Any]]) -> str:
        for artifact in artifacts_for_task:
            if str(artifact.get("kind") or "").strip() != ArtifactKind.RECONCILIATION_RESULT.value:
                continue
            payload = artifact.get("payload") if isinstance(artifact.get("payload"), Mapping) else {}
            result = payload.get("reconciliation_result") if isinstance(payload, Mapping) else {}
            if isinstance(result, Mapping):
                return str(result.get("status") or "").strip().lower()
        return ""

    def _payload_has_provenance(value: Any) -> bool:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if str(key).strip() in provenance_keys:
                    if isinstance(nested, list):
                        if any(str(item).strip() for item in nested):
                            return True
                    elif isinstance(nested, Mapping):
                        if nested:
                            return True
                    elif str(nested).strip():
                        return True
                if _payload_has_provenance(nested):
                    return True
        elif isinstance(value, list):
            for nested in value:
                if _payload_has_provenance(nested):
                    return True
        return False

    def _direct_string_refs(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _final_source_refs(artifact_records_value: Sequence[Mapping[str, Any]]) -> tuple[set[str], set[str]]:
        source_artifact_ids: set[str] = set()
        source_task_ids: set[str] = set()
        for artifact in artifact_records_value:
            if str(artifact.get("kind") or "").strip() != ArtifactKind.AGGREGATED_ANSWER.value:
                continue
            payload = artifact.get("payload") if isinstance(artifact.get("payload"), Mapping) else {}
            nested = payload.get("aggregated_answer") if isinstance(payload.get("aggregated_answer"), Mapping) else {}
            payloads = [payload, nested]
            for item in payloads:
                source_artifact_ids.update(_direct_string_refs(item.get("source_artifact_id")))
                source_artifact_ids.update(_direct_string_refs(item.get("source_artifact_ids")))
                source_task_ids.update(_direct_string_refs(item.get("source_task_id")))
                source_task_ids.update(_direct_string_refs(item.get("source_task_ids")))
                for result in item.get("subtask_results") or []:
                    if not isinstance(result, Mapping):
                        continue
                    source_task_ids.update(_direct_string_refs(result.get("task_id")))
                    source_artifact_ids.update(_direct_string_refs(result.get("artifact_id")))
                    source_artifact_ids.update(_direct_string_refs(result.get("source_artifact_id")))
        return source_artifact_ids, source_task_ids

    task_records = _normalise_ledger_records(tasks)
    artifact_records = _normalise_ledger_records(artifacts)
    task_id_counts: Dict[str, int] = {}
    for task in task_records:
        task_id = str(task.get("task_id") or "").strip()
        if task_id:
            task_id_counts[task_id] = task_id_counts.get(task_id, 0) + 1
    artifact_id_counts: Dict[str, int] = {}
    for artifact in artifact_records:
        artifact_id = str(artifact.get("artifact_id") or "").strip()
        if artifact_id:
            artifact_id_counts[artifact_id] = artifact_id_counts.get(artifact_id, 0) + 1
    artifact_by_id = {
        str(item.get("artifact_id") or "").strip(): item
        for item in artifact_records
        if str(item.get("artifact_id") or "").strip()
    }
    referenced_artifact_ids: set[str] = set()
    task_views: List[Dict[str, Any]] = []

    for task in task_records:
        artifact_ids = [
            str(value).strip()
            for value in (task.get("artifact_ids") or [])
            if str(value).strip()
        ]
        referenced_artifact_ids.update(artifact_ids)
        attached = [
            artifact_by_id[artifact_id]
            for artifact_id in artifact_ids
            if artifact_id in artifact_by_id
        ]
        latest = attached[-1] if attached else {}
        task_views.append(
            {
                "task_id": str(task.get("task_id") or "").strip(),
                "kind": str(task.get("kind") or "").strip(),
                "label": str(task.get("label") or "").strip(),
                "status": str(task.get("status") or "").strip(),
                "metric_family": str(task.get("metric_family") or "").strip(),
                "artifact_ids": artifact_ids,
                "artifact_kinds": [
                    str(artifact.get("kind") or "").strip()
                    for artifact in attached
                    if str(artifact.get("kind") or "").strip()
                ],
                "latest_artifact_id": str(latest.get("artifact_id") or "").strip(),
                "latest_artifact_kind": str(latest.get("kind") or "").strip(),
                "latest_artifact_status": str(latest.get("status") or "").strip(),
                "latest_artifact_summary": str(latest.get("summary") or "").strip(),
            }
        )

    artifact_views: List[Dict[str, Any]] = []
    for artifact in artifact_records:
        payload = artifact.get("payload") if isinstance(artifact.get("payload"), dict) else {}
        artifact_views.append(
            {
                "artifact_id": str(artifact.get("artifact_id") or "").strip(),
                "task_id": str(artifact.get("task_id") or "").strip(),
                "kind": str(artifact.get("kind") or "").strip(),
                "status": str(artifact.get("status") or "").strip(),
                "summary": str(artifact.get("summary") or "").strip(),
                "payload_keys": sorted(str(key) for key in payload.keys()),
                "evidence_refs": [
                    str(value).strip()
                    for value in (artifact.get("evidence_refs") or [])
                    if str(value).strip()
                ],
            }
        )

    artifact_ids = {
        str(item.get("artifact_id") or "").strip()
        for item in artifact_records
        if str(item.get("artifact_id") or "").strip()
    }
    task_ids = {
        str(item.get("task_id") or "").strip()
        for item in task_records
        if str(item.get("task_id") or "").strip()
    }
    missing_artifact_ids = sorted(
        artifact_id for artifact_id in referenced_artifact_ids if artifact_id not in artifact_ids
    )
    orphan_artifact_ids = sorted(
        artifact_id
        for artifact_id, artifact in artifact_by_id.items()
        if str(artifact.get("task_id") or "").strip() not in task_ids
    )
    integrity_issues: List[Dict[str, Any]] = []

    for task_id, count in sorted(task_id_counts.items()):
        if count > 1:
            integrity_issues.append(
                {"type": "duplicate_task_id", "severity": "error", "task_id": task_id, "count": count}
            )
    for artifact_id, count in sorted(artifact_id_counts.items()):
        if count > 1:
            integrity_issues.append(
                {"type": "duplicate_artifact_id", "severity": "error", "artifact_id": artifact_id, "count": count}
            )
    for artifact_id in missing_artifact_ids:
        integrity_issues.append(
            {"type": "missing_artifact_reference", "severity": "error", "artifact_id": artifact_id}
        )
    for artifact_id in orphan_artifact_ids:
        integrity_issues.append(
            {"type": "orphan_artifact", "severity": "warning", "artifact_id": artifact_id}
        )
    final_source_artifact_ids, final_source_task_ids = _final_source_refs(artifact_records)
    for artifact_id in sorted(set(orphan_artifact_ids) & final_source_artifact_ids):
        integrity_issues.append(
            {
                "type": "final_source_orphan_artifact",
                "severity": "error",
                "artifact_id": artifact_id,
            }
        )
    for task in task_views:
        status = str(task.get("status") or "").strip().lower()
        if status in {"completed", "partial"} and not list(task.get("artifact_ids") or []):
            integrity_issues.append(
                {
                    "type": "task_without_artifacts",
                    "severity": "warning",
                    "task_id": task.get("task_id") or "",
                    "status": status,
                }
            )
            if str(task.get("task_id") or "").strip() in final_source_task_ids:
                integrity_issues.append(
                    {
                        "type": "final_source_task_without_artifacts",
                        "severity": "error",
                        "task_id": task.get("task_id") or "",
                        "status": status,
                    }
                )
        required_kinds = sorted(
            required_artifact_kinds_by_task_kind.get(str(task.get("kind") or "").strip(), set())
        )
        if status == "completed" and required_kinds:
            task_kind = str(task.get("kind") or "").strip()
            attached_artifacts = [
                artifact_by_id[artifact_id]
                for artifact_id in (task.get("artifact_ids") or [])
                if artifact_id in artifact_by_id
            ]
            present_kinds = {
                str(kind).strip()
                for kind in (task.get("artifact_kinds") or [])
                if str(kind).strip()
            }
            for missing_kind in sorted(set(required_kinds) - present_kinds):
                integrity_issues.append(
                    {
                        "type": "missing_required_artifact_kind",
                        "severity": "error",
                        "task_id": task.get("task_id") or "",
                        "task_kind": task.get("kind") or "",
                        "artifact_kind": missing_kind,
                    }
                )
            for artifact in attached_artifacts:
                artifact_kind = str(artifact.get("kind") or "").strip()
                if artifact_kind not in required_kinds:
                    continue
                payload = artifact.get("payload") if isinstance(artifact.get("payload"), Mapping) else {}
                missing_payload_key = _payload_missing_contract(artifact_kind, payload)
                if missing_payload_key:
                    integrity_issues.append(
                        {
                            "type": "missing_required_artifact_payload",
                            "severity": "error",
                            "task_id": task.get("task_id") or "",
                            "task_kind": task.get("kind") or "",
                            "artifact_id": str(artifact.get("artifact_id") or "").strip(),
                            "artifact_kind": artifact_kind,
                            "payload_key": missing_payload_key,
                        }
                    )
                elif artifact_kind == ArtifactKind.CRITIC_REPORT.value:
                    report = (
                        payload.get("critic_report")
                        if isinstance(payload.get("critic_report"), Mapping)
                        else payload
                    )
                    acceptance_state = critic_report_runtime_acceptance_state(dict(report))
                    acceptance_reasons = list(acceptance_state.get("reasons") or [])
                    if "critic_rejected" in acceptance_reasons:
                        target_refs = list(acceptance_state.get("target_refs") or [])
                        integrity_issues.append(
                            {
                                "type": "critic_report_rejected",
                                "severity": "error",
                                "task_id": task.get("task_id") or "",
                                "task_kind": task.get("kind") or "",
                                "artifact_id": str(artifact.get("artifact_id") or "").strip(),
                                "artifact_kind": artifact_kind,
                                "runtime_acceptance_status": acceptance_state.get(
                                    "runtime_acceptance_status"
                                ),
                                "reasons": acceptance_reasons,
                                "target_refs": target_refs,
                                "target_task_ids": [
                                    ref for ref in target_refs if ref in task_ids
                                ],
                                "target_artifact_ids": [
                                    ref for ref in target_refs if ref in artifact_ids
                                ],
                            }
                        )
            has_evidence_ref = any(
                str(value).strip()
                for artifact in attached_artifacts
                for value in (artifact.get("evidence_refs") or [])
            )
            has_payload_provenance = any(
                _payload_has_provenance(artifact.get("payload") or {})
                for artifact in attached_artifacts
            )
            requires_evidence_ref = task_kind == TaskKind.CALCULATION.value
            if task_kind == TaskKind.RECONCILIATION.value:
                requires_evidence_ref = _reconciliation_result_status(attached_artifacts) in {"ok", "ready"}
            elif task_kind == TaskKind.REFLECTION.value:
                requires_evidence_ref = False
            elif task_kind == TaskKind.RETRIEVAL.value:
                requires_evidence_ref = True
            elif task_kind == TaskKind.SYNTHESIS.value:
                requires_evidence_ref = True
            elif task_kind == TaskKind.CRITIC.value:
                requires_evidence_ref = True
            if requires_evidence_ref and not has_evidence_ref and not has_payload_provenance:
                integrity_issues.append(
                    {
                        "type": "missing_required_evidence_ref",
                        "severity": "error",
                        "task_id": task.get("task_id") or "",
                        "task_kind": task_kind,
                    }
                )

    integrity_status = "ok"
    if any(issue.get("severity") == "error" for issue in integrity_issues):
        integrity_status = "error"
    elif integrity_issues:
        integrity_status = "warning"

    return {
        "tasks": task_views,
        "artifacts": artifact_views,
        "task_count": len(task_views),
        "artifact_count": len(artifact_views),
        "orphan_artifact_ids": orphan_artifact_ids,
        "missing_artifact_ids": missing_artifact_ids,
        "integrity_status": integrity_status,
        "integrity_issue_count": len(integrity_issues),
        "integrity_issues": integrity_issues,
    }


def _extract_artifact_payload_value(
    artifact: Dict[str, Any],
    payload_key: str,
) -> Any:
    payload = dict(artifact.get("payload") or {})
    value = payload.get(payload_key)
    if isinstance(value, list):
        return [dict(item) if isinstance(item, dict) else item for item in value]
    if isinstance(value, dict):
        return dict(value)
    return value


def _find_task_record_in_list(tasks: List[Dict[str, Any]], task_id: str) -> Dict[str, Any]:
    task_id = str(task_id or "").strip()
    if not task_id:
        return {}
    for task in reversed(list(tasks or [])):
        if str(task.get("task_id") or "").strip() == task_id:
            return dict(task)
    return {}


def _latest_artifact_value_for_task_records(
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    *,
    task_id: str,
    kind: ArtifactKind,
    payload_key: str,
) -> Any:
    kind_value = str(kind.value if hasattr(kind, "value") else kind)
    task_record = _find_task_record_in_list(tasks, task_id)
    artifact_ids = [
        str(value).strip()
        for value in (task_record.get("artifact_ids") or [])
        if str(value).strip()
    ]

    for artifact_id in reversed(artifact_ids):
        for artifact in reversed(list(artifacts or [])):
            if str(artifact.get("artifact_id") or "").strip() != artifact_id:
                continue
            if str(artifact.get("kind") or "") != kind_value:
                continue
            return _extract_artifact_payload_value(artifact, payload_key)

    for artifact in reversed(list(artifacts or [])):
        if str(artifact.get("task_id") or "").strip() != str(task_id or "").strip():
            continue
        if str(artifact.get("kind") or "") != kind_value:
            continue
        return _extract_artifact_payload_value(artifact, payload_key)

    return {} if payload_key.endswith("_result") or payload_key.endswith("_plan") else []


def _project_task_trace_from_runtime(
    result: Dict[str, Any],
    task_id: str,
) -> Dict[str, Any]:
    tasks = [dict(item) for item in (result.get("tasks") or [])]
    artifacts = [dict(item) for item in (result.get("artifacts") or [])]
    task_id = str(task_id or "").strip()

    if not task_id or not tasks or not artifacts:
        return {
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

    return {
        "calculation_operands": list(
            _latest_artifact_value_for_task_records(
                tasks,
                artifacts,
                task_id=task_id,
                kind=ArtifactKind.OPERAND_SET,
                payload_key="calculation_operands",
            )
            or []
        ),
        "calculation_plan": dict(
            _latest_artifact_value_for_task_records(
                tasks,
                artifacts,
                task_id=task_id,
                kind=ArtifactKind.CALCULATION_PLAN,
                payload_key="calculation_plan",
            )
            or {}
        ),
        "calculation_result": dict(
            _latest_artifact_value_for_task_records(
                tasks,
                artifacts,
                task_id=task_id,
                kind=ArtifactKind.CALCULATION_RESULT,
                payload_key="calculation_result",
            )
            or {}
        ),
    }


def _project_task_trace_from_state(
    state: Dict[str, Any],
    task_id: str,
) -> Dict[str, Any]:
    task_id = str(task_id or "").strip()
    active_task_id = str((state.get("active_subtask") or {}).get("task_id") or "").strip()
    tasks = [dict(item) for item in (state.get("tasks") or [])]
    artifacts = [dict(item) for item in (state.get("artifacts") or [])]

    calculation_operands = _latest_artifact_value_for_task_records(
        tasks,
        artifacts,
        task_id=task_id,
        kind=ArtifactKind.OPERAND_SET,
        payload_key="calculation_operands",
    )
    calculation_plan = _latest_artifact_value_for_task_records(
        tasks,
        artifacts,
        task_id=task_id,
        kind=ArtifactKind.CALCULATION_PLAN,
        payload_key="calculation_plan",
    )
    calculation_result = _latest_artifact_value_for_task_records(
        tasks,
        artifacts,
        task_id=task_id,
        kind=ArtifactKind.CALCULATION_RESULT,
        payload_key="calculation_result",
    )
    reconciliation_result = _latest_artifact_value_for_task_records(
        tasks,
        artifacts,
        task_id=task_id,
        kind=ArtifactKind.RECONCILIATION_RESULT,
        payload_key="reconciliation_result",
    )

    if task_id and task_id == active_task_id:
        suppress_aggregate_fallback = False
        active_trace = _normalise_resolved_calculation_trace(state)
        if not active_trace:
            active_trace = _resolve_runtime_calculation_trace(
                state,
                allow_legacy_top_level=False,
            )
        active_trace_result = dict(active_trace.get("calculation_result") or {})
        active_trace_plan = dict(active_trace.get("calculation_plan") or {})
        active_trace_operation = _trace_operation_family(
            calculation_plan=active_trace_plan,
            calculation_result=active_trace_result,
        )
        live_state_result = dict(state.get("calculation_result") or {})
        live_state_plan = dict(state.get("calculation_plan") or {})
        live_state_operation = _trace_operation_family(
            calculation_plan=live_state_plan,
            calculation_result=live_state_result,
        )
        prefer_live_state = (
            active_trace_operation == "aggregate_subtasks"
            and live_state_operation
            and live_state_operation != "aggregate_subtasks"
        ) or (
            str(active_trace_result.get("status") or "").strip().lower() == "partial"
            and str(live_state_result.get("status") or "").strip().lower() == "ok"
        )
        if active_trace_operation == "aggregate_subtasks" and not prefer_live_state:
            if calculation_operands or calculation_plan or calculation_result:
                active_trace = {}
                suppress_aggregate_fallback = True
            elif state.get("calculation_operands") or state.get("calculation_plan") or state.get("calculation_result"):
                # Aggregate projections summarize already-finished siblings.
                # They must not be captured as the current active task's own
                # result when that task did not produce material yet.
                if live_state_operation and live_state_operation != "aggregate_subtasks":
                    prefer_live_state = True
                else:
                    active_trace = {}
                    suppress_aggregate_fallback = True
        if prefer_live_state and state.get("calculation_operands"):
            calculation_operands = [dict(item) for item in (state.get("calculation_operands") or [])]
        elif active_trace.get("calculation_operands"):
            calculation_operands = [
                dict(item)
                for item in (
                    active_trace.get("calculation_operands")
                    or []
                )
            ]
        if prefer_live_state and state.get("calculation_plan"):
            calculation_plan = dict(state.get("calculation_plan") or {})
        elif active_trace.get("calculation_plan"):
            calculation_plan = dict(
                active_trace.get("calculation_plan")
            )
        if prefer_live_state and live_state_result:
            calculation_result = live_state_result
        elif active_trace.get("calculation_result"):
            calculation_result = dict(
                active_trace.get("calculation_result")
            )
        if not reconciliation_result:
            reconciliation_result = dict(state.get("reconciliation_result") or {})

    task_record = _find_task_record_in_list(tasks, task_id)
    return {
        "task_id": task_id,
        "artifact_ids": [str(value).strip() for value in (task_record.get("artifact_ids") or []) if str(value).strip()],
        "calculation_operands": list(calculation_operands or []),
        "calculation_plan": dict(calculation_plan or {}),
        "calculation_result": dict(calculation_result or {}),
        "reconciliation_result": dict(reconciliation_result or {}),
    }


def _build_aggregate_calculation_projection(
    subtask_results: List[Dict[str, Any]],
    final_answer: str,
) -> Dict[str, Any]:
    aggregate_operands: List[Dict[str, Any]] = []
    seen_operand_keys: set[tuple[str, ...]] = set()
    subtask_plans: List[Dict[str, Any]] = []
    subtask_result_views: List[Dict[str, Any]] = []

    for row in list(subtask_results or []):
        task_id = str(row.get("task_id") or "").strip()
        metric_family = str(row.get("metric_family") or "").strip()
        metric_label = str(row.get("metric_label") or "").strip()

        for operand in list(row.get("calculation_operands") or []):
            operand_row = dict(operand)
            if not _operand_row_has_material_numeric_payload(operand_row):
                continue
            operand_row.setdefault("task_id", task_id)
            operand_row.setdefault("metric_family", metric_family)
            operand_row.setdefault("metric_label", metric_label)
            operand_source_ids = _clean_source_row_ids([
                operand_row.get("source_row_id"),
                operand_row.get("source_row_ids"),
            ])
            operand_key = (
                str(operand_row.get("task_id") or ""),
                str(operand_row.get("operand_id") or operand_row.get("matched_operand_role") or ""),
                operand_source_ids[0] if operand_source_ids else "",
                "|".join(operand_source_ids),
                str(operand_row.get("raw_value") or operand_row.get("value") or ""),
                str(operand_row.get("raw_unit") or ""),
                str(operand_row.get("label") or operand_row.get("label_kr") or ""),
            )
            if operand_key in seen_operand_keys:
                continue
            seen_operand_keys.add(operand_key)
            aggregate_operands.append(operand_row)

        plan = dict(row.get("calculation_plan") or {})
        if plan:
            subtask_plans.append(
                {
                    "task_id": task_id,
                    "metric_family": metric_family,
                    "metric_label": metric_label,
                    "calculation_plan": plan,
                }
            )

        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        operation_family = _trace_operation_family(
            calculation_plan=plan,
            calculation_result=calculation_result,
        ) or str(answer_slots.get("operation_family") or row.get("operation_family") or "").strip()
        subtask_source_row_ids = _clean_source_row_ids([
            row.get("source_row_id"),
            row.get("source_row_ids"),
            calculation_result.get("source_row_ids"),
            answer_slots.get("source_row_ids"),
        ])
        subtask_source_evidence_ids = _extract_subtask_source_evidence_ids(
            row,
            calculation_result,
            answer_slots,
            subtask_source_row_ids,
        )
        subtask_result_views.append(
            {
                "task_id": task_id,
                "metric_family": metric_family,
                "metric_label": metric_label,
                "operation_family": operation_family,
                "answer": str(row.get("answer") or "").strip(),
                "status": str(row.get("status") or ""),
                "calculation_result": calculation_result,
                "source_row_ids": subtask_source_row_ids,
                "source_evidence_ids": subtask_source_evidence_ids,
            }
        )

    all_ok = all(str(item.get("status") or "") == "ok" for item in subtask_result_views) if subtask_result_views else False
    source_row_ids = list(
        dict.fromkeys(
            source_row_id
            for operand in aggregate_operands
            for source_row_id in _clean_source_row_ids([
                operand.get("source_row_id"),
                operand.get("source_row_ids"),
            ])
        )
    )
    subtask_source_row_ids = list(
        dict.fromkeys(
            source_row_id
            for item in subtask_result_views
            for source_row_id in _clean_source_row_ids(item.get("source_row_ids") or [])
        )
    )
    source_evidence_ids = list(
        dict.fromkeys(
            source_id
            for item in subtask_result_views
            for source_id in _clean_source_row_ids(item.get("source_evidence_ids") or [])
        )
    )
    aggregate_source_row_ids = list(dict.fromkeys([*source_row_ids, *subtask_source_row_ids, *source_evidence_ids]))
    return {
        "calculation_operands": aggregate_operands,
        "calculation_plan": {
            "status": "ok" if subtask_plans else "empty",
            "mode": "aggregate_subtasks",
            "subtask_count": len(subtask_result_views),
            "subtasks": subtask_plans,
        },
        "calculation_result": {
            "status": "ok" if all_ok else "partial",
            "rendered_value": final_answer,
            "formatted_result": final_answer,
            "source_row_ids": aggregate_source_row_ids,
            "source_evidence_ids": source_evidence_ids,
            "subtask_results": subtask_result_views,
            "answer_slots": validate_answer_slots_payload(
                {
                    "operation_family": "aggregate_subtasks",
                    "source_row_ids": aggregate_source_row_ids,
                    "subtask_results": [
                        {
                            "task_id": str(item.get("task_id") or ""),
                            "metric_family": str(item.get("metric_family") or ""),
                            "metric_label": str(item.get("metric_label") or ""),
                            "operation_family": str(item.get("operation_family") or ""),
                            "answer": str(item.get("answer") or ""),
                            "answer_slots": dict((item.get("calculation_result") or {}).get("answer_slots") or {}),
                            "rendered_value": str((item.get("calculation_result") or {}).get("rendered_value") or ""),
                            "source_row_ids": list(item.get("source_row_ids") or []),
                            "source_evidence_ids": list(item.get("source_evidence_ids") or []),
                        }
                        for item in subtask_result_views
                    ],
                }
            ),
            "derived_metrics": {
                "subtask_count": len(subtask_result_views),
                "subtask_ids": [
                    str(item.get("task_id") or "")
                    for item in subtask_result_views
                    if str(item.get("task_id") or "").strip()
                ],
                "aggregate_source_row_ids": aggregate_source_row_ids,
                "aggregate_source_evidence_ids": source_evidence_ids,
            },
        },
    }


def _trace_has_material(trace: Mapping[str, Any]) -> bool:
    return bool(
        trace.get("calculation_operands")
        or trace.get("calculation_plan")
        or trace.get("calculation_result")
    )


def _attach_runtime_projection_metadata(
    trace: Dict[str, Any],
    *,
    source: str,
    source_task_id: str = "",
    legacy_fallback: bool = False,
) -> Dict[str, Any]:
    if not _trace_has_material(trace):
        return trace
    metadata = dict(trace.get("runtime_projection") or {})
    metadata.update(
        {
            "source": str(source or "").strip(),
            "legacy_fallback": bool(legacy_fallback),
        }
    )
    if source_task_id:
        metadata["source_task_id"] = str(source_task_id).strip()
    trace["runtime_projection"] = metadata
    return trace


def _build_runtime_calculation_trace(
    *,
    calculation_operands: Optional[List[Dict[str, Any]]] = None,
    calculation_plan: Optional[Dict[str, Any]] = None,
    calculation_result: Optional[Dict[str, Any]] = None,
    source: str,
    source_task_id: str = "",
    legacy_fallback: bool = False,
) -> RuntimeCalculationTrace:
    trace: RuntimeCalculationTrace = {
        "calculation_operands": [dict(item) for item in (calculation_operands or [])],
        "calculation_plan": dict(calculation_plan or {}),
        "calculation_result": dict(calculation_result or {}),
    }
    return _attach_runtime_projection_metadata(
        trace,
        source=source,
        source_task_id=source_task_id,
        legacy_fallback=legacy_fallback,
    )


def _first_mapping(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _source_section_from_table_id(value: Any) -> str:
    text = _normalise_spaces(str(value or ""))
    if not text:
        return ""
    marker_index = text.find("::table:")
    if marker_index <= 0:
        return ""
    return text[:marker_index].strip()


def _report_cache_candidate_for_trace(state: Dict[str, Any], trace: Dict[str, Any]) -> Dict[str, Any]:
    report_scope = dict(state.get("report_scope") or {})
    active_subtask = dict(state.get("active_subtask") or {})
    calculation_operands = [
        dict(item)
        for item in list(trace.get("calculation_operands") or [])
        if isinstance(item, Mapping)
    ]
    calculation_plan = dict(trace.get("calculation_plan") or {})
    calculation_result = dict(trace.get("calculation_result") or {})
    if not (calculation_operands or calculation_plan or calculation_result):
        return {}
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    primary_slot = _first_mapping(
        answer_slots.get("primary_value"),
        answer_slots.get("current_value"),
        answer_slots.get("delta_value"),
    )
    operand = calculation_operands[0] if calculation_operands else {}
    operand_metadata = dict(operand.get("metadata") or {})
    source_table_id = (
        operand.get("source_table_id")
        or operand.get("table_source_id")
        or operand_metadata.get("source_table_id")
        or operand_metadata.get("table_source_id")
    )

    candidate = {
        **report_scope,
        "value_kind": "calculation_result",
        "concept_id": (
            primary_slot.get("concept")
            or active_subtask.get("concept_id")
            or active_subtask.get("metric_family")
            or state.get("target_metric_family")
        ),
        "metric_label": (
            primary_slot.get("label")
            or active_subtask.get("metric_label")
            or calculation_result.get("metric_label")
        ),
        "period": (
            primary_slot.get("period")
            or primary_slot.get("period_label")
            or operand.get("period")
            or operand.get("period_label")
            or report_scope.get("year")
        ),
        "value_text": (
            calculation_result.get("rendered_value")
            or calculation_result.get("formatted_value")
            or calculation_result.get("formatted_result")
            or primary_slot.get("display")
            or primary_slot.get("value_text")
            or primary_slot.get("rendered_value")
        ),
        "normalized_value": (
            calculation_result.get("value")
            if calculation_result.get("value") is not None
            else primary_slot.get("normalized_value")
        ),
        "consolidation_scope": (
            operand.get("consolidation_scope")
            or operand_metadata.get("consolidation_scope")
            or active_subtask.get("consolidation_scope")
        ),
        "statement_type": operand.get("statement_type") or operand_metadata.get("statement_type"),
        "source_section": (
            operand.get("source_section")
            or operand.get("source_section_path")
            or operand.get("section_path")
            or operand_metadata.get("source_section")
            or operand_metadata.get("section_path")
            or _source_section_from_table_id(source_table_id)
        ),
        "source_table_id": source_table_id,
        "source_anchor": operand.get("source_anchor") or operand_metadata.get("source_anchor"),
        "source_row_id": (
            operand.get("source_row_id")
            or operand.get("source_row_ids")
            or operand.get("row_id")
            or primary_slot.get("source_row_id")
            or primary_slot.get("source_row_ids")
        ),
        "evidence_refs": calculation_result.get("evidence_refs") or primary_slot.get("evidence_refs"),
    }
    classification = classify_report_cache_candidate(candidate)
    projection = {
        "status": classification["status"],
        "reasons": list(classification.get("reasons") or []),
        "key": dict(classification.get("key") or {}),
        "key_id": report_cache_key_id(classification.get("key") or {}),
        "read_only": True,
    }
    projection["retrieval_bypass"] = classify_report_cache_consumer_candidate(projection)
    return projection


def _build_fallback_calculation_trace(
    result: Dict[str, Any],
    *,
    allow_legacy_top_level: bool = True,
) -> Dict[str, Any]:
    operands = list(result.get("calculation_operands") or [])
    plan = dict(result.get("calculation_plan") or {})
    top_level_result = dict(result.get("calculation_result") or {})
    structured_result = dict(result.get("structured_result") or {})
    if not allow_legacy_top_level:
        if structured_result:
            return _build_runtime_calculation_trace(
                calculation_result=structured_result,
                source="structured_result",
                legacy_fallback=False,
            )
        return {}

    calculation_result = dict(top_level_result)
    source = "legacy_top_level"
    legacy_fallback = bool(operands or plan or top_level_result)

    if structured_result:
        calculation_result = structured_result
        if not operands and not plan and not top_level_result:
            source = "structured_result"
            legacy_fallback = False

    trace = _build_runtime_calculation_trace(
        calculation_operands=operands,
        calculation_plan=plan,
        calculation_result=calculation_result,
        source=source,
        legacy_fallback=legacy_fallback,
    )
    metadata = trace.get("runtime_projection")
    if (
        structured_result
        and isinstance(metadata, MutableMapping)
        and (operands or plan or top_level_result)
    ):
        metadata["calculation_result_source"] = "structured_result"
        if top_level_result:
            metadata["superseded_calculation_result_source"] = "legacy_top_level"
    return trace


def _normalise_resolved_calculation_trace(result: Dict[str, Any]) -> Dict[str, Any]:
    resolved = dict(result.get("resolved_calculation_trace") or {})
    structured_result = dict(result.get("structured_result") or {})

    operands = list(resolved.get("calculation_operands") or [])
    plan = dict(resolved.get("calculation_plan") or {})
    calc_result = dict(resolved.get("calculation_result") or {})
    report_cache_candidate = dict(resolved.get("report_cache_candidate") or {})
    source = "resolved_calculation_trace"
    if structured_result and not calc_result:
        calc_result = structured_result
        if not operands and not plan:
            source = "structured_result"

    if operands or plan or calc_result:
        trace = _build_runtime_calculation_trace(
            calculation_operands=operands,
            calculation_plan=plan,
            calculation_result=calc_result,
            source=source,
            legacy_fallback=False,
        )
        if report_cache_candidate:
            trace["report_cache_candidate"] = report_cache_candidate
        return trace
    return {}


def _trace_operation_family(
    *,
    calculation_plan: Optional[Dict[str, Any]] = None,
    calculation_result: Optional[Dict[str, Any]] = None,
) -> str:
    plan = dict(calculation_plan or {})
    calc_result = dict(calculation_result or {})
    answer_slots = dict(calc_result.get("answer_slots") or {})
    operation_family = _normalise_spaces(
        str(
            answer_slots.get("operation_family")
            or calc_result.get("operation_family")
            or plan.get("operation_family")
            or ""
        )
    ).lower()
    if operation_family:
        return operation_family
    if str(plan.get("mode") or "").strip().lower() == "aggregate_subtasks":
        return "aggregate_subtasks"
    if calc_result.get("subtask_results"):
        return "aggregate_subtasks"
    return ""


def _resolve_runtime_calculation_trace(
    result: Dict[str, Any],
    *,
    allow_legacy_top_level: bool = True,
) -> Dict[str, Any]:
    normalised = _normalise_resolved_calculation_trace(result)
    fallback_trace = _build_fallback_calculation_trace(
        result,
        allow_legacy_top_level=allow_legacy_top_level,
    )
    subtask_results = [dict(item) for item in (result.get("subtask_results") or [])]

    active_task_id = str((result.get("active_subtask") or {}).get("task_id") or "").strip()
    if not active_task_id and not subtask_results:
        calc_task_ids = [
            str(task.get("task_id") or "").strip()
            for task in (result.get("tasks") or [])
            if str(task.get("task_id") or "").strip()
            and str(task.get("kind") or "") == "calculation"
        ]
        if len(calc_task_ids) == 1:
            active_task_id = calc_task_ids[0]

    if normalised:
        plan = dict(normalised.get("calculation_plan") or {})
        calc_result = dict(normalised.get("calculation_result") or {})
        normalised_operation = _trace_operation_family(
            calculation_plan=plan,
            calculation_result=calc_result,
        )
        if normalised_operation and normalised_operation != "aggregate_subtasks":
            return normalised
        if normalised_operation == "aggregate_subtasks":
            if active_task_id:
                projected_active = _project_task_trace_from_runtime(result, active_task_id)
                if _trace_operation_family(
                    calculation_plan=dict(projected_active.get("calculation_plan") or {}),
                    calculation_result=dict(projected_active.get("calculation_result") or {}),
                ) != "aggregate_subtasks" and (
                    projected_active.get("calculation_operands")
                    or projected_active.get("calculation_plan")
                    or projected_active.get("calculation_result")
                ):
                    return _attach_runtime_projection_metadata(
                        projected_active,
                        source="task_artifact_ledger",
                        source_task_id=active_task_id,
                    )
                if _trace_operation_family(
                    calculation_plan=dict(fallback_trace.get("calculation_plan") or {}),
                    calculation_result=dict(fallback_trace.get("calculation_result") or {}),
                ) != "aggregate_subtasks" and (
                    fallback_trace.get("calculation_operands")
                    or fallback_trace.get("calculation_plan")
                    or fallback_trace.get("calculation_result")
                ):
                    return fallback_trace
            return normalised

    if active_task_id:
        projected = _project_task_trace_from_runtime(result, active_task_id)
        if (
            projected["calculation_operands"]
            or projected["calculation_plan"]
            or projected["calculation_result"]
        ):
            return _attach_runtime_projection_metadata(
                projected,
                source="task_artifact_ledger",
                source_task_id=active_task_id,
            )

    if subtask_results:
        final_answer = str(result.get("answer") or result.get("compressed_answer") or "").strip()
        return _attach_runtime_projection_metadata(
            _build_aggregate_calculation_projection(subtask_results, final_answer),
            source="aggregate_subtasks",
        )

    if normalised:
        if (
            dict(normalised.get("runtime_projection") or {}).get("source")
            == "structured_result"
            and (fallback_trace.get("calculation_operands") or fallback_trace.get("calculation_plan"))
        ):
            return fallback_trace
        return normalised

    return fallback_trace


def _resolve_runtime_structured_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return a structured result for export/review compatibility surfaces.

    This helper intentionally preserves legacy top-level fallback because it is
    used by benchmark, replay, MAS, and public response adapters that may read
    older payloads. Live graph readers should resolve the canonical trace
    directly with allow_legacy_top_level=False.
    """
    structured_result = dict(result.get("structured_result") or {})
    if structured_result:
        return structured_result

    resolved_trace = _resolve_runtime_calculation_trace(result)
    resolved_result = dict(resolved_trace.get("calculation_result") or {})
    if resolved_result:
        return resolved_result

    return {}


def _runtime_trace_state_update(
    state: Dict[str, Any],
    *,
    calculation_operands: Optional[List[Dict[str, Any]]] = None,
    calculation_plan: Optional[Dict[str, Any]] = None,
    calculation_result: Optional[Dict[str, Any]] = None,
    include_compatibility_mirrors: bool = False,
) -> Dict[str, Any]:
    # Compatibility carry-forward for callers that omit one of the trace parts.
    # Migrated live graph nodes pass every updated part explicitly, so this
    # fallback remains only for older adapter/helper call surfaces.
    current_trace = _resolve_runtime_calculation_trace(state)
    resolved_trace = _build_runtime_calculation_trace(
        calculation_operands=(
            calculation_operands
            if calculation_operands is not None
            else list(current_trace.get("calculation_operands") or [])
        ),
        calculation_plan=(
            calculation_plan
            if calculation_plan is not None
            else dict(current_trace.get("calculation_plan") or {})
        ),
        calculation_result=(
            calculation_result
            if calculation_result is not None
            else dict(current_trace.get("calculation_result") or {})
        ),
        source="runtime_trace_state_update",
        legacy_fallback=False,
    )
    if calculation_result is not None:
        structured_result = dict(calculation_result)
    else:
        structured_result = _resolve_runtime_structured_result(
            {
                "structured_result": state.get("structured_result", {}),
                "resolved_calculation_trace": resolved_trace,
            }
        )
    update: Dict[str, Any] = {
        "resolved_calculation_trace": resolved_trace,
        "structured_result": structured_result,
    }
    report_cache_candidate = _report_cache_candidate_for_trace(state, resolved_trace)
    if report_cache_candidate:
        resolved_trace["report_cache_candidate"] = report_cache_candidate
    if include_compatibility_mirrors:
        # Internal compatibility mirror while graph-state callers migrate.
        update.update(
            {
                "calculation_operands": list(resolved_trace["calculation_operands"]),
                "calculation_plan": dict(resolved_trace["calculation_plan"]),
                "calculation_result": dict(resolved_trace["calculation_result"]),
            }
        )
    return update


# ---------------------------------------------------------------------------
# Numeric parsing and normalization
# ---------------------------------------------------------------------------

def _parse_number_text(text: str) -> Optional[float]:
    cleaned = _normalise_spaces(str(text or "")).replace(",", "").strip()
    if not cleaned:
        return None
    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1].strip()
    if cleaned.startswith("△"):
        negative = True
        cleaned = cleaned[1:].strip()
    if cleaned.startswith("▲"):
        negative = True
        cleaned = cleaned[1:].strip()
    try:
        value = float(cleaned)
        return -value if negative else value
    except ValueError:
        return None


_ALLOWED_FORMULA_FUNCTIONS: Dict[str, Any] = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "log": math.log,
    "exp": math.exp,
}


def _safe_eval_formula(expression: str, variables: Dict[str, float]) -> float:
    """Evaluate a restricted arithmetic expression used by calculation plans."""
    tree = ast.parse(expression, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError("non-numeric constant")
        if isinstance(node, ast.Name):
            if node.id in variables:
                return float(variables[node.id])
            raise ValueError(f"unknown variable: {node.id}")
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise ValueError("unsupported unary operator")
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0.0:
                    raise ZeroDivisionError("division by zero")
                return left / right
            if isinstance(node.op, ast.Pow):
                return left ** right
            raise ValueError("unsupported binary operator")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("unsupported function call")
            fn = _ALLOWED_FORMULA_FUNCTIONS.get(node.func.id)
            if fn is None:
                raise ValueError(f"unsupported function: {node.func.id}")
            if node.keywords:
                raise ValueError("keyword args are not allowed")
            args = [_eval(arg) for arg in node.args]
            return float(fn(*args))
        raise ValueError(f"unsupported AST node: {type(node).__name__}")

    return float(_eval(tree))


def _extract_composite_krw(text: str) -> Optional[float]:
    cleaned = _normalise_spaces(text)
    composite = re.search(r"(?P<jo>[\d,]+(?:\.\d+)?)\s*조\s*(?P<eok>[\d,]+(?:\.\d+)?)\s*억", cleaned)
    if composite:
        jo = _parse_number_text(composite.group("jo"))
        eok = _parse_number_text(composite.group("eok"))
        if jo is None or eok is None:
            return None
        return jo * 1_0000_0000_0000 + eok * 100_000_000
    only_jo = re.search(r"(?P<jo>[\d,]+(?:\.\d+)?)\s*조\s*원?", cleaned)
    if only_jo:
        jo = _parse_number_text(only_jo.group("jo"))
        if jo is not None:
            return jo * 1_0000_0000_0000
    return None


def _normalise_operand_value(raw_value: str, raw_unit: str) -> tuple[Optional[float], str]:
    """Normalize display-level values into comparison-friendly numeric units."""
    unit = _normalise_spaces(raw_unit).lower()
    composite_krw = _extract_composite_krw(raw_value)
    if composite_krw is not None:
        return composite_krw, "KRW"

    unit_policy = dict(NUMERIC_UNIT_NORMALIZATION_POLICY)
    inline_unit_match = re.fullmatch(
        str(unit_policy.get("inline_value_unit_pattern") or ""),
        _normalise_spaces(raw_value),
    )
    if inline_unit_match:
        raw_value = inline_unit_match.group("value")
        inline_unit = re.sub(r"\s+", "", inline_unit_match.group("unit"))
        inline_unit = str(dict(unit_policy.get("inline_unit_aliases") or {}).get(inline_unit) or inline_unit)
        unit = inline_unit.lower()

    value = _parse_number_text(raw_value)
    percent_units = tuple(str(item) for item in (unit_policy.get("percent_units") or ()) if str(item))
    if value is None and unit in percent_units:
        stripped_value = str(raw_value or "")
        for percent_unit in percent_units:
            stripped_value = stripped_value.replace(percent_unit, "")
        value = _parse_number_text(stripped_value)
    if value is None:
        return None, "UNKNOWN"

    krw_scale = dict(unit_policy.get("krw_scales") or {})
    usd_scale = dict(unit_policy.get("usd_scales") or {})
    compact_unit = re.sub(r"\s+", "", unit)
    count_scale = {base_unit: 1.0 for base_unit in KOREAN_COUNT_UNITS}
    for prefix, scale in KOREAN_COUNT_SCALE_PREFIXES:
        for base_unit in KOREAN_COUNT_UNITS:
            count_scale[f"{prefix}{base_unit}"] = scale

    if unit in krw_scale:
        return value * krw_scale[unit], "KRW"
    if unit in usd_scale:
        return value * usd_scale[unit], "USD"
    if compact_unit in count_scale:
        return value * count_scale[compact_unit], "COUNT"
    if unit in percent_units:
        return value, "PERCENT"
    return value, "UNKNOWN"


def _coerce_lookup_magnitude_value(
    *,
    normalized_value: Optional[float],
    normalized_unit: str,
    raw_value: str,
    concept: str,
    statement_type: str,
    row_label: str = "",
    semantic_label: str = "",
) -> Optional[float]:
    if normalized_value is None or normalized_unit != "KRW" or normalized_value >= 0:
        return normalized_value

    lookup_hints = _lookup_hints_for_concept_key(concept)
    normalized_statement_type = _normalise_spaces(statement_type).lower()
    if not bool(lookup_hints.get("coerce_parenthesized_negative_to_positive_magnitude")):
        return normalized_value
    if normalized_statement_type not in {"income_statement", "summary_financials", "notes"}:
        return normalized_value

    magnitude_surface_tokens = [
        _normalise_spaces(str(token))
        for token in (lookup_hints.get("magnitude_surface_tokens") or [])
        if _normalise_spaces(str(token))
    ]
    surface = _normalise_spaces(" ".join(part for part in (row_label, semantic_label) if part))
    if surface and magnitude_surface_tokens and not any(token in surface for token in magnitude_surface_tokens):
        return normalized_value
    raw_surface = str(raw_value or "")
    if not any(marker in raw_surface for marker in ("(", ")", "△", "▲", "-")):
        return normalized_value
    return abs(normalized_value)


def _coerce_lookup_magnitude_record(
    record: Dict[str, Any],
    evidence_item: Optional[Dict[str, Any]] = None,
    *,
    concept: str = "",
    statement_type: str = "",
    row_label: str = "",
    semantic_label: str = "",
) -> Dict[str, Any]:
    """Apply ontology-declared lookup magnitude semantics to a slot/operand row."""
    updated = dict(record or {})
    normalized_unit = _normalise_spaces(str(updated.get("normalized_unit") or "")).upper()
    normalized_value = updated.get("normalized_value")
    try:
        numeric_value = float(normalized_value)
    except (TypeError, ValueError):
        return updated

    metadata = dict((evidence_item or {}).get("metadata") or {})
    resolved_concept = _normalise_spaces(
        str(
            concept
            or updated.get("concept")
            or updated.get("matched_operand_concept")
            or ""
        )
    )
    resolved_statement_type = _normalise_spaces(
        str(
            statement_type
            or updated.get("statement_type")
            or metadata.get("statement_type")
            or ""
        )
    )
    resolved_row_label = _normalise_spaces(
        " ".join(
            str(part or "")
            for part in (
                row_label,
                updated.get("row_label"),
                updated.get("label"),
                updated.get("matched_operand_label"),
                metadata.get("row_label"),
            )
            if str(part or "").strip()
        )
    )
    resolved_semantic_label = _normalise_spaces(
        " ".join(
            str(part or "")
            for part in (
                semantic_label,
                updated.get("semantic_label"),
                metadata.get("semantic_label"),
                metadata.get("table_value_labels_text"),
            )
            if str(part or "").strip()
        )
    )
    coerced_value = _coerce_lookup_magnitude_value(
        normalized_value=numeric_value,
        normalized_unit=normalized_unit,
        raw_value=_normalise_spaces(str(updated.get("raw_value") or updated.get("rendered_value") or "")),
        concept=resolved_concept,
        statement_type=resolved_statement_type,
        row_label=resolved_row_label,
        semantic_label=resolved_semantic_label,
    )
    if coerced_value != numeric_value:
        raw_value = _normalise_spaces(str(updated.get("raw_value") or ""))
        raw_unit = _normalise_spaces(str(updated.get("raw_unit") or ""))
        rendered_value = _normalise_spaces(str(updated.get("rendered_value") or ""))
        magnitude_raw = raw_value.strip()
        if magnitude_raw.startswith("(") and magnitude_raw.endswith(")"):
            magnitude_raw = magnitude_raw[1:-1].strip()
        magnitude_raw = magnitude_raw.lstrip("△▲-").strip()
        if rendered_value and not updated.get("source_rendered_value"):
            updated["source_rendered_value"] = rendered_value
        if magnitude_raw and raw_unit:
            updated["rendered_value"] = _normalise_spaces(f"{magnitude_raw}{raw_unit}")
        updated["normalized_value"] = coerced_value
        updated["value_coercion"] = "lookup_magnitude_from_source_surface"
    return updated


def _extract_period_sort_key(period: str) -> int:
    text = _normalise_spaces(period)
    year_match = re.search(r"(19|20)\d{2}", text)
    if year_match:
        return int(year_match.group(0))
    if "당기" in text:
        return 9999
    if "전기" in text:
        return 9998
    return -1


def _format_korean_won_compact(value: float) -> str:
    format_policy = dict(KOREAN_WON_COMPACT_FORMAT_POLICY)
    threshold = int(format_policy.get("hundred_million_threshold") or 100_000_000)
    hundred_million_scale = int(format_policy.get("hundred_million_scale") or threshold)
    if abs(value) >= threshold:
        amount = int(round(abs(value) / hundred_million_scale)) * hundred_million_scale
    else:
        amount = int(round(abs(value)))
    negative = value < 0
    trillion_scale = int(format_policy.get("trillion_scale") or 1_0000_0000_0000)
    ten_thousand_scale = int(format_policy.get("ten_thousand_scale") or 10_000)
    jo = amount // trillion_scale
    amount %= trillion_scale
    eok = amount // hundred_million_scale
    amount %= hundred_million_scale
    man = amount // ten_thousand_scale

    parts: List[str] = []
    if jo:
        parts.append(f"{jo}{format_policy.get('trillion_suffix') or ''}")
    if eok:
        parts.append(f"{eok:,}{format_policy.get('hundred_million_suffix') or ''}")
    elif jo:
        parts.append(str(format_policy.get("zero_hundred_million_label") or "0"))
    elif man:
        parts.append(f"{man:,}{format_policy.get('ten_thousand_suffix') or ''}")
    else:
        parts.append(f"{int(round(abs(value))):,}{format_policy.get('base_suffix') or ''}")

    rendered = " ".join(parts)
    return f"-{rendered}" if negative else rendered


def _display_operand_label(label: str) -> str:
    text = _normalise_spaces(label)
    text = re.sub(r"^[\uac00-\ud7a3A-Za-z0-9&.\- ]{2,40}\s+(?=\d{4}\ub144\s+)", "", text)
    text = re.sub(r"^\d{4}년\s*", "", text)
    text = re.sub(r"^\d{4}\s+", "", text)
    return text


# ---------------------------------------------------------------------------
# Semantic planning helpers
# ---------------------------------------------------------------------------

def _strip_rerank_metadata(text: str) -> str:
    raw = str(text or "")
    raw = re.sub(r"\[[^\]]+\]", " ", raw)
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def _metric_terms_from_topic(topic: str) -> set[str]:
    text = _normalise_spaces(topic)
    known_terms = [str(item) for item in METRIC_TOPIC_EXTRACTION_TERMS if str(item)]
    return {term for term in known_terms if term in text}


def _is_ratio_percent_query(text: str) -> bool:
    normalized = _normalise_spaces(text)
    return any(keyword in normalized for keyword in (RATIO_PERCENT_QUERY_POLICY.get("markers") or ()))


def _matched_ontology_concept_specs(query: str, topic: str = "") -> List[Dict[str, Any]]:
    ontology = get_financial_ontology()
    return [
        dict(spec)
        for spec in (ontology.concept_specs(query, topic, "comparison") or [])
        if dict(spec)
    ]


def _desired_statement_types(query: str, topic: str) -> List[str]:
    text = _normalise_spaces(f"{query} {topic}")
    desired: List[str] = []
    for policy in (*FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES, *FINANCIAL_NUMERIC_STATEMENT_HINT_POLICIES):
        markers = tuple(str(item) for item in (policy.get("markers") or ()) if str(item))
        if any(marker in text for marker in markers):
            desired.extend(str(item).strip() for item in (policy.get("statement_types") or ()) if str(item).strip())
    for spec in _matched_ontology_concept_specs(query, topic):
        desired.extend(str(item).strip() for item in (spec.get("preferred_statement_types") or []) if str(item).strip())
        for member_spec in (spec.get("member_specs") or []):
            desired.extend(
                str(item).strip()
                for item in (dict(member_spec).get("preferred_statement_types") or [])
                if str(item).strip()
            )
    return list(dict.fromkeys(desired))


def _desired_consolidation_scope(query: str, report_scope: Dict[str, Any]) -> str:
    text = _normalise_spaces(query)
    query_markers = dict(CONSOLIDATION_SCOPE_POLICY.get("query_markers") or {})
    for scope, markers in query_markers.items():
        if any(str(marker) and str(marker) in text for marker in markers or ()):
            return str(scope)
    scope_value = _normalise_spaces(str((report_scope or {}).get("consolidation") or "")).lower()
    metadata_values = dict(CONSOLIDATION_SCOPE_POLICY.get("metadata_values") or {})
    for scope, values in metadata_values.items():
        if scope_value in {str(value).lower() for value in values or ()}:
            return str(scope)
    default_markers = tuple(str(item) for item in (CONSOLIDATION_SCOPE_POLICY.get("default_consolidated_markers") or ()))
    if any(marker in text for marker in default_markers):
        return "consolidated"
    return "unknown"


def _metadata_period_match_strength(period_labels: List[str], query_years: List[int]) -> float:
    if not query_years or not period_labels:
        return 0.0
    normalized_labels = {str(label).strip() for label in period_labels if str(label).strip()}
    wanted = {str(year) for year in query_years}
    overlap = len(normalized_labels & wanted)
    if overlap <= 0:
        return 0.0
    if overlap >= len(wanted):
        return 1.0
    return overlap / max(len(wanted), 1)


def _prioritize_candidate_items(
    candidate_items: List[Dict[str, Any]],
    query: str,
    topic: str,
    report_scope: Dict[str, Any],
    query_years: List[int],
) -> List[Dict[str, Any]]:
    desired_statement_types = set(_desired_statement_types(query, topic))
    desired_consolidation = _desired_consolidation_scope(query, report_scope)
    table_counts: Dict[str, int] = {}
    for item in candidate_items:
        metadata = dict(item.get("metadata") or {})
        table_source_id = str(metadata.get("table_source_id") or "").strip()
        if table_source_id:
            table_counts[table_source_id] = table_counts.get(table_source_id, 0) + 1

    def score(item: Dict[str, Any]) -> tuple[float, int]:
        metadata = dict(item.get("metadata") or {})
        points = 0.0
        statement_type = str(metadata.get("statement_type") or "unknown").strip()
        if desired_statement_types:
            if statement_type in desired_statement_types:
                points += 3.0
            elif statement_type != "unknown":
                points -= 1.0
        consolidation_scope = str(metadata.get("consolidation_scope") or "unknown").strip()
        if desired_consolidation != "unknown":
            if consolidation_scope == desired_consolidation:
                points += 2.0
            elif consolidation_scope != "unknown":
                points -= 2.0
        period_strength = _metadata_period_match_strength(list(metadata.get("period_labels") or []), query_years)
        points += period_strength * 1.5
        table_source_id = str(metadata.get("table_source_id") or "").strip()
        return points, table_counts.get(table_source_id, 0)

    return sorted(candidate_items, key=score, reverse=True)


def _should_apply_strict_company_scope(companies: List[str], report_scope: Dict[str, Any]) -> bool:
    if not companies:
        return False
    scope = dict(report_scope or {})
    scope_rcept_no = str(scope.get("rcept_no") or "").strip()
    if scope_rcept_no:
        return False
    if _report_scope_source_receipts(scope):
        return False
    return True


def _report_scope_source_reports(report_scope: Dict[str, Any]) -> List[Dict[str, Any]]:
    scope = dict(report_scope or {})
    rows: List[Dict[str, Any]] = []
    for key in ("source_reports", "report_inventory"):
        for item in list(scope.get(key) or []):
            current = dict(item or {})
            receipt_no = str(
                current.get("rcept_no")
                or current.get("receipt_no")
                or str((current.get("metadata") or {}).get("rcept_no") or "")
            ).strip()
            year_raw = current.get("year")
            if year_raw in (None, ""):
                year_raw = (current.get("metadata") or {}).get("year")
            try:
                year = int(year_raw) if year_raw not in (None, "") else None
            except (TypeError, ValueError):
                year = None
            if not receipt_no and year is None:
                continue
            rows.append(
                {
                    "rcept_no": receipt_no,
                    "year": year,
                    "report_type": str(
                        current.get("report_type")
                        or current.get("report_nm")
                        or (current.get("metadata") or {}).get("report_type")
                        or ""
                    ).strip(),
                }
            )
    return rows


def _report_scope_source_receipts(report_scope: Dict[str, Any]) -> List[str]:
    receipts: List[str] = []
    for row in _report_scope_source_reports(report_scope):
        receipt_no = str(row.get("rcept_no") or "").strip()
        if receipt_no and receipt_no not in receipts:
            receipts.append(receipt_no)
    return receipts


def _operand_target_receipts(
    operand: Dict[str, Any],
    query_years: List[int],
    report_scope: Dict[str, Any],
) -> List[str]:
    source_rows = _report_scope_source_reports(report_scope)
    if not source_rows:
        return []

    target_years = _operand_target_years(operand, query_years)
    receipts: List[str] = []
    if target_years:
        for year in target_years:
            for row in source_rows:
                if row.get("year") == year:
                    receipt_no = str(row.get("rcept_no") or "").strip()
                    if receipt_no and receipt_no not in receipts:
                        receipts.append(receipt_no)
        if receipts:
            return receipts

    role = str(operand.get("role") or "").strip()
    year_ranked = [
        row for row in sorted(source_rows, key=lambda current: int(current.get("year") or -1), reverse=True)
        if row.get("year") is not None and str(row.get("rcept_no") or "").strip()
    ]
    if role == "current_period" and year_ranked:
        return [str(year_ranked[0].get("rcept_no") or "").strip()]
    if role == "prior_period" and len(year_ranked) >= 2:
        return [str(year_ranked[1].get("rcept_no") or "").strip()]
    return []


def _candidate_allows_comparative_report_scope_fallback(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
    report_scope: Dict[str, Any],
) -> bool:
    source_rows = _report_scope_source_reports(report_scope)
    if len(source_rows) < 2:
        return False

    target_years = _operand_target_years(operand, query_years)
    explicit_years = _candidate_explicit_years(candidate)
    if not target_years or not explicit_years or not any(year in explicit_years for year in target_years):
        return False

    metadata = dict(candidate.get("metadata") or {})
    candidate_receipt = str(metadata.get("rcept_no") or "").strip()
    if not candidate_receipt:
        return False

    year_ranked = [
        row
        for row in sorted(source_rows, key=lambda current: int(current.get("year") or -1), reverse=True)
        if row.get("year") is not None and str(row.get("rcept_no") or "").strip()
    ]
    if not year_ranked:
        return False
    latest_receipt = str(year_ranked[0].get("rcept_no") or "").strip()
    if candidate_receipt != latest_receipt:
        return False

    role = str(operand.get("role") or "").strip()
    candidate_period_focus = _normalise_spaces(str(metadata.get("period_focus") or ""))
    if role == "prior_period" and candidate_period_focus == "current":
        return False
    if role == "current_period" and candidate_period_focus == "prior":
        return False
    return True


def _candidate_matches_target_report_scope(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
    report_scope: Dict[str, Any],
) -> bool:
    source_rows = _report_scope_source_reports(report_scope)
    if not source_rows:
        return True

    metadata = dict(candidate.get("metadata") or {})
    candidate_receipt = str(metadata.get("rcept_no") or "").strip()
    candidate_year: Optional[int] = None
    try:
        raw_year = metadata.get("year")
        if raw_year not in (None, ""):
            candidate_year = int(raw_year)
    except (TypeError, ValueError):
        candidate_year = None
    explicit_years = _candidate_explicit_years(candidate)
    target_years = _operand_target_years(operand, query_years)
    target_receipts = _operand_target_receipts(operand, query_years, report_scope)

    if target_receipts:
        if candidate_receipt:
            if candidate_receipt in target_receipts:
                return True
            if _candidate_allows_comparative_report_scope_fallback(
                candidate,
                operand=operand,
                query_years=query_years,
                report_scope=report_scope,
            ):
                return True
            return False
        if target_years and explicit_years and any(year in explicit_years for year in target_years):
            return True
        return False

    if target_years:
        if explicit_years:
            return any(year in explicit_years for year in target_years)
        if candidate_year is not None:
            return candidate_year in target_years
    return True


def _candidate_report_scope_binding_bonus(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
    report_scope: Dict[str, Any],
) -> float:
    source_rows = _report_scope_source_reports(report_scope)
    if not source_rows:
        return 0.0

    metadata = dict(candidate.get("metadata") or {})
    candidate_receipt = str(metadata.get("rcept_no") or "").strip()
    explicit_years = _candidate_explicit_years(candidate)
    candidate_year: Optional[int] = None
    try:
        raw_year = metadata.get("year")
        if raw_year not in (None, ""):
            candidate_year = int(raw_year)
    except (TypeError, ValueError):
        candidate_year = None

    target_years = _operand_target_years(operand, query_years)
    target_receipts = _operand_target_receipts(operand, query_years, report_scope)

    if target_receipts:
        if candidate_receipt:
            if candidate_receipt in target_receipts:
                return 3.0
            if _candidate_allows_comparative_report_scope_fallback(
                candidate,
                operand=operand,
                query_years=query_years,
                report_scope=report_scope,
            ):
                return 1.25
            return -3.0
        if explicit_years and target_years and any(year in explicit_years for year in target_years):
            return 1.0
        return -3.0

    if target_years:
        if explicit_years and any(year in explicit_years for year in target_years):
            return 1.0
        if candidate_year is not None and candidate_year in target_years:
            return 0.75
        if candidate_year is not None:
            return -0.75
    return 0.0


def _candidate_matches_operand_target_year(
    candidate: Dict[str, Any],
    operand: Dict[str, Any],
    query_years: List[int],
) -> bool:
    target_years = _operand_target_years(operand, query_years)
    if not target_years:
        return False

    explicit_years = _candidate_explicit_years(candidate)
    if explicit_years and any(year in explicit_years for year in target_years):
        return True

    metadata = dict(candidate.get("metadata") or {})
    try:
        raw_year = metadata.get("year")
        if raw_year not in (None, ""):
            candidate_year = int(raw_year)
            candidate_period_focus = _normalise_spaces(str(metadata.get("period_focus") or ""))
            if candidate_period_focus == "prior":
                return (candidate_year - 1) in target_years
            if candidate_period_focus == "current":
                return candidate_year in target_years
            return candidate_year in target_years
    except (TypeError, ValueError):
        return False
    return False


def _candidate_selected_cell_for_operand(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
    period_focus: str,
) -> Optional[Dict[str, Any]]:
    metadata = dict(candidate.get("metadata") or {})
    candidate_kind = str(candidate.get("candidate_kind") or "").strip()
    cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
    if not cells and candidate_kind in {"table_row", "evidence_row"}:
        cells = _parse_unstructured_table_row_cells(str(metadata.get("row_text") or ""), metadata)
    if not cells:
        return None
    cells = [{**cell, "_report_year": metadata.get("year")} for cell in cells]
    return _select_structured_cell(
        cells,
        operand=operand,
        query_years=query_years,
        period_focus=period_focus,
    )


def _candidate_direct_logical_signature(
    candidate: Dict[str, Any],
    *,
    selected_cell: Optional[Dict[str, Any]] = None,
) -> tuple[str, str, str, str]:
    metadata = dict(candidate.get("metadata") or {})
    block_key = _candidate_row_block_signature(candidate)
    table_source_id = _normalise_spaces(str(metadata.get("table_source_id") or ""))
    row_label = _normalise_spaces(
        str(
            metadata.get("row_label")
            or metadata.get("semantic_label")
            or metadata.get("aggregate_label")
            or ""
        )
    )
    value_text = _normalise_spaces(str((selected_cell or {}).get("value_text") or ""))
    if not value_text:
        value_text = _normalise_spaces(str(metadata.get("row_text") or str(candidate.get("text") or "")))
    period_marker = _normalise_spaces(
        " ".join(str(item).strip() for item in ((selected_cell or {}).get("column_headers") or []) if str(item).strip())
    )
    if not period_marker:
        period_marker = _normalise_spaces(str(metadata.get("period_focus") or ""))
    scope_key = block_key or table_source_id or _normalise_spaces(str(metadata.get("section_path") or ""))
    return (scope_key, row_label, value_text, period_marker)


def _candidate_direct_family_signature(
    candidate: Dict[str, Any],
    *,
    selected_cell: Optional[Dict[str, Any]] = None,
) -> tuple[str, str, str, str]:
    metadata = dict(candidate.get("metadata") or {})
    block_key = _candidate_row_block_signature(candidate)
    table_source_id = _normalise_spaces(str(metadata.get("table_source_id") or ""))
    row_label = _normalise_spaces(
        str(
            metadata.get("row_label")
            or metadata.get("semantic_label")
            or metadata.get("aggregate_label")
            or ""
        )
    )
    period_marker = _normalise_spaces(
        " ".join(str(item).strip() for item in ((selected_cell or {}).get("column_headers") or []) if str(item).strip())
    )
    statement_type = _normalise_spaces(str(metadata.get("statement_type") or ""))
    scope_key = block_key or table_source_id or _normalise_spaces(str(metadata.get("section_path") or ""))
    return (scope_key, row_label, period_marker, statement_type)


def _candidate_is_canonical_statement_winner(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
) -> bool:
    if not _lookup_prefers_canonical_statement_rows(operand):
        return False
    metadata = dict(candidate.get("metadata") or {})
    statement_type = str(metadata.get("statement_type") or "").strip()
    canonical_types, canonical_sections = _lookup_canonical_statement_preferences(operand)
    if canonical_types and statement_type not in canonical_types:
        return False
    canonical_statement_type_hit = bool(canonical_types) and statement_type in canonical_types and statement_type not in {"notes", "unknown"}
    local_heading = _normalise_spaces(
        str(metadata.get("local_heading") or metadata.get("table_context") or metadata.get("section_path") or "")
    )
    section_path = _normalise_spaces(str(metadata.get("section_path") or ""))
    scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
    note_markers = tuple(str(item) for item in (scoring_policy.get("note_context_markers") or ()) if str(item))
    note_context = any(marker in local_heading or marker in section_path for marker in note_markers)
    allows_note_canonical = any(
        marker in _normalise_spaces(section)
        for marker in note_markers
        for section in canonical_sections
    )
    if note_context and not allows_note_canonical:
        return False
    if canonical_sections and not canonical_statement_type_hit and not any(
        _normalise_spaces(section) in local_heading or _normalise_spaces(section) in section_path
        for section in canonical_sections
        if _normalise_spaces(section)
    ):
        return False
    if _candidate_direct_match_strength(candidate, operand) < 2.5:
        return False
    if not _candidate_matches_operand_target_year(candidate, operand, query_years):
        candidate_period_focus = _normalise_spaces(str(metadata.get("period_focus") or ""))
        desired_period_focus = _operand_period_focus(operand, "unknown")
        if desired_period_focus in {"current", "prior"} and candidate_period_focus != desired_period_focus:
            return False
    return True


def _direct_candidate_semantic_priority(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    preferred_statement_types: List[str],
    query_years: List[int],
) -> tuple[int, int, int, int, int]:
    metadata = dict(candidate.get("metadata") or {})
    binding_policy = dict(operand.get("binding_policy") or {})
    normalized_preferred_types = [
        _normalise_spaces(str(item))
        for item in preferred_statement_types
        if _normalise_spaces(str(item))
    ]
    preferred_value_roles = [
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_value_roles") or [])
        if _normalise_spaces(str(item))
    ]
    preferred_aggregation_stages = [
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_aggregation_stages") or [])
        if _normalise_spaces(str(item))
    ]

    statement_type = _normalise_spaces(str(metadata.get("statement_type") or ""))
    value_role = _candidate_value_role(candidate)
    aggregation_stage = _candidate_aggregation_stage(candidate)
    direct_match_strength = _candidate_direct_match_strength(candidate, operand)
    candidate_kind = _normalise_spaces(str(candidate.get("candidate_kind") or ""))

    statement_rank = 0
    if statement_type in normalized_preferred_types:
        statement_rank = len(normalized_preferred_types) - normalized_preferred_types.index(statement_type)

    value_role_rank = 0
    if value_role in preferred_value_roles:
        value_role_rank = len(preferred_value_roles) - preferred_value_roles.index(value_role)

    aggregation_stage_rank = 0
    if aggregation_stage in preferred_aggregation_stages:
        aggregation_stage_rank = len(preferred_aggregation_stages) - preferred_aggregation_stages.index(aggregation_stage)

    target_year_match = 1 if _candidate_matches_operand_target_year(candidate, operand, query_years) else 0
    structured_value_rank = 1 if candidate_kind == "structured_value" else 0

    return (
        aggregation_stage_rank,
        value_role_rank,
        statement_rank,
        target_year_match,
        structured_value_rank + int(direct_match_strength * 10),
    )


def _candidate_sibling_surface_hit_count(candidate: Dict[str, Any], sibling_surfaces: List[str]) -> int:
    if not sibling_surfaces:
        return 0
    metadata = dict(candidate.get("metadata") or {})
    haystack = _normalise_spaces(
        " ".join(
            part
            for part in (
                str(metadata.get("table_row_labels_text") or ""),
                str(metadata.get("table_value_labels_text") or ""),
                str(metadata.get("table_summary_text") or ""),
                str(metadata.get("row_context_text") or ""),
                str(metadata.get("row_text") or ""),
                str(candidate.get("text") or ""),
            )
            if part
        )
    )
    if not haystack:
        return 0
    compact_haystack = re.sub(r"\s+", "", haystack)
    hits = 0
    for surface in list(dict.fromkeys(sibling_surfaces)):
        normalized = _strip_leading_period_qualifiers(_normalise_spaces(str(surface or "")))
        if not normalized:
            continue
        compact_surface = re.sub(r"\s+", "", normalized)
        if normalized in haystack or (compact_surface and compact_surface in compact_haystack):
            hits += 1
    return hits


def _query_mentions_metric(query: str, metric: Dict[str, Any]) -> bool:
    combined = _normalise_spaces(query)
    aliases = [str(metric.get("display_name") or "").strip()]
    aliases.extend(metric.get("aliases", []) or [])
    aliases.extend(metric.get("intent_keywords", []) or [])
    return any(_normalise_spaces(alias) in combined for alias in aliases if str(alias).strip())


def _query_component_match_count(
    query: str,
    operand_specs: List[Dict[str, Any]],
) -> int:
    combined = _normalise_spaces(query)
    matched_labels: List[str] = []
    for spec in operand_specs:
        label = str(spec.get("label") or "").strip()
        aliases = [label]
        aliases.extend(spec.get("aliases", []) or [])
        aliases.extend(spec.get("keywords", []) or [])
        if any(_normalise_spaces(alias) in combined for alias in aliases if str(alias).strip()):
            matched_labels.append(label or str(spec.get("concept") or "").strip())
    return len(dict.fromkeys(item for item in matched_labels if item))


_QUOTED_METRIC_RE = re.compile(r"""['"“”‘’「」『』](?P<label>[^'"“”‘’「」『』]+)['"“”‘’「」『』]""")
_GENERIC_RATIO_SHARE_RE = re.compile(
    r"(?P<denominator>[가-힣A-Za-z0-9·/&\-\s\(\)]+?)\s*중\s*"
    r"(?P<numerator>[가-힣A-Za-z0-9·/&\-\s\(\)]+?)\s*"
    r"(?:(?:이|가)\s*차지하는\s*)?(?:의\s*)?"
    r"(?:비중|비율)"
)
_GENERIC_PERIOD_COMPARISON_METRIC_RE = re.compile(
    r"(?:20\d{2}년\s*)?"
    r"(?P<label>[가-힣A-Za-z0-9·/&\-\s\(\)]{2,80}?)의\s*"
    rf"{KOREAN_PERIOD_COMPARISON_RE_FRAGMENT}\s*"
    rf"{KOREAN_PERIOD_RATE_METRIC_SUFFIX_RE_FRAGMENT}"
)


def _clean_metric_label(label: str) -> str:
    text = _normalise_spaces(str(label or ""))
    label_policy = dict(GENERIC_OPERAND_LABEL_POLICY)
    text = re.sub(str(label_policy.get("leading_year_pattern") or r"$^"), "", text)
    for boundary in label_policy.get("cleanup_boundaries") or ():
        if boundary in text:
            text = text.rsplit(boundary, 1)[-1].strip()
    text = re.sub(str(label_policy.get("cleanup_suffix_pattern") or r"$^"), "", text).strip()
    return text


def _extract_quoted_metric_labels(query: str) -> List[str]:
    labels: List[str] = []
    for match in _QUOTED_METRIC_RE.finditer(str(query or "")):
        cleaned = _clean_metric_label(match.group("label"))
        if cleaned:
            labels.append(cleaned)
    return list(dict.fromkeys(labels))


def _ontology_operand_surface_candidates(spec: Mapping[str, Any]) -> List[str]:
    surface_contract = dict(spec.get("surface_contract") or {})
    candidates: List[str] = [str(spec.get("name") or "").strip()]
    candidates.extend(str(item).strip() for item in (spec.get("aliases") or []) if str(item).strip())
    candidates.extend(str(item).strip() for item in (spec.get("keywords") or []) if str(item).strip())
    candidates.extend(
        str(item).strip()
        for item in (surface_contract.get("positive") or [])
        if str(item).strip()
    )
    return list(dict.fromkeys(item for item in candidates if item))


def _surface_visible_in_text(surface: str, text: str) -> bool:
    normalized_surface = _normalise_spaces(surface)
    if not normalized_surface:
        return False
    normalized_text = _normalise_spaces(text)
    if normalized_surface in normalized_text:
        return True
    compact_surface = re.sub(r"\s+", "", normalized_surface)
    compact_text = re.sub(r"\s+", "", normalized_text)
    return bool(compact_surface and compact_surface in compact_text)


def _drop_redundant_parenthetical_alias_labels(labels: Sequence[str]) -> List[str]:
    normalized = list(dict.fromkeys(label for label in labels if label))
    parenthetical_aliases: set[str] = set()
    for label in normalized:
        for match in re.finditer(r"\(([^()]+)\)", label):
            alias = _normalise_spaces(match.group(1))
            if alias:
                parenthetical_aliases.add(alias)
    if not parenthetical_aliases:
        retained = normalized
    else:
        retained = [
            label
            for label in normalized
            if _normalise_spaces(label) not in parenthetical_aliases
        ]

    deduped: List[str] = []
    compact_seen: set[str] = set()
    for label in retained:
        compact = re.sub(r"\s+", "", _normalise_spaces(label))
        if compact in compact_seen:
            continue
        compact_seen.add(compact)
        deduped.append(label)

    compact_by_label = {
        label: re.sub(r"\s+", "", _normalise_spaces(label))
        for label in deduped
    }
    return [
        label
        for label, compact in compact_by_label.items()
        if not any(
            compact
            and compact != other_compact
            and compact in other_compact
            for other_label, other_compact in compact_by_label.items()
            if other_label != label
        )
    ]


def _extract_generic_operand_labels(query: str) -> List[str]:
    text = str(query or "")
    labels: List[str] = []

    for expansion in GENERIC_OPERAND_LABEL_POLICY.get("compound_label_expansions") or ():
        markers = tuple(str(item) for item in (dict(expansion).get("markers") or ()) if str(item))
        if any(marker in text for marker in markers):
            labels.extend(str(item) for item in (dict(expansion).get("labels") or ()) if str(item))

    labels.extend(_extract_quoted_metric_labels(text))
    for spec in _matched_ontology_concept_specs(query):
        if bool(spec.get("is_group")):
            continue
        visible_surfaces: List[str] = []
        for surface in _ontology_operand_surface_candidates(spec):
            if _surface_visible_in_text(surface, text):
                cleaned = _clean_metric_label(surface)
                if cleaned:
                    visible_surfaces.append(cleaned)
        concept_name = _clean_metric_label(str(spec.get("name") or "").strip())
        if concept_name and not any(re.search(r"[가-힣]", item) for item in visible_surfaces):
            labels.append(concept_name)
        labels.extend(visible_surfaces)
    for match in _GENERIC_PERIOD_COMPARISON_METRIC_RE.finditer(text):
        cleaned = _clean_metric_label(match.group("label"))
        if cleaned:
            labels.append(cleaned)

    normalized = _drop_redundant_parenthetical_alias_labels(labels)
    derived_labels = {str(item) for item in (GENERIC_OPERAND_LABEL_POLICY.get("derived_labels_to_drop") or ())}
    normalized = [item for item in normalized if item not in derived_labels]
    return normalized


def _extract_generic_ratio_operand_specs(query: str) -> List[Dict[str, Any]]:
    text = _normalise_spaces(query)
    if not text:
        return []

    match = _GENERIC_RATIO_SHARE_RE.search(text)
    if not match:
        return []

    denominator = _clean_metric_label(match.group("denominator"))
    numerator = _clean_metric_label(match.group("numerator"))
    if not denominator or not numerator or denominator == numerator:
        return []

    return [
        {
            "label": numerator,
            "role": "numerator_1",
            "required": True,
        },
        {
            "label": denominator,
            "role": "denominator_1",
            "required": True,
        },
    ]


def _label_implies_percent_metric(label: str) -> bool:
    normalized = _normalise_spaces(str(label or ""))
    if not normalized:
        return False
    return any(
        token in normalized
        for token in (*KOREAN_PERCENT_METRIC_HINT_TERMS, "%", "%p")
    )


def _infer_generic_unit_family(label: str) -> str:
    normalized = _normalise_spaces(str(label or ""))
    if not normalized:
        return ""
    if _label_implies_percent_metric(normalized):
        return "PERCENT"
    compact = re.sub(r"\s+", "", normalized)
    unit_policy = dict(GENERIC_UNIT_FAMILY_POLICY)
    count_markers = tuple(str(item) for item in (unit_policy.get("count_markers") or ()) if str(item))
    if any(token in compact for token in count_markers):
        return "COUNT"
    return ""


def _query_requests_narrative_context(query: str) -> bool:
    normalized = _normalise_spaces(str(query or "")).lower()
    if not normalized:
        return False
    narrative_hints = tuple(str(item) for item in (HELPER_RUNTIME_POLICY.get("narrative_context_hints") or ()) if str(item))
    return any(token in normalized for token in narrative_hints)


def _is_single_metric_period_comparison(query: str, operand_labels: List[str]) -> bool:
    text = _normalise_spaces(query)
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    comparison_markers = tuple(str(item) for item in (period_policy.get("comparison_markers") or ()) if str(item))
    if not any(marker in text for marker in comparison_markers):
        return False
    distinct = [label for label in operand_labels if label]
    distinct = list(dict.fromkeys(distinct))
    if len(distinct) <= 1:
        return True
    return False


def _requires_direct_numeric_grounding(active_subtask: Dict[str, Any]) -> bool:
    task = dict(active_subtask or {})
    operation_family = str(task.get("operation_family") or "").strip().lower()
    if operation_family in {"lookup", "single_value"}:
        return True

    required_operands = [
        dict(item)
        for item in (task.get("required_operands") or [])
        if bool(item.get("required", True))
    ]
    if not required_operands:
        return False

    if operation_family in {"ratio", "sum"}:
        concepts = [
            str(item.get("concept") or "").strip()
            for item in required_operands
            if str(item.get("concept") or "").strip()
        ]
        return len(concepts) == len(required_operands)

    if operation_family not in {"difference", "growth_rate"}:
        return False

    concepts = {
        str(item.get("concept") or "").strip()
        for item in required_operands
        if str(item.get("concept") or "").strip()
    }
    roles = {
        str(item.get("role") or "").strip()
        for item in required_operands
        if str(item.get("role") or "").strip()
    }
    if len(concepts) == 1 and {"current_period", "prior_period"}.issubset(roles):
        return True

    operand_labels = [str(item.get("label") or "").strip() for item in required_operands if str(item.get("label") or "").strip()]
    return _is_single_metric_period_comparison(str(task.get("query") or ""), operand_labels)


def _extract_year_tokens(query: str, report_scope: Dict[str, Any]) -> List[int]:
    years: List[int] = []
    for token in re.findall(r"(20\d{2})년", str(query or "")):
        year = int(token)
        if year not in years:
            years.append(year)
    scope_year_raw = report_scope.get("year")
    try:
        if scope_year_raw not in (None, ""):
            scope_year = int(scope_year_raw)
            if scope_year not in years:
                years.insert(0, scope_year)
    except (TypeError, ValueError):
        pass
    for row in _report_scope_source_reports(report_scope):
        year_raw = row.get("year")
        if year_raw in (None, ""):
            year_raw = dict(row.get("metadata") or {}).get("year")
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            continue
        if year not in years:
            years.append(year)
    return years


def _build_generic_metric_aliases(label: str) -> List[str]:
    base = str(label or "").strip()
    if not base:
        return []
    aliases = [base]
    without_parens = _normalise_spaces(re.sub(r"\([^)]*\)", " ", base))
    if without_parens and without_parens != base:
        aliases.append(without_parens)
    for inner in re.findall(r"\(([^)]*)\)", base):
        cleaned_inner = _normalise_spaces(inner)
        if cleaned_inner:
            aliases.append(cleaned_inner)
    for substitution in GENERIC_METRIC_ALIAS_SUBSTITUTIONS:
        source = str(substitution.get("source") or "")
        target = str(substitution.get("target") or "")
        blocked = tuple(str(item) for item in (substitution.get("blocked_if_present") or ()) if str(item))
        if source and target and source in base and not any(token in base for token in blocked):
            aliases.append(base.replace(source, target))
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _infer_generic_concept_spec(
    label: str,
    ontology: Any,
) -> Dict[str, Any]:
    cleaned = _clean_metric_label(label)
    normalized = _normalise_spaces(cleaned)
    if not normalized:
        return {}

    exact_matches: List[Dict[str, Any]] = []
    fuzzy_matches: List[Dict[str, Any]] = []
    for spec in list(getattr(ontology, "all_concept_specs", lambda: [])() or []):
        if bool(spec.get("is_group")):
            continue
        alias_values = [
            str(spec.get("name") or "").strip(),
            *(spec.get("aliases") or []),
            *(spec.get("keywords") or []),
        ]
        normalized_aliases = [
            _normalise_spaces(alias)
            for alias in alias_values
            if _normalise_spaces(alias)
        ]
        if not normalized_aliases:
            continue
        if normalized in normalized_aliases:
            exact_matches.append(dict(spec))
            continue
        if any(normalized in alias or alias in normalized for alias in normalized_aliases):
            fuzzy_matches.append(dict(spec))

    if exact_matches:
        exact_matches.sort(
            key=lambda spec: max(
                (
                    len(_normalise_spaces(alias))
                    for alias in [
                        str(spec.get("name") or "").strip(),
                        *(spec.get("aliases") or []),
                    ]
                    if _normalise_spaces(alias)
                ),
                default=0,
            ),
            reverse=True,
        )
        return exact_matches[0]
    if fuzzy_matches:
        return fuzzy_matches[0]

    matched_specs = [
        dict(spec)
        for spec in list(ontology.concept_specs(cleaned, cleaned, "comparison") or [])
        if not bool(spec.get("is_group"))
    ]
    return matched_specs[0] if matched_specs else {}


def _augment_generic_operand_with_concept(
    operand: Dict[str, Any],
    *,
    concept_spec: Dict[str, Any],
) -> Dict[str, Any]:
    if not concept_spec:
        return dict(operand)

    updated = dict(operand)
    updated["concept"] = str(concept_spec.get("concept") or "").strip()
    updated["aliases"] = list(
        dict.fromkeys(
            [
                *(updated.get("aliases") or []),
                str(concept_spec.get("name") or "").strip(),
                *(concept_spec.get("aliases") or []),
            ]
        )
    )
    updated["keywords"] = list(
        dict.fromkeys(
            [
                *(updated.get("keywords") or []),
                *(concept_spec.get("keywords") or []),
            ]
        )
    )
    updated["preferred_sections"] = list(
        dict.fromkeys(
            [
                *(updated.get("preferred_sections") or []),
                *(concept_spec.get("preferred_sections") or []),
            ]
        )
    )
    updated["preferred_statement_types"] = list(
        dict.fromkeys(
            [
                *(updated.get("preferred_statement_types") or []),
                *(concept_spec.get("preferred_statement_types") or []),
            ]
        )
    )
    binding_policy = dict(concept_spec.get("binding_policy") or {})
    role = str(updated.get("role") or "").strip()
    if role == "current_period" and not str(binding_policy.get("prefer_period_focus") or "").strip():
        binding_policy["prefer_period_focus"] = "current"
    elif role == "prior_period" and not str(binding_policy.get("prefer_period_focus") or "").strip():
        binding_policy["prefer_period_focus"] = "prior"
    updated["binding_policy"] = binding_policy
    updated["surface_contract"] = dict(concept_spec.get("surface_contract") or {})
    if not str(updated.get("unit_family") or "").strip():
        updated["unit_family"] = str(concept_spec.get("unit_family") or "").strip()
    return updated


def _infer_statement_and_section_hints(query: str) -> tuple[List[str], List[str]]:
    text = _normalise_spaces(query)
    ontology = get_financial_ontology()
    statement_types = _desired_statement_types(query, query)
    preferred_sections: List[str] = []
    for policy in FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES:
        markers = tuple(str(item) for item in (policy.get("markers") or ()) if str(item))
        if not any(marker in text for marker in markers):
            continue
        preferred_sections.extend(str(item).strip() for item in (policy.get("preferred_sections") or ()) if str(item).strip())
        for statement_type in policy.get("statement_types") or ():
            if str(statement_type) not in statement_types:
                statement_types.append(str(statement_type))
    segment_markers = tuple(str(item) for item in (FINANCIAL_SEGMENT_SECTION_HINT_POLICY.get("markers") or ()) if str(item))
    if any(marker in text for marker in segment_markers):
        preferred_sections.extend(
            str(item).strip()
            for item in (FINANCIAL_SEGMENT_SECTION_HINT_POLICY.get("preferred_sections") or ())
            if str(item).strip()
        )
        for statement_type in FINANCIAL_SEGMENT_SECTION_HINT_POLICY.get("statement_types") or ():
            if str(statement_type) not in statement_types:
                statement_types.append(str(statement_type))
    preferred_sections.extend(ontology.preferred_sections(query, query, "comparison"))
    numeric_hint_policies = active_numeric_section_hint_policies(text)
    preferred_sections.extend(numeric_section_policy_preferred_sections(numeric_hint_policies))
    for statement_type in numeric_section_policy_statement_types(numeric_hint_policies):
        if statement_type not in statement_types:
            statement_types.append(statement_type)
    active_policies = active_narrative_policies(text)
    preferred_sections.extend(narrative_policy_preferred_sections(active_policies))
    for statement_type in narrative_policy_terms(active_policies, "statement_types"):
        if statement_type not in statement_types:
            statement_types.append(statement_type)
    return list(dict.fromkeys(statement_types)), list(dict.fromkeys(preferred_sections))


def _build_generic_required_operands(
    query: str,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    ontology = get_financial_ontology()
    ratio_operand_specs = _extract_generic_ratio_operand_specs(query)
    if ratio_operand_specs:
        preferred_statement_types, preferred_sections = _infer_statement_and_section_hints(query)
        rows: List[Dict[str, Any]] = []
        for spec in ratio_operand_specs:
            label = str(spec.get("label") or "").strip()
            aliases = _build_generic_metric_aliases(label)
            concept_spec = _infer_generic_concept_spec(label, ontology)
            role = str(spec.get("role") or "").strip()
            binding_policy: Dict[str, Any] = {}
            if role.startswith("denominator"):
                binding_policy = {
                    "prefer_value_roles": ["aggregate"],
                    "prefer_aggregation_stages": ["final", "subtotal", "direct"],
                }
            rows.append(
                _augment_generic_operand_with_concept(
                    {
                        "label": label,
                        "aliases": list(dict.fromkeys(alias for alias in aliases if alias)),
                        "role": role,
                        "required": True,
                        "unit_family": _infer_generic_unit_family(label),
                        "preferred_statement_types": list(preferred_statement_types),
                        "preferred_sections": list(preferred_sections),
                        "binding_policy": binding_policy,
                    },
                    concept_spec=concept_spec,
                )
            )
        if rows:
            return rows

    operand_labels = _extract_generic_operand_labels(query)
    if _is_single_metric_period_comparison(query, operand_labels):
        period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
        current_hint = str(period_policy.get("current_period_hint") or "current")
        prior_hint = str(period_policy.get("prior_period_hint") or "prior")
        year_label_template = str(period_policy.get("year_label_template") or "{year} {label}")
        current_label_template = str(period_policy.get("current_label_template") or "{period_hint} {label}")
        prior_label_template = str(period_policy.get("prior_label_template") or "{period_hint} {label}")
        base_label = operand_labels[0] if operand_labels else _infer_generic_metric_label(query, "")
        aliases = _build_generic_metric_aliases(base_label)
        unit_family = _infer_generic_unit_family(base_label)
        concept_spec = _infer_generic_concept_spec(base_label, ontology)
        year_tokens = _extract_year_tokens(query, report_scope)
        if year_tokens:
            current_year = year_tokens[0]
            prior_year = year_tokens[1] if len(year_tokens) > 1 else current_year - 1
            return [
                _augment_generic_operand_with_concept(
                    {
                        "label": year_label_template.format(year=current_year, label=base_label),
                        "aliases": aliases,
                        "role": "current_period",
                        "required": True,
                        "period_hint": str(current_year),
                        "unit_family": unit_family,
                    },
                    concept_spec=concept_spec,
                ),
                _augment_generic_operand_with_concept(
                    {
                        "label": year_label_template.format(year=prior_year, label=base_label),
                        "aliases": aliases,
                        "role": "prior_period",
                        "required": True,
                        "period_hint": str(prior_year),
                        "unit_family": unit_family,
                    },
                    concept_spec=concept_spec,
                ),
            ]
        return [
            _augment_generic_operand_with_concept(
                {
                    "label": current_label_template.format(period_hint=current_hint, label=base_label),
                    "aliases": aliases,
                    "role": "current_period",
                    "required": True,
                    "period_hint": current_hint,
                    "unit_family": unit_family,
                },
                concept_spec=concept_spec,
            ),
            _augment_generic_operand_with_concept(
                {
                    "label": prior_label_template.format(period_hint=prior_hint, label=base_label),
                    "aliases": aliases,
                    "role": "prior_period",
                    "required": True,
                    "period_hint": prior_hint,
                    "unit_family": unit_family,
                },
                concept_spec=concept_spec,
            ),
        ]

    rows: List[Dict[str, Any]] = []
    for label in operand_labels:
        aliases = _build_generic_metric_aliases(label)
        concept_spec = _infer_generic_concept_spec(label, ontology)
        rows.append(
            _augment_generic_operand_with_concept(
                {
                    "label": label,
                    "aliases": list(dict.fromkeys(alias for alias in aliases if alias)),
                    "role": "",
                    "required": True,
                    "unit_family": _infer_generic_unit_family(label),
                },
                concept_spec=concept_spec,
            )
        )
    return rows


def _infer_generic_metric_label(query: str, topic: str) -> str:
    quoted = _extract_quoted_metric_labels(query)
    if len(quoted) == 1:
        return quoted[0]
    operand_labels = _extract_generic_operand_labels(query)
    if operand_labels:
        return operand_labels[0]
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    return _clean_metric_label(topic) or str(period_policy.get("fallback_metric_label") or "")


def _build_generic_retrieval_queries(
    query: str,
    metric_label: str,
    operand_specs: List[Dict[str, Any]],
    preferred_sections: List[str],
    report_scope: Dict[str, Any],
    constraints: Optional[Dict[str, str]] = None,
) -> List[str]:
    def _collapse_duplicate_query_tokens(raw: str) -> str:
        pieces = [piece for piece in _normalise_spaces(raw).split(" ") if piece]
        collapsed: List[str] = []
        for piece in pieces:
            if collapsed and collapsed[-1] == piece:
                continue
            collapsed.append(piece)
        return " ".join(collapsed).strip()

    def _strip_leading_period_prefix(text: str) -> str:
        return _normalise_spaces(re.sub(rf"^{KOREAN_PERIOD_PREFIX_RE_FRAGMENT}\s+", "", _normalise_spaces(text or "")))

    def _surface_query_variants(text: str) -> List[str]:
        normalized = _strip_leading_period_prefix(text)
        if not normalized:
            return []
        variants = [normalized]
        tokens = normalized.split()
        if len(tokens) >= 2:
            variants.append(" ".join(tokens[:-1]))
        for candidate in list(variants):
            if re.search(r"[가-힣]", candidate) and " " in candidate:
                variants.append(re.sub(r"\s+", "", candidate))
        return list(dict.fromkeys(item for item in variants if item))

    def _query_surfaces_for_operand(operand: Dict[str, Any]) -> List[str]:
        label = str(operand.get("label") or "").strip()
        surfaces: List[str] = []
        surfaces.extend(_surface_query_variants(label))
        for alias in list(operand.get("aliases") or [])[:3]:
            surfaces.extend(_surface_query_variants(str(alias).strip()))
        for surface in _lookup_query_surface_preferences(operand):
            surfaces.extend(_surface_query_variants(surface))
        return list(dict.fromkeys(surface for surface in surfaces if surface))

    queries = [query]
    year = str(report_scope.get("year") or "").strip()
    year_prefix = f"{year}년 " if year else ""
    fallback_period_focus = str((constraints or {}).get("period_focus") or "unknown").strip()

    def _year_for_operand(operand: Dict[str, Any]) -> str:
        period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
        prior_period_hints = set(str(item) for item in (period_policy.get("prior_period_hints") or ()) if str(item))
        if not year.isdigit():
            return year
        role = str(operand.get("role") or "").strip()
        period_hint = str(operand.get("period_hint") or "").strip()
        if role == "prior_period" or period_hint in prior_period_hints:
            return str(int(year) - 1)
        if role == "current_period":
            return year
        if fallback_period_focus == "prior":
            return str(int(year) - 1)
        return year

    def _prefix_for_operand(operand: Dict[str, Any]) -> str:
        period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
        year_suffix_template = str(period_policy.get("year_suffix_template") or "{year}")
        current_hint = str(period_policy.get("current_period_hint") or "current")
        prior_hint = str(period_policy.get("prior_period_hint") or "prior")
        operand_year = _year_for_operand(operand)
        pieces: List[str] = []
        if operand_year:
            pieces.append(year_suffix_template.format(year=operand_year))
        period_hint = str(operand.get("period_hint") or "").strip()
        role = str(operand.get("role") or "").strip()
        if not period_hint:
            if role == "current_period":
                period_hint = current_hint
            elif role == "prior_period":
                period_hint = prior_hint
        normalized_period_hint = _normalise_spaces(period_hint)
        if operand_year and normalized_period_hint in {operand_year, year_suffix_template.format(year=operand_year)}:
            period_hint = ""
        if period_hint:
            pieces.append(period_hint)
        return _normalise_spaces(" ".join(pieces))

    if len(operand_specs) == 2:
        left = dict(operand_specs[0] or {})
        right = dict(operand_specs[1] or {})
        left_role = str(left.get("role") or "").strip()
        right_role = str(right.get("role") or "").strip()
        left_concept = str(left.get("concept") or "").strip()
        right_concept = str(right.get("concept") or "").strip()
        left_label_base = _strip_leading_period_prefix(str(left.get("label") or ""))
        right_label_base = _strip_leading_period_prefix(str(right.get("label") or ""))
        same_metric_pair = bool(
            (left_concept and left_concept == right_concept)
            or (left_label_base and left_label_base == right_label_base)
        )
        if (
            {left_role, right_role} == {"current_period", "prior_period"}
            and same_metric_pair
        ):
            left_year = _year_for_operand(left)
            right_year = _year_for_operand(right)
            alias_candidates = [str(item).strip() for item in (left.get("aliases") or []) if str(item).strip()]
            shared_label = _strip_leading_period_prefix(alias_candidates[0] if alias_candidates else "") or _strip_leading_period_prefix(
                str(left.get("label") or "")
            )
            if shared_label:
                year_suffix_template = str(dict(GENERIC_PERIOD_OPERAND_POLICY).get("year_suffix_template") or "{year}")
                compact_bits = [
                    bit
                    for bit in (
                        year_suffix_template.format(year=left_year) if left_year else "",
                        year_suffix_template.format(year=right_year) if right_year else "",
                        shared_label,
                    )
                    if bit
                ]
                queries.append(_collapse_duplicate_query_tokens(" ".join(compact_bits)))
                for section in preferred_sections[:2]:
                    queries.append(_collapse_duplicate_query_tokens(f"{' '.join(compact_bits)} {section}"))
                for alias in list(left.get("aliases") or [])[:2]:
                    alias_text = _strip_leading_period_prefix(str(alias).strip())
                    if alias_text and alias_text != shared_label:
                        alias_bits = [
                            bit
                            for bit in (
                                year_suffix_template.format(year=left_year) if left_year else "",
                                year_suffix_template.format(year=right_year) if right_year else "",
                                alias_text,
                            )
                            if bit
                        ]
                        queries.append(_collapse_duplicate_query_tokens(" ".join(alias_bits)))
                        for section in preferred_sections[:2]:
                            queries.append(_collapse_duplicate_query_tokens(f"{' '.join(alias_bits)} {section}"))
        else:
            numerator = left if left_role.startswith("numerator") else right if right_role.startswith("numerator") else {}
            denominator = left if left_role.startswith("denominator") else right if right_role.startswith("denominator") else {}
            if numerator and denominator:
                numerator_label = _strip_leading_period_prefix(str(numerator.get("label") or ""))
                denominator_label = _strip_leading_period_prefix(str(denominator.get("label") or ""))
                pair_queries = [
                    _collapse_duplicate_query_tokens(" ".join(bit for bit in (year_prefix.strip(), denominator_label, numerator_label) if bit)),
                    _collapse_duplicate_query_tokens(" ".join(bit for bit in (year_prefix.strip(), numerator_label, denominator_label) if bit)),
                ]
                for pair_query in pair_queries:
                    if pair_query:
                        queries.append(pair_query)
                        for section in preferred_sections[:3]:
                            queries.append(_collapse_duplicate_query_tokens(f"{pair_query} {section}"))

    metric_query_surfaces = _surface_query_variants(metric_label)
    if metric_query_surfaces:
        queries.append(_collapse_duplicate_query_tokens(f"{year_prefix}{metric_query_surfaces[0]}"))
        for section in preferred_sections[:4]:
            queries.append(_collapse_duplicate_query_tokens(f"{year_prefix}{metric_query_surfaces[0]} {section}"))
        for surface in metric_query_surfaces[1:]:
            queries.append(_collapse_duplicate_query_tokens(f"{year_prefix}{surface}"))
            for section in preferred_sections[:2]:
                queries.append(_collapse_duplicate_query_tokens(f"{year_prefix}{surface} {section}"))
    for operand in operand_specs:
        label = str(operand.get("label") or "").strip()
        if not label:
            continue
        operand_prefix = _prefix_for_operand(operand) or year_prefix.strip()
        segment_label = _operand_segment_label(operand)
        normalized_label = _strip_leading_period_prefix(label)
        queries.append(_collapse_duplicate_query_tokens(f"{operand_prefix} {normalized_label or label}"))
        for surface in _query_surfaces_for_operand(operand):
            normalized_surface = surface
            if segment_label and normalized_surface and segment_label not in normalized_surface:
                normalized_surface = _normalise_spaces(f"{segment_label} {normalized_surface}")
            queries.append(_collapse_duplicate_query_tokens(f"{operand_prefix} {normalized_surface}"))
            for section in preferred_sections[:2]:
                queries.append(_collapse_duplicate_query_tokens(f"{operand_prefix} {normalized_surface} {section}"))
        for section in preferred_sections[:2]:
            queries.append(_collapse_duplicate_query_tokens(f"{operand_prefix} {normalized_label or label} {section}"))
    return list(dict.fromkeys(item for item in queries if item))


def _planner_intent_cues(ontology: Any, operation_family: str) -> List[str]:
    guidance = dict(getattr(ontology, "planner_guidance", {}) or {})
    intent_cues = dict(guidance.get("intent_cues") or {})
    return [
        str(item).strip()
        for item in (intent_cues.get(operation_family) or [])
        if str(item).strip()
    ]


def _infer_operation_family_from_query(query: str, ontology: Any) -> str:
    text = _normalise_spaces(query).lower()
    if not text:
        return "single_value"

    generic_operand_labels = _extract_generic_operand_labels(query)
    for policy in OPERATION_FAMILY_QUERY_POLICIES:
        markers = tuple(str(marker).lower() for marker in (policy.get("markers") or ()) if str(marker))
        if any(marker in text for marker in markers):
            return str(policy.get("operation_family") or "single_value")
    if _is_percent_point_difference_query(query):
        return "difference"
    if _is_single_metric_period_comparison(query, generic_operand_labels):
        return "difference"
    if _is_ratio_percent_query(query):
        return "ratio"
    if any(cue.lower() in text for cue in _planner_intent_cues(ontology, "growth_rate")):
        return "growth_rate"
    if any(cue.lower() in text for cue in _planner_intent_cues(ontology, "ratio")):
        return "ratio"
    if any(cue.lower() in text for cue in _planner_intent_cues(ontology, "difference")):
        return "difference"
    if any(cue.lower() in text for cue in _planner_intent_cues(ontology, "sum")):
        return "sum"
    return "single_value"


def _concept_alias_position(spec: Dict[str, Any], text: str) -> float:
    haystack = _normalise_spaces(text).lower()
    positions: List[int] = []
    aliases = [
        str(spec.get("name") or "").strip(),
        *(spec.get("aliases") or []),
        *(spec.get("keywords") or []),
    ]
    for alias in aliases:
        needle = _normalise_spaces(alias).lower()
        if not needle:
            continue
        position = haystack.find(needle)
        if position >= 0:
            positions.append(position)
    return float(min(positions)) if positions else math.inf


def _order_concept_specs_by_query(concept_specs: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    indexed: List[tuple[float, int, Dict[str, Any]]] = []
    for index, spec in enumerate(concept_specs):
        indexed.append((_concept_alias_position(spec, query), index, spec))
    indexed.sort(key=lambda item: (item[0], item[1]))
    return [spec for _position, _index, spec in indexed]


def _expand_group_concept_specs(
    concept_specs: List[Dict[str, Any]],
    role_hints: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    expanded: List[Dict[str, Any]] = []
    role_hints = list(role_hints or [])
    for index, spec in enumerate(concept_specs):
        current_role = role_hints[index] if index < len(role_hints) else str(spec.get("role") or "").strip()
        member_specs = list(spec.get("member_specs") or [])
        if member_specs:
            for member_spec in member_specs:
                expanded_spec = dict(member_spec)
                if current_role and not str(expanded_spec.get("role") or "").strip():
                    expanded_spec["role"] = current_role
                expanded.append(expanded_spec)
            continue
        expanded_spec = dict(spec)
        if current_role and not str(expanded_spec.get("role") or "").strip():
            expanded_spec["role"] = current_role
        expanded.append(expanded_spec)

    deduped: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for spec in expanded:
        concept_key = str(spec.get("concept") or "").strip()
        role = str(spec.get("role") or "").strip()
        dedupe_key = (concept_key, role)
        if concept_key and dedupe_key in seen:
            continue
        if concept_key:
            seen.add(dedupe_key)
        deduped.append(spec)
    return deduped


def _normalize_operation_roles(operation_family: str, roles: List[str]) -> List[str]:
    normalized = list(roles)
    if operation_family == "ratio":
        counters = {"numerator": 0, "denominator": 0}
        for index, role in enumerate(normalized):
            if role.startswith("numerator"):
                counters["numerator"] += 1
                normalized[index] = f"numerator_{counters['numerator']}"
            elif role.startswith("denominator"):
                counters["denominator"] += 1
                normalized[index] = f"denominator_{counters['denominator']}"
    elif operation_family == "sum":
        counter = 0
        for index, role in enumerate(normalized):
            if role.startswith("addend"):
                counter += 1
                normalized[index] = f"addend_{counter}"
    return normalized


def _build_concept_period_operands(
    spec: Dict[str, Any],
    query: str,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    current_hint = str(period_policy.get("current_period_hint") or "current")
    prior_hint = str(period_policy.get("prior_period_hint") or "prior")
    year_label_template = str(period_policy.get("year_label_template") or "{year} {label}")
    current_label_template = str(period_policy.get("current_label_template") or "{period_hint} {label}")
    prior_label_template = str(period_policy.get("prior_label_template") or "{period_hint} {label}")
    label = str(spec.get("name") or "").strip()
    concept = str(spec.get("concept") or "").strip()
    aliases = list(dict.fromkeys([label, *(spec.get("aliases") or [])]))
    keywords = list(dict.fromkeys(spec.get("keywords") or []))
    preferred_sections = list(dict.fromkeys(spec.get("preferred_sections") or []))
    preferred_statement_types = list(dict.fromkeys(spec.get("preferred_statement_types") or []))
    binding_policy = dict(spec.get("binding_policy") or {})
    surface_contract = dict(spec.get("surface_contract") or {})
    year_tokens = _extract_year_tokens(query, report_scope)
    if year_tokens:
        current_year = year_tokens[0]
        prior_year = year_tokens[1] if len(year_tokens) > 1 else current_year - 1
        return [
            {
                "label": year_label_template.format(year=current_year, label=label),
                "concept": concept,
                "aliases": aliases,
                "keywords": keywords,
                "role": "current_period",
                "required": True,
                "period_hint": str(current_year),
                "preferred_sections": preferred_sections,
                "preferred_statement_types": preferred_statement_types,
                "binding_policy": binding_policy,
                "unit_family": str(spec.get("unit_family") or "").strip(),
                "surface_contract": surface_contract,
            },
            {
                "label": year_label_template.format(year=prior_year, label=label),
                "concept": concept,
                "aliases": aliases,
                "keywords": keywords,
                "role": "prior_period",
                "required": True,
                "period_hint": str(prior_year),
                "preferred_sections": preferred_sections,
                "preferred_statement_types": preferred_statement_types,
                "binding_policy": binding_policy,
                "unit_family": str(spec.get("unit_family") or "").strip(),
                "surface_contract": surface_contract,
            },
        ]
    return [
        {
            "label": current_label_template.format(period_hint=current_hint, label=label),
            "concept": concept,
            "aliases": aliases,
            "keywords": keywords,
            "role": "current_period",
            "required": True,
            "period_hint": current_hint,
            "preferred_sections": preferred_sections,
            "preferred_statement_types": preferred_statement_types,
            "binding_policy": binding_policy,
            "unit_family": str(spec.get("unit_family") or "").strip(),
            "surface_contract": surface_contract,
        },
        {
            "label": prior_label_template.format(period_hint=prior_hint, label=label),
            "concept": concept,
            "aliases": aliases,
            "keywords": keywords,
            "role": "prior_period",
            "required": True,
            "period_hint": prior_hint,
            "preferred_sections": preferred_sections,
            "preferred_statement_types": preferred_statement_types,
            "binding_policy": binding_policy,
            "unit_family": str(spec.get("unit_family") or "").strip(),
            "surface_contract": surface_contract,
        },
    ]


def _assign_ratio_roles_to_concepts(query: str, concept_specs: List[Dict[str, Any]]) -> List[str]:
    ordered = _order_concept_specs_by_query(concept_specs, query)
    roles = [""] * len(ordered)

    def _assign(indices: List[int], prefix: str) -> None:
        for offset, index in enumerate(indices, start=1):
            roles[index] = f"{prefix}_{offset}"

    def _candidate_score(spec: Dict[str, Any], target_label: str) -> tuple[int, int, float]:
        normalized_target = _normalise_spaces(target_label)
        alias_values = [
            str(spec.get("name") or "").strip(),
            *(spec.get("aliases") or []),
            *(spec.get("keywords") or []),
        ]
        normalized_aliases = [
            _normalise_spaces(alias)
            for alias in alias_values
            if _normalise_spaces(alias)
        ]
        exact = any(normalized_target == alias for alias in normalized_aliases)
        overlap = any(
            normalized_target in alias or alias in normalized_target
            for alias in normalized_aliases
        )
        if not exact and not overlap:
            return (0, 0, math.inf)
        best_position = _concept_alias_position(spec, target_label)
        best_alias_length = max((len(alias) for alias in normalized_aliases), default=0)
        return (2 if exact else 1, best_alias_length, best_position)

    share_specs = _extract_generic_ratio_operand_specs(query)
    if share_specs:
        assigned: set[int] = set()
        for share_spec in share_specs:
            target_label = str(share_spec.get("label") or "").strip()
            target_role = str(share_spec.get("role") or "").strip()
            candidates: List[tuple[int, int, float, int]] = []
            for index, spec in enumerate(ordered):
                if index in assigned:
                    continue
                score = _candidate_score(spec, target_label)
                if score[0] <= 0:
                    continue
                candidates.append((*score, index))
            if not candidates:
                continue
            candidates.sort(key=lambda item: (item[0], item[1], -item[2]), reverse=True)
            chosen_index = candidates[0][3]
            roles[chosen_index] = target_role
            assigned.add(chosen_index)
        if any(role.startswith("numerator") for role in roles) and any(role.startswith("denominator") for role in roles):
            return roles

    text = str(query or "")
    if "대비" in text:
        before_text, after_text = text.split("대비", 1)
        denominator_indices = [
            index
            for index, spec in enumerate(ordered)
            if _concept_alias_position(spec, before_text) < math.inf
        ]
        numerator_indices = [
            index
            for index, spec in enumerate(ordered)
            if _concept_alias_position(spec, after_text) < math.inf
        ]
        if denominator_indices and numerator_indices:
            _assign(numerator_indices, "numerator")
            _assign(denominator_indices, "denominator")
            return roles

    if "/" in text:
        left_text, right_text = text.split("/", 1)
        numerator_indices = [
            index
            for index, spec in enumerate(ordered)
            if _concept_alias_position(spec, left_text) < math.inf
        ]
        denominator_indices = [
            index
            for index, spec in enumerate(ordered)
            if _concept_alias_position(spec, right_text) < math.inf
        ]
        if numerator_indices and denominator_indices:
            _assign(numerator_indices, "numerator")
            _assign(denominator_indices, "denominator")
            return roles

    if len(ordered) == 2:
        roles[0] = "numerator_1"
        roles[1] = "denominator_1"
    return roles


def _extract_segment_labels_from_query(query: str, report_scope: Dict[str, Any]) -> List[str]:
    text = _normalise_spaces(query)
    if not text:
        return []

    blocked_tokens = {
        str(report_scope.get("company") or "").strip(),
        str(report_scope.get("report_type") or "").strip(),
        *KOREAN_SEGMENT_LABEL_REPORT_TERMS,
        *KOREAN_SEGMENT_LABEL_SCOPE_TOKENS,
        *KOREAN_SEGMENT_LABEL_BLOCKED_TOKENS,
    }
    blocked_exact_labels = set(KOREAN_SEGMENT_LABEL_BLOCKED_EXACT_LABELS)

    def _valid_label(label: str) -> str:
        normalized = _normalise_spaces(label)
        normalized = _normalise_spaces(re.sub(KOREAN_SEGMENT_LABEL_PERIOD_PREFIX_RE_FRAGMENT, "", normalized))
        normalized = _normalise_spaces(re.sub(KOREAN_SEGMENT_LABEL_TRAILING_PERIOD_RE_FRAGMENT, "", normalized))
        if not normalized:
            return ""
        if normalized in blocked_tokens:
            return ""
        if normalized in blocked_exact_labels:
            return ""
        if any(marker in normalized for marker in KOREAN_SEGMENT_LABEL_MARKERS if marker != "segment"):
            return ""
        if any(token in normalized for token in KOREAN_SEGMENT_LABEL_REPORT_TERMS):
            return ""
        if re.fullmatch(KOREAN_SEGMENT_LABEL_PERIOD_RE_FRAGMENT, normalized):
            return ""
        if len(normalized) > 40:
            return ""
        return normalized

    labels: List[str] = []

    if any(marker in text for marker in KOREAN_SEGMENT_LABEL_MARKERS):
        for match in re.finditer(KOREAN_SEGMENT_LABEL_PAREN_RE_FRAGMENT, text, flags=re.IGNORECASE):
            normalized = _valid_label(match.group(1))
            if normalized:
                labels.append(normalized)
        segment_anchor = ""
        for marker in KOREAN_SEGMENT_LABEL_ANCHORS:
            if marker in text:
                segment_anchor = marker
                break
        if segment_anchor:
            prefix = text.split(segment_anchor, 1)[0].strip()
            for boundary in KOREAN_SEGMENT_LABEL_BOUNDARIES:
                if boundary in prefix:
                    prefix = prefix.rsplit(boundary, 1)[-1].strip()
            prefix = re.sub(r"\b20\d{2}\b", " ", prefix)
            raw_parts = re.split(KOREAN_SEGMENT_LABEL_SPLIT_RE_FRAGMENT, prefix)
            for part in raw_parts:
                normalized = _valid_label(part)
                if normalized:
                    labels.append(normalized)

    for pattern in KOREAN_SEGMENT_LABEL_TOKEN_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            normalized = _valid_label(match.group(1))
            if normalized:
                labels.append(normalized)

    return list(dict.fromkeys(label for label in labels if label))


def _expand_segment_sum_specs(
    ordered_specs: List[Dict[str, Any]],
    query: str,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if len(ordered_specs) != 1:
        return ordered_specs

    segment_labels = _extract_segment_labels_from_query(query, report_scope)
    if len(segment_labels) < 2:
        return ordered_specs

    base_spec = dict(ordered_specs[0])
    base_name = str(base_spec.get("name") or "").strip()
    expanded: List[Dict[str, Any]] = []
    for index, segment_label in enumerate(segment_labels, start=1):
        spec = dict(base_spec)
        spec["name"] = f"{segment_label} {base_name}".strip()
        aliases = list(spec.get("aliases") or [])
        spec["aliases"] = list(dict.fromkeys([spec["name"], segment_label, base_name, *aliases]))
        binding_policy = dict(spec.get("binding_policy") or {})
        binding_policy["segment_label"] = segment_label
        spec["binding_policy"] = binding_policy
        spec["role"] = f"addend_{index}"
        expanded.append(spec)
    return expanded


def _build_concept_required_operands(
    query: str,
    report_scope: Dict[str, Any],
    concept_specs: List[Dict[str, Any]],
    operation_family: str,
) -> List[Dict[str, Any]]:
    ordered_specs = list(concept_specs)
    if not ordered_specs:
        return []

    raw_explicit_roles = [str(spec.get("role") or "").strip() for spec in ordered_specs]
    preserve_planner_order = False
    if operation_family == "ratio":
        preserve_planner_order = any(role.startswith("numerator") for role in raw_explicit_roles) and any(
            role.startswith("denominator") for role in raw_explicit_roles
        )
    elif operation_family == "sum":
        preserve_planner_order = any(role.startswith("addend") for role in raw_explicit_roles)
    elif operation_family == "difference":
        preserve_planner_order = any(role in {"minuend", "subtrahend", "current_period", "prior_period"} for role in raw_explicit_roles)
    elif operation_family == "growth_rate":
        preserve_planner_order = any(role in {"current_period", "prior_period"} for role in raw_explicit_roles)

    if not preserve_planner_order:
        ordered_specs = _order_concept_specs_by_query(concept_specs, query)
        raw_explicit_roles = [str(spec.get("role") or "").strip() for spec in ordered_specs]

    if len(ordered_specs) == 1 and operation_family in {"difference", "growth_rate"}:
        expanded_single = _expand_group_concept_specs(ordered_specs, raw_explicit_roles)
        if len(expanded_single) == 1:
            return _build_concept_period_operands(expanded_single[0], query, report_scope)
        return []

    if (
        len(ordered_specs) == 1
        and not raw_explicit_roles
        and _is_single_metric_period_comparison(query, [str(ordered_specs[0].get("name") or "").strip()])
    ):
        expanded_single = _expand_group_concept_specs(ordered_specs, raw_explicit_roles)
        if len(expanded_single) == 1:
            return _build_concept_period_operands(expanded_single[0], query, report_scope)
        return []

    role_hints = raw_explicit_roles
    if operation_family == "ratio":
        if any(role.startswith("numerator") for role in raw_explicit_roles) and any(role.startswith("denominator") for role in raw_explicit_roles):
            role_hints = raw_explicit_roles
        else:
            role_hints = _assign_ratio_roles_to_concepts(query, ordered_specs)
        if not any(role.startswith("numerator") for role in role_hints) or not any(role.startswith("denominator") for role in role_hints):
            return []
        if _extract_generic_ratio_operand_specs(query) and any(not role for role in role_hints):
            paired = [
                (spec, role)
                for spec, role in zip(ordered_specs, role_hints)
                if role.startswith("numerator") or role.startswith("denominator")
            ]
            if paired:
                ordered_specs = [spec for spec, _role in paired]
                role_hints = [role for _spec, role in paired]

    if operation_family == "sum" and len(ordered_specs) == 1:
        ordered_specs = _expand_segment_sum_specs(ordered_specs, query, report_scope)
        role_hints = [str(spec.get("role") or "").strip() for spec in ordered_specs]

    ordered_specs = _expand_group_concept_specs(ordered_specs, role_hints)
    if not ordered_specs:
        return []

    explicit_roles = _normalize_operation_roles(
        operation_family,
        [str(spec.get("role") or "").strip() for spec in ordered_specs],
    )
    if operation_family == "ratio":
        if not any(role.startswith("numerator") for role in explicit_roles) or not any(role.startswith("denominator") for role in explicit_roles):
            return []

    if operation_family in {"ratio", "sum"}:
        deduped_specs: List[Dict[str, Any]] = []
        deduped_roles: List[str] = []
        seen_keys: set[Any] = set()
        for spec, role in zip(ordered_specs, explicit_roles):
            concept_key = str(spec.get("concept") or "").strip()
            dedupe_key: Any = concept_key
            if operation_family in {"ratio", "sum"}:
                # Sum and ratio tasks can legitimately use the same concept more than
                # once when operands differ by role family, segment, or scope (for
                # example, segment operating income / company operating income).
                # Collapse group/member duplicate matches that land in the same role
                # family, but preserve numerator-vs-denominator distinctions.
                binding_policy = dict(spec.get("binding_policy") or {})
                normalized_role = str(role or "").strip()
                if operation_family == "ratio":
                    if normalized_role.startswith("numerator"):
                        normalized_role = "numerator"
                    elif normalized_role.startswith("denominator"):
                        normalized_role = "denominator"
                dedupe_key = (
                    concept_key,
                    normalized_role,
                    _normalise_spaces(str(binding_policy.get("segment_label") or "")),
                )
            if concept_key and dedupe_key in seen_keys:
                continue
            if concept_key:
                seen_keys.add(dedupe_key)
            deduped_specs.append(spec)
            deduped_roles.append(role)
        ordered_specs = deduped_specs
        explicit_roles = _normalize_operation_roles(operation_family, deduped_roles)

    operands: List[Dict[str, Any]] = []
    for index, spec in enumerate(ordered_specs, start=1):
        role = ""
        if operation_family == "ratio":
            role = explicit_roles[index - 1]
        elif operation_family == "sum":
            role = explicit_roles[index - 1] or f"addend_{index}"
        elif operation_family == "difference" and len(ordered_specs) >= 2:
            role = explicit_roles[index - 1] or ("minuend" if index == 1 else "subtrahend")
        elif operation_family == "growth_rate" and len(ordered_specs) >= 2:
            role = explicit_roles[index - 1] or ("current_period" if index == 1 else "prior_period")
        elif operation_family in {"lookup", "single_value"}:
            role = explicit_roles[index - 1]
        operands.append(
            {
                "label": str(spec.get("name") or "").strip(),
                "concept": str(spec.get("concept") or "").strip(),
                "aliases": list(dict.fromkeys([str(spec.get("name") or "").strip(), *(spec.get("aliases") or [])])),
                "keywords": list(dict.fromkeys(spec.get("keywords") or [])),
                "role": role,
                "required": True,
                "preferred_sections": list(dict.fromkeys(spec.get("preferred_sections") or [])),
                "preferred_statement_types": list(dict.fromkeys(spec.get("preferred_statement_types") or [])),
                "binding_policy": dict(spec.get("binding_policy") or {}),
                "unit_family": str(spec.get("unit_family") or "").strip(),
                "surface_contract": dict(spec.get("surface_contract") or {}),
            }
        )
    return operands


def _build_concept_metric_label(
    query: str,
    concept_specs: List[Dict[str, Any]],
    operation_family: str,
) -> str:
    ordered_specs = _order_concept_specs_by_query(concept_specs, query)
    labels = [
        str(spec.get("name") or spec.get("label") or "").strip()
        for spec in ordered_specs
        if str(spec.get("name") or spec.get("label") or "").strip()
    ]
    label_policy = dict(CONCEPT_METRIC_LABEL_POLICY)
    templates = dict(label_policy.get("operation_templates") or {})
    label_joiner = str(label_policy.get("label_joiner") or " + ")
    labels_joined = label_joiner.join(labels)
    if operation_family == "ratio" and labels:
        return str(templates.get("ratio") or "{labels_joined}").format(labels_joined=labels_joined)
    if operation_family == "sum" and labels:
        return str(templates.get("sum") or "{labels_joined}").format(labels_joined=labels_joined)
    if operation_family == "difference" and labels:
        if len(labels) >= 2:
            return str(templates.get("difference_two") or "{first_label} {second_label}").format(
                first_label=labels[0],
                second_label=labels[1],
            )
        return str(templates.get("difference_one") or "{label}").format(label=labels[0])
    if operation_family == "growth_rate" and labels:
        return str(templates.get("growth_rate") or "{label}").format(label=labels[0])
    if labels:
        return labels[0]
    return _clean_metric_label(query) or str(label_policy.get("fallback_label") or "")


def _build_concept_task_constraints(
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    operand_specs: Optional[List[Dict[str, Any]]] = None,
    operation_family: str = "",
) -> Dict[str, str]:
    guidance = dict(getattr(ontology, "planner_guidance", {}) or {})
    defaults = dict(guidance.get("dimension_defaults") or {})
    consolidation_scope = _desired_consolidation_scope(query, report_scope)
    if consolidation_scope == "unknown":
        consolidation_scope = str(defaults.get("consolidation_scope") or "unknown")
    period_focus = _infer_period_focus(query, str(defaults.get("period_focus") or "unknown"))
    if operand_specs:
        period_focus = _task_period_focus_from_operands(operation_family, operand_specs, period_focus)
    constraint_policy = dict(TASK_CONSTRAINT_POLICY)
    segment_markers = tuple(str(item) for item in (constraint_policy.get("segment_markers") or ()) if str(item))
    normalized_query = _normalise_spaces(query)
    return {
        "consolidation_scope": str(consolidation_scope or "unknown"),
        "period_focus": str(period_focus or "unknown"),
        "entity_scope": str(defaults.get("entity_scope") or "company"),
        "segment_scope": "segment" if any(marker in normalized_query for marker in segment_markers) else "none",
    }


def _build_explicit_ratio_definition_task(
    *,
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    concept_specs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    text = _normalise_spaces(query)
    compact_text = re.sub(r"\s+", "", text)
    ratio_policy = dict(EXPLICIT_RATIO_DEFINITION_POLICY)
    definition_marker = str(ratio_policy.get("definition_marker") or "")
    ratio_markers = tuple(str(item) for item in (ratio_policy.get("ratio_markers") or ()) if str(item))
    if not compact_text or not definition_marker or definition_marker not in compact_text:
        return None
    if not any(marker in compact_text for marker in ratio_markers):
        return None

    mentions: List[Dict[str, Any]] = []
    seen_mentions: set[tuple[str, int, int]] = set()
    for spec in concept_specs:
        concept_key = _normalise_spaces(str(spec.get("concept") or ""))
        if not concept_key:
            continue
        base_label = str(spec.get("name") or "").strip()
        for surface in _metric_scope_surfaces(spec, base_label):
            compact_surface = re.sub(r"\s+", "", _normalise_spaces(surface))
            if len(compact_surface) < 2:
                continue
            for match in re.finditer(re.escape(compact_surface), compact_text, flags=re.IGNORECASE):
                key = (concept_key, match.start(), match.end())
                if key in seen_mentions:
                    continue
                seen_mentions.add(key)
                mentions.append(
                    {
                        "start": match.start(),
                        "end": match.end(),
                        "length": match.end() - match.start(),
                        "spec": dict(spec),
                    }
                )
    if len(mentions) < 2:
        return None

    for ratio_match in re.finditer(re.escape(definition_marker), compact_text):
        marker_start = ratio_match.start()
        marker_end = ratio_match.end()
        next_ratio_terms = [
            index
            for term in ratio_markers
            for index in [compact_text.find(term, marker_end)]
            if index >= 0
        ]
        ratio_end = min(next_ratio_terms) if next_ratio_terms else len(compact_text)
        left_candidates = [item for item in mentions if int(item["end"]) <= marker_start]
        right_candidates = [
            item
            for item in mentions
            if int(item["start"]) >= marker_end and int(item["start"]) <= ratio_end
        ]
        if not left_candidates or not right_candidates:
            continue
        right_concepts = {
            _normalise_spaces(str(dict(item.get("spec") or {}).get("concept") or ""))
            for item in right_candidates
            if _normalise_spaces(str(dict(item.get("spec") or {}).get("concept") or ""))
        }
        if len(right_concepts) > 1:
            # Multi-component right-hand sides need the generic operand builder so
            # sums such as "A 대비 B, C, D 비중" keep every required numerator.
            continue
        left = sorted(
            left_candidates,
            key=lambda item: (marker_start - int(item["end"]), -int(item["length"])),
        )[0]
        right = sorted(
            right_candidates,
            key=lambda item: (int(item["start"]) - marker_end, -int(item["length"])),
        )[0]
        left_spec = dict(left.get("spec") or {})
        right_spec = dict(right.get("spec") or {})
        if _normalise_spaces(str(left_spec.get("concept") or "")) == _normalise_spaces(
            str(right_spec.get("concept") or "")
        ):
            continue

        denominator = {**left_spec, "role": "denominator_1"}
        numerator = {**right_spec, "role": "numerator_1"}
        operand_specs = _build_concept_required_operands(
            query,
            report_scope,
            [denominator, numerator],
            "ratio",
        )
        if not operand_specs:
            continue
        denominator_label = str(denominator.get("name") or "").strip()
        numerator_label = str(numerator.get("name") or "").strip()
        metric_label = (
            str(ratio_policy.get("metric_label_template") or "").format(
                denominator_label=denominator_label,
                numerator_label=numerator_label,
            )
            if denominator_label and numerator_label
            else _build_concept_metric_label(query, [numerator, denominator], "ratio")
        )
        task = _compose_concept_numeric_task(
            query=query,
            report_scope=report_scope,
            ontology=ontology,
            metric_label=metric_label,
            operation_family="ratio",
            operand_specs=operand_specs,
        )
        if task:
            task["planner_evidence"] = {
                "ratio_definition_marker": definition_marker,
                "denominator_concept": str(denominator.get("concept") or "").strip(),
                "numerator_concept": str(numerator.get("concept") or "").strip(),
            }
            return task
    return None


def _build_concept_numeric_task(
    *,
    query: str,
    topic: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    concept_specs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    explicit_ratio_task = _build_explicit_ratio_definition_task(
        query=query,
        report_scope=report_scope,
        ontology=ontology,
        concept_specs=concept_specs,
    )
    if explicit_ratio_task:
        return explicit_ratio_task
    analysis_task = _build_concept_analysis_task(
        query=query,
        report_scope=report_scope,
        ontology=ontology,
        concept_specs=concept_specs,
    )
    if analysis_task:
        return analysis_task
    group_decomposition_task = _build_group_decomposition_task(
        query=query,
        report_scope=report_scope,
        ontology=ontology,
        concept_specs=concept_specs,
    )
    if group_decomposition_task:
        return group_decomposition_task
    operation_family = _infer_operation_family_from_query(query, ontology)
    operand_specs = _build_concept_required_operands(query, report_scope, concept_specs, operation_family)
    if not operand_specs:
        return None
    metric_label = _build_concept_metric_label(query, operand_specs, operation_family)
    return _compose_concept_numeric_task(
        query=query,
        report_scope=report_scope,
        ontology=ontology,
        metric_label=metric_label,
        operation_family=operation_family,
        operand_specs=operand_specs,
    )


def _metric_scope_surfaces(concept_spec: Dict[str, Any], base_label: str) -> List[str]:
    surfaces: List[str] = []
    for value in (
        base_label,
        str(concept_spec.get("name") or "").strip(),
        *(concept_spec.get("aliases") or []),
        *(concept_spec.get("keywords") or []),
    ):
        normalized = _normalise_spaces(str(value or ""))
        if normalized:
            surfaces.append(normalized)
        compact = re.sub(r"\s+", "", normalized)
        if compact and compact != normalized:
            surfaces.append(compact)
    return list(dict.fromkeys(surface for surface in surfaces if surface))


def _query_clause_spans(text: str) -> List[tuple[int, int]]:
    spans: List[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"(?:[,.;:?!]|\b(?:and|then)\b|그리고|또한|하며|하고)\s*", text, flags=re.IGNORECASE):
        end = match.start()
        if end > start:
            spans.append((start, end))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans or [(0, len(text))]


def _segment_label_shares_metric_clause(query: str, label: str, metric_surfaces: List[str]) -> bool:
    text = _normalise_spaces(query)
    normalized_label = _normalise_spaces(label)
    if not text or not normalized_label or not metric_surfaces:
        return False
    compact_text = re.sub(r"\s+", "", text)
    compact_label = re.sub(r"\s+", "", normalized_label)
    normalized_surfaces = [
        _normalise_spaces(surface)
        for surface in metric_surfaces
        if _normalise_spaces(surface)
    ]
    compact_surfaces = [
        re.sub(r"\s+", "", surface)
        for surface in normalized_surfaces
        if re.sub(r"\s+", "", surface)
    ]

    for start, end in _query_clause_spans(text):
        clause = text[start:end]
        clause_compact = re.sub(r"\s+", "", clause)
        label_in_clause = normalized_label in clause or (compact_label and compact_label in clause_compact)
        if not label_in_clause:
            continue
        if any(surface in clause for surface in normalized_surfaces):
            return True
        if any(surface and surface in clause_compact for surface in compact_surfaces):
            return True

    label_positions = [match.start() for match in re.finditer(re.escape(normalized_label), text, flags=re.IGNORECASE)]
    if not label_positions and compact_label:
        label_positions = [match.start() for match in re.finditer(re.escape(compact_label), compact_text, flags=re.IGNORECASE)]
    if not label_positions:
        return False
    for surface in normalized_surfaces:
        for surface_match in re.finditer(re.escape(surface), text, flags=re.IGNORECASE):
            if any(abs(surface_match.start() - label_pos) <= 24 for label_pos in label_positions):
                return True
    for surface in compact_surfaces:
        for surface_match in re.finditer(re.escape(surface), compact_text, flags=re.IGNORECASE):
            if any(abs(surface_match.start() - label_pos) <= 24 for label_pos in label_positions):
                return True
    return False


def _build_entity_scoped_concept_specs(
    *,
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    operation_family: str,
) -> List[Dict[str, Any]]:
    labels = _extract_segment_labels_from_query(query, report_scope)
    if not labels:
        return []
    if operation_family in {"sum", "difference"} and len(labels) < 2:
        return []
    if operation_family in {"growth_rate", "lookup", "single_value"} and len(labels) < 1:
        return []

    default_metric_policy = dict(HELPER_RUNTIME_POLICY.get("entity_scoped_default_metric") or {})
    default_metric_terms = tuple(str(item) for item in (default_metric_policy.get("query_terms") or ()) if str(item))
    default_metric_label = str(default_metric_policy.get("label") or "").strip()
    normalized_query = _normalise_spaces(query)
    base_label = (
        default_metric_label
        if default_metric_label and any(term in normalized_query for term in default_metric_terms)
        else _infer_generic_metric_label(query, "")
    )
    concept_spec = _infer_generic_concept_spec(base_label, ontology)
    if not concept_spec:
        return []
    metric_surfaces = _metric_scope_surfaces(concept_spec, base_label)
    labels = [
        label
        for label in labels
        if _segment_label_shares_metric_clause(query, label, metric_surfaces)
    ]
    if not labels:
        return []
    if operation_family in {"sum", "difference"} and len(labels) < 2:
        return []

    specs: List[Dict[str, Any]] = []
    for index, label in enumerate(labels, start=1):
        spec = dict(concept_spec)
        spec["name"] = f"{label} {str(concept_spec.get('name') or base_label).strip()}".strip()
        spec["aliases"] = list(
            dict.fromkeys(
                [
                    spec["name"],
                    label,
                    str(concept_spec.get("name") or "").strip(),
                    *(concept_spec.get("aliases") or []),
                ]
            )
        )
        binding_policy = dict(spec.get("binding_policy") or {})
        binding_policy["segment_label"] = label
        spec["binding_policy"] = binding_policy
        if operation_family == "sum":
            spec["role"] = f"addend_{index}"
        elif operation_family == "difference":
            spec["role"] = "minuend" if index == 1 else "subtrahend"
        elif operation_family in {"lookup", "single_value"}:
            spec["role"] = ""
        specs.append(spec)
        if operation_family == "difference" and len(specs) >= 2:
            break
        if operation_family in {"growth_rate", "lookup", "single_value"}:
            break
    return specs


def _build_heuristic_numeric_task(
    *,
    query: str,
    topic: str,
    intent: str,
    report_scope: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    metric_label = _infer_generic_metric_label(query, topic)
    operand_specs = _build_generic_required_operands(query, report_scope)
    preferred_statement_types, preferred_sections = _infer_statement_and_section_hints(query)
    for spec in operand_specs:
        preferred_statement_types.extend(spec.get("preferred_statement_types") or [])
        preferred_sections.extend(spec.get("preferred_sections") or [])
    preferred_statement_types = list(dict.fromkeys(item for item in preferred_statement_types if str(item).strip()))
    preferred_sections = list(dict.fromkeys(item for item in preferred_sections if str(item).strip()))
    operation_family = _infer_operation_family_from_query(query, get_financial_ontology())
    constraints = {
        "consolidation_scope": _desired_consolidation_scope(query, report_scope),
        "period_focus": _infer_period_focus(query, "unknown"),
        "entity_scope": "company",
        "segment_scope": (
            "segment"
            if any(
                str(marker) and str(marker) in _normalise_spaces(query)
                for marker in (TASK_CONSTRAINT_POLICY.get("segment_markers") or ())
            )
            else "none"
        ),
    }
    constraints["period_focus"] = _task_period_focus_from_operands(
        operation_family,
        operand_specs,
        str(constraints.get("period_focus") or "unknown"),
    )
    retrieval_queries = _build_generic_retrieval_queries(
        query=query,
        metric_label=metric_label,
        operand_specs=operand_specs,
        preferred_sections=preferred_sections,
        report_scope=report_scope,
        constraints=constraints,
    )
    if not retrieval_queries:
        return None
    return {
        "task_id": "task_1",
        "metric_family": "generic_numeric",
        "metric_label": metric_label,
        "query": query,
        "operation_family": operation_family,
        "required_operands": operand_specs,
        "preferred_statement_types": preferred_statement_types,
        "preferred_sections": preferred_sections,
        "retrieval_queries": retrieval_queries,
        "constraints": constraints,
    }


def _task_dependency_query_years(task: Dict[str, Any], report_scope: Dict[str, Any]) -> List[int]:
    query_text = " ".join(
        part
        for part in [
            str(task.get("query") or "").strip(),
            str(task.get("metric_label") or "").strip(),
        ]
        if part
    )
    years = _extract_year_tokens(query_text, report_scope)
    if not years:
        scope_year_raw = report_scope.get("year")
        try:
            if scope_year_raw not in (None, ""):
                years = [int(scope_year_raw)]
        except (TypeError, ValueError):
            years = []
    return years


def _task_binding_period_hint(
    operand: Dict[str, Any],
    *,
    task: Dict[str, Any],
    report_scope: Dict[str, Any],
) -> str:
    query_years = _task_dependency_query_years(task, report_scope)
    target_years = _operand_target_years(operand, query_years)
    if target_years:
        return str(target_years[0])
    period_hint = _normalise_spaces(str(operand.get("period_hint") or ""))
    if period_hint:
        return period_hint
    label_match = re.search(r"(20\d{2})", str(operand.get("label") or ""))
    if label_match:
        return str(label_match.group(1))
    return ""


def _task_binding_segment_label(operand: Dict[str, Any]) -> str:
    binding_policy = dict(operand.get("binding_policy") or {})
    return _normalise_spaces(str(binding_policy.get("segment_label") or ""))


def _task_output_slots_for_dependency(
    task: Dict[str, Any],
    *,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    operation_family = str(task.get("operation_family") or "").strip().lower()
    if operation_family not in {"lookup", "single_value"}:
        return []
    outputs: List[Dict[str, Any]] = []
    for operand in list(task.get("required_operands") or []):
        concept = _normalise_spaces(str(operand.get("concept") or ""))
        if not concept:
            continue
        outputs.append(
            {
                "slot": "primary_value",
                "role": _normalise_spaces(str(operand.get("role") or "")) or "primary_value",
                "concept": concept,
                "period": _task_binding_period_hint(dict(operand), task=task, report_scope=report_scope),
                "label": _normalise_spaces(str(operand.get("label") or task.get("metric_label") or "")),
                "segment_label": _task_binding_segment_label(dict(operand)),
            }
        )
    return outputs


def _task_input_bindings_for_dependency(
    task: Dict[str, Any],
    *,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    operation_family = str(task.get("operation_family") or "").strip().lower()
    if operation_family not in {"difference", "growth_rate", "ratio", "sum"}:
        return []
    bindings: List[Dict[str, Any]] = []
    for operand in list(task.get("required_operands") or []):
        concept = _normalise_spaces(str(operand.get("concept") or ""))
        if not concept:
            continue
        bindings.append(
            {
                "role": _normalise_spaces(str(operand.get("role") or "")),
                "concept": concept,
                "period": _task_binding_period_hint(dict(operand), task=task, report_scope=report_scope),
                "label": _normalise_spaces(str(operand.get("label") or "")),
                "preferred_task_id": "",
                "source_slot": "primary_value",
                "source_preference": ["retrieval"],
                "segment_label": _task_binding_segment_label(dict(operand)),
            }
        )
    return bindings


def _next_dependency_task_id(tasks: List[Dict[str, Any]]) -> int:
    max_index = 0
    for task in tasks:
        match = re.match(r"task_(\d+)$", str(task.get("task_id") or "").strip())
        if match:
            max_index = max(max_index, int(match.group(1)))
    return max_index + 1


def _dependency_metric_label(binding: Dict[str, Any]) -> str:
    label = _normalise_spaces(str(binding.get("label") or ""))
    period = _normalise_spaces(str(binding.get("period") or ""))
    if period and label and period not in label:
        return f"{period}년 {label}" if re.fullmatch(r"20\d{2}", period) else f"{period} {label}"
    return label or (f"{period} 값" if period else "조회값")


def _lookup_constraint_from_binding(binding: Dict[str, Any], base_constraints: Dict[str, Any]) -> Dict[str, str]:
    constraints = dict(base_constraints or {})
    role = _normalise_spaces(str(binding.get("role") or ""))
    if role == "current_period":
        constraints["period_focus"] = "current"
    elif role == "prior_period":
        constraints["period_focus"] = "prior"
    else:
        constraints["period_focus"] = str(constraints.get("period_focus") or "unknown")
    return constraints


def _lookup_hints_for_concept_key(concept_key: str) -> Dict[str, Any]:
    normalized_key = _normalise_spaces(str(concept_key or ""))
    if not normalized_key:
        return {}

    ontology = get_financial_ontology()
    concept = ontology.concept(str(concept_key or "").strip())
    if concept:
        return dict(concept.get("lookup_hints") or {})

    for spec in list(getattr(ontology, "all_concept_specs", lambda: [])() or []):
        if bool(spec.get("is_group")):
            continue
        if _normalise_spaces(str(spec.get("concept") or "")) == normalized_key:
            return dict(spec.get("lookup_hints") or {})
    return {}


def _lookup_prefers_canonical_statement_rows(operand: Dict[str, Any]) -> bool:
    if _operand_segment_label(operand):
        return False
    lookup_hints = _lookup_hints_for_concept_key(str(operand.get("concept") or ""))
    return bool(lookup_hints.get("prefer_canonical_statement_rows"))


def _lookup_canonical_statement_preferences(operand: Dict[str, Any]) -> tuple[List[str], List[str]]:
    lookup_hints = _lookup_hints_for_concept_key(str(operand.get("concept") or ""))
    return (
        [
            str(item).strip()
            for item in (lookup_hints.get("canonical_statement_types") or [])
            if str(item).strip()
        ],
        [
            str(item).strip()
            for item in (lookup_hints.get("canonical_sections") or [])
            if str(item).strip()
        ],
    )


def _lookup_query_surface_preferences(operand: Dict[str, Any]) -> List[str]:
    lookup_hints = _lookup_hints_for_concept_key(str(operand.get("concept") or ""))
    return [
        str(item).strip()
        for item in (lookup_hints.get("aggregate_query_surfaces") or [])
        if str(item).strip()
    ]


def _operand_lookup_surface_match(text: str, operand: Dict[str, Any]) -> bool:
    surfaces = _lookup_query_surface_preferences(operand)
    if not surfaces:
        return False
    return _text_has_contract_term(text, surfaces)


def _candidate_has_operand_context_surface(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    context_text = " ".join(
        str(part or "").strip()
        for part in (
            " ".join(str(item).strip() for item in (metadata.get("semantic_aliases") or []) if str(item).strip()),
            " ".join(str(item).strip() for item in (metadata.get("column_headers_chain") or []) if str(item).strip()),
            str(metadata.get("table_row_labels_text") or ""),
            str(metadata.get("table_summary_text") or ""),
            str(metadata.get("row_text") or ""),
            str(candidate.get("text") or ""),
        )
        if str(part or "").strip()
    )
    return _text_has_positive_surface(context_text, operand) or _operand_text_match(context_text, operand)


def _concept_spec_for_key(ontology: Any, key: str) -> Dict[str, Any]:
    concept_key = _normalise_spaces(str(key or ""))
    if not concept_key:
        return {}
    for spec in list(getattr(ontology, "all_concept_specs", lambda: [])() or []):
        if bool(spec.get("is_group")):
            continue
        if _normalise_spaces(str(spec.get("concept") or "")) == concept_key:
            return dict(spec)
    return {}


def _spec_mentions_query(spec: Dict[str, Any], query: str) -> bool:
    text = _normalise_spaces(query)
    if not text:
        return False
    values = [
        str(spec.get("name") or "").strip(),
        *(spec.get("aliases") or []),
        *(spec.get("keywords") or []),
    ]
    return any(
        _normalise_spaces(value) in text
        for value in values
        if _normalise_spaces(value)
    )


def _group_decomposition_query_matches(
    *,
    query: str,
    group_spec: Dict[str, Any],
    hints: Dict[str, Any],
    ontology: Any,
) -> bool:
    text = _normalise_spaces(query)
    if not text:
        return False

    any_of = [
        _normalise_spaces(str(token))
        for token in (hints.get("query_any_of") or [])
        if _normalise_spaces(str(token))
    ]
    all_of = [
        _normalise_spaces(str(token))
        for token in (hints.get("query_all_of") or [])
        if _normalise_spaces(str(token))
    ]
    if any_of and not any(token in text for token in any_of):
        return False
    if all_of and not all(token in text for token in all_of):
        return False

    member_specs = [dict(spec) for spec in (group_spec.get("member_specs") or []) if dict(spec)]
    if bool(hints.get("require_all_member_mentions", False)) and any(
        not _spec_mentions_query(spec, query) for spec in member_specs
    ):
        return False

    denominator_concepts = [
        str(item).strip()
        for item in (hints.get("denominator_concepts") or [])
        if str(item).strip()
    ]
    denominator_specs = [_concept_spec_for_key(ontology, key) for key in denominator_concepts]
    denominator_specs = [spec for spec in denominator_specs if spec]
    if bool(hints.get("require_denominator_mentions", False)) and any(
        not _spec_mentions_query(spec, query) for spec in denominator_specs
    ):
        return False
    return True


def _build_group_decomposition_task(
    *,
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    concept_specs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    for group_spec in _order_concept_specs_by_query(concept_specs, query):
        if not bool(group_spec.get("is_group")):
            continue
        hints = dict(group_spec.get("decomposition_hints") or {})
        if not hints:
            continue
        if not _group_decomposition_query_matches(
            query=query,
            group_spec=group_spec,
            hints=hints,
            ontology=ontology,
        ):
            continue

        operation_family = str(hints.get("preferred_operation") or "").strip() or _infer_operation_family_from_query(query, ontology)
        member_role_prefix = str(hints.get("member_role_prefix") or "numerator").strip() or "numerator"
        member_roles = [
            str(item).strip()
            for item in (hints.get("member_roles") or [])
            if str(item).strip()
        ]
        numerator_specs = [
            {
                **dict(spec),
                "role": member_roles[index - 1] if index <= len(member_roles) else f"{member_role_prefix}_{index}",
            }
            for index, spec in enumerate((group_spec.get("member_specs") or []), start=1)
            if dict(spec)
        ]
        denominator_specs: List[Dict[str, Any]] = []
        for index, concept_key in enumerate((hints.get("denominator_concepts") or []), start=1):
            concept_spec = _concept_spec_for_key(ontology, str(concept_key).strip())
            if not concept_spec:
                continue
            denominator_specs.append({**concept_spec, "role": f"denominator_{index}"})

        denominator_concept_keys = [
            str(item).strip()
            for item in (hints.get("denominator_concepts") or [])
            if str(item).strip()
        ]
        if not numerator_specs:
            continue
        if denominator_concept_keys and not denominator_specs:
            continue

        ordered_specs = [*numerator_specs, *denominator_specs]
        operand_specs = _build_concept_required_operands(
            query,
            report_scope,
            ordered_specs,
            operation_family,
        )
        if not operand_specs:
            continue

        metric_label = str(hints.get("metric_label") or "").strip() or _build_concept_metric_label(
            query,
            ordered_specs,
            operation_family,
        )
        task = _compose_concept_numeric_task(
            query=query,
            report_scope=report_scope,
            ontology=ontology,
            metric_label=metric_label,
            operation_family=operation_family,
            operand_specs=operand_specs,
        )
        if task and hints:
            task["decomposition_hints"] = dict(hints)
        return task
    return None


def _build_concept_analysis_task(
    *,
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    concept_specs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    text = _normalise_spaces(query)
    if not text:
        return None

    specs_by_concept = {
        _normalise_spaces(str(spec.get("concept") or "")): dict(spec)
        for spec in concept_specs
        if _normalise_spaces(str(spec.get("concept") or ""))
    }
    for numerator_spec in _order_concept_specs_by_query(concept_specs, query):
        hints = dict(numerator_spec.get("analysis_hints") or {})
        if not hints:
            continue
        query_any_of = [
            _normalise_spaces(str(token))
            for token in (hints.get("query_any_of") or [])
            if _normalise_spaces(str(token))
        ]
        if query_any_of and not any(token in text for token in query_any_of):
            continue

        operation_family = str(hints.get("preferred_operation") or "ratio").strip().lower()
        if operation_family != "ratio":
            continue
        for denominator_index, denominator_key in enumerate((hints.get("denominator_concepts") or []), start=1):
            denominator_spec = specs_by_concept.get(_normalise_spaces(str(denominator_key or "")))
            if not denominator_spec:
                continue
            numerator = {**dict(numerator_spec), "role": "numerator_1"}
            denominator = {**denominator_spec, "role": f"denominator_{denominator_index}"}
            operand_specs = _build_concept_required_operands(
                query,
                report_scope,
                [numerator, denominator],
                operation_family,
            )
            if not operand_specs:
                continue
            metric_label = str(hints.get("metric_label") or "").strip() or _build_concept_metric_label(
                query,
                [numerator, denominator],
                operation_family,
            )
            task = _compose_concept_numeric_task(
                query=query,
                report_scope=report_scope,
                ontology=ontology,
                metric_label=metric_label,
                operation_family=operation_family,
                operand_specs=operand_specs,
            )
            if task:
                task["analysis_hints"] = dict(hints)
                return task
    return None


def _compose_concept_numeric_task(
    *,
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    metric_label: str,
    operation_family: str,
    operand_specs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not operand_specs:
        return None
    preferred_statement_types: List[str] = []
    preferred_sections: List[str] = []
    query_statement_types, query_sections = _infer_statement_and_section_hints(query)
    preferred_statement_types.extend(query_statement_types)
    preferred_sections.extend(query_sections)
    for spec in operand_specs:
        preferred_statement_types.extend(spec.get("preferred_statement_types") or [])
        preferred_sections.extend(spec.get("preferred_sections") or [])
    preferred_statement_types = list(dict.fromkeys(item for item in preferred_statement_types if str(item).strip()))
    preferred_sections = list(dict.fromkeys(item for item in preferred_sections if str(item).strip()))
    constraints = _build_concept_task_constraints(
        query,
        report_scope,
        ontology,
        operand_specs=operand_specs,
        operation_family=operation_family,
    )
    retrieval_queries = _build_generic_retrieval_queries(
        query=query,
        metric_label=metric_label,
        operand_specs=operand_specs,
        preferred_sections=preferred_sections,
        report_scope=report_scope,
        constraints=constraints,
    )
    task_query = _build_metric_task_query(
        original_query=query,
        metric_label=metric_label,
        constraints=constraints,
        operand_specs=operand_specs,
        report_scope=report_scope,
    )
    result_unit = _infer_concept_ratio_result_unit(query, metric_label, operation_family)
    return {
        "task_id": "task_1",
        "metric_family": f"concept_{operation_family}",
        "metric_label": metric_label,
        "query": task_query,
        "operation_family": operation_family,
        "result_unit": result_unit,
        "required_operands": operand_specs,
        "preferred_statement_types": preferred_statement_types,
        "preferred_sections": preferred_sections,
        "retrieval_queries": retrieval_queries,
        "constraints": constraints,
    }


def _split_multi_lookup_concept_task(
    task: Dict[str, Any],
    *,
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
) -> List[Dict[str, Any]]:
    operation_family = _normalise_spaces(str(task.get("operation_family") or "")).lower()
    if operation_family not in {"lookup", "single_value"}:
        return [dict(task)]
    operand_specs = [dict(item) for item in (task.get("required_operands") or [])]
    if len(operand_specs) <= 1:
        return [dict(task)]

    sibling_surfaces_by_index: Dict[int, List[str]] = {}
    for index, current_operand in enumerate(operand_specs):
        current_surfaces: List[str] = []
        for other_index, operand in enumerate(operand_specs):
            if other_index == index:
                continue
            surface_contract = dict(operand.get("surface_contract") or {})
            current_surfaces.extend(
                str(item).strip()
                for item in (
                    [operand.get("label")]
                    + list(operand.get("aliases") or [])
                    + list(surface_contract.get("positive") or [])
                )
                if str(item or "").strip()
            )
        sibling_surfaces_by_index[index] = list(dict.fromkeys(current_surfaces))

    split_tasks: List[Dict[str, Any]] = []
    for zero_based_index, operand in enumerate(operand_specs):
        index = zero_based_index + 1
        metric_label = str(operand.get("label") or task.get("metric_label") or "").strip()
        constraints = _build_concept_task_constraints(
            query,
            report_scope,
            ontology,
            operand_specs=[operand],
            operation_family="lookup",
        )
        preferred_statement_types = list(
            dict.fromkeys(
                [
                    *list(operand.get("preferred_statement_types") or []),
                    *list(task.get("preferred_statement_types") or []),
                ]
            )
        )
        preferred_sections = list(
            dict.fromkeys(
                [
                    *list(operand.get("preferred_sections") or []),
                    *list(task.get("preferred_sections") or []),
                ]
            )
        )
        retrieval_queries = _build_generic_retrieval_queries(
            query=query,
            metric_label=metric_label,
            operand_specs=[operand],
            preferred_sections=preferred_sections,
            report_scope=report_scope,
            constraints=constraints,
        )
        task_query = _build_metric_task_query(
            original_query=query,
            metric_label=metric_label,
            constraints=constraints,
            operand_specs=[operand],
            report_scope=report_scope,
        )
        sibling_lookup_surfaces = list(
            dict.fromkeys(
                [
                    *list(task.get("sibling_lookup_surfaces") or []),
                    *sibling_surfaces_by_index.get(zero_based_index, []),
                ]
            )
        )
        split_tasks.append(
            {
                **dict(task),
                "task_id": f"task_{index}",
                "metric_family": "concept_lookup",
                "metric_label": metric_label,
                "query": task_query,
                "operation_family": "lookup",
                "result_unit": "",
                "required_operands": [operand],
                "preferred_statement_types": preferred_statement_types,
                "preferred_sections": preferred_sections,
                "retrieval_queries": retrieval_queries,
                "constraints": constraints,
                "sibling_lookup_surfaces": sibling_lookup_surfaces,
            }
        )
    return split_tasks


def _infer_concept_ratio_result_unit(query: str, metric_label: str, operation_family: str) -> str:
    if _normalise_spaces(operation_family) != "ratio":
        return ""
    text = _normalise_spaces(f"{query} {metric_label}")
    ratio_policy = dict(CONCEPT_RATIO_RESULT_UNIT_POLICY)
    multiplier_markers = tuple(str(item) for item in (ratio_policy.get("multiplier_markers") or ()) if str(item))
    percent_markers = tuple(str(item) for item in (ratio_policy.get("percent_markers") or ()) if str(item))
    if any(marker in text for marker in multiplier_markers) and not any(marker in text for marker in percent_markers):
        return str(ratio_policy.get("multiplier_unit") or "")
    return str(ratio_policy.get("percent_unit") or "")


def _build_lookup_producer_task_from_binding(
    *,
    binding: Dict[str, Any],
    consumer_task: Dict[str, Any],
    next_task_id: str,
    report_scope: Dict[str, Any],
) -> Dict[str, Any]:
    consumer_operands = [dict(item) for item in (consumer_task.get("required_operands") or [])]
    source_operand = next(
        (
            dict(item)
            for item in consumer_operands
            if _normalise_spaces(str(item.get("role") or "")) == _normalise_spaces(str(binding.get("role") or ""))
            and _normalise_spaces(str(item.get("concept") or "")) == _normalise_spaces(str(binding.get("concept") or ""))
        ),
        {},
    )
    operand = dict(source_operand or {})
    operand["label"] = _dependency_metric_label(binding)
    operand["period_hint"] = _normalise_spaces(str(binding.get("period") or operand.get("period_hint") or ""))
    operand["role"] = _normalise_spaces(str(binding.get("role") or operand.get("role") or ""))
    binding_concept = _normalise_spaces(str(binding.get("concept") or operand.get("concept") or ""))
    if binding_concept:
        operand["concept"] = binding_concept
        concept_spec = _concept_spec_for_key(get_financial_ontology(), binding_concept)
        if concept_spec:
            operand = _augment_generic_operand_with_concept(operand, concept_spec=concept_spec)
    binding_policy = dict(operand.get("binding_policy") or {})
    # Producer lookups should be free to bind to canonical statement rows even
    # when the downstream derived task prefers aggregate note-table shapes.
    binding_policy.pop("prefer_value_roles", None)
    binding_policy.pop("prefer_aggregation_stages", None)
    binding_segment = _normalise_spaces(str(binding.get("segment_label") or ""))
    if binding_segment:
        binding_policy["segment_label"] = binding_segment
    operand["binding_policy"] = binding_policy
    lookup_query_surfaces = _lookup_query_surface_preferences(operand)
    if lookup_query_surfaces:
        existing_aliases = [str(item).strip() for item in (operand.get("aliases") or []) if str(item).strip()]
        operand["aliases"] = list(dict.fromkeys([*lookup_query_surfaces, *existing_aliases]))

    constraints = _lookup_constraint_from_binding(
        binding,
        dict(consumer_task.get("constraints") or {}),
    )
    preferred_sections = list(
        dict.fromkeys(
            [
                *list(consumer_task.get("preferred_sections") or []),
                *list(operand.get("preferred_sections") or []),
            ]
        )
    )
    preferred_statement_types = list(
        dict.fromkeys(
            [
                *list(operand.get("preferred_statement_types") or []),
                *list(consumer_task.get("preferred_statement_types") or []),
            ]
        )
    )
    if _lookup_prefers_canonical_statement_rows(operand):
        canonical_types, canonical_sections = _lookup_canonical_statement_preferences(operand)
        # For producer lookup tasks that explicitly prefer canonical statement
        # rows, keep retrieval focused on those statement types/sections instead
        # of widening back out to note sections from downstream consumers.
        if canonical_types:
            preferred_statement_types = list(dict.fromkeys(canonical_types))
        if canonical_sections:
            preferred_sections = list(dict.fromkeys(canonical_sections))
        operand["preferred_statement_types"] = list(preferred_statement_types)
        operand["preferred_sections"] = list(preferred_sections)
    retrieval_queries = _build_generic_retrieval_queries(
        query=str(consumer_task.get("query") or consumer_task.get("metric_label") or ""),
        metric_label=str(operand.get("label") or ""),
        operand_specs=[operand],
        preferred_sections=preferred_sections,
        report_scope=report_scope,
        constraints=constraints,
    )
    task_query = _build_metric_task_query(
        original_query=str(consumer_task.get("query") or consumer_task.get("metric_label") or ""),
        metric_label=str(operand.get("label") or ""),
        constraints=constraints,
        operand_specs=[operand],
        report_scope=report_scope,
    )
    return {
        "task_id": next_task_id,
        "metric_family": "concept_lookup" if _normalise_spaces(str(binding.get("concept") or "")) else "generic_numeric",
        "metric_label": str(operand.get("label") or ""),
        "query": task_query,
        "operation_family": "lookup",
        "required_operands": [operand],
        "preferred_statement_types": preferred_statement_types,
        "preferred_sections": preferred_sections,
        "retrieval_queries": retrieval_queries,
        "constraints": constraints,
    }


def _synthesize_missing_lookup_dependency_tasks(
    tasks: List[Dict[str, Any]],
    *,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    base_tasks = [dict(task) for task in (tasks or [])]
    producer_catalog: List[tuple[str, Dict[str, Any]]] = []
    for task in base_tasks:
        producer_task_id = _normalise_spaces(str(task.get("task_id") or ""))
        if not producer_task_id:
            continue
        for output in _task_output_slots_for_dependency(task, report_scope=report_scope):
            producer_catalog.append((producer_task_id, dict(output)))

    next_index = _next_dependency_task_id(base_tasks)
    created_keys: set[tuple[str, str, str]] = set()
    synthetic_tasks: List[Dict[str, Any]] = []
    for task in base_tasks:
        operation_family = _normalise_spaces(str(task.get("operation_family") or "")).lower()
        if operation_family not in {"difference", "growth_rate", "ratio", "sum"}:
            continue
        for binding in _task_input_bindings_for_dependency(task, report_scope=report_scope):
            if any(_dependency_binding_matches_output(binding, output) for _task_id, output in producer_catalog):
                continue
            binding_key = (
                _normalise_spaces(str(binding.get("concept") or "")),
                _normalise_spaces(str(binding.get("period") or "")),
                _normalise_spaces(str(binding.get("segment_label") or "")),
            )
            if not binding_key[0] or binding_key in created_keys:
                continue
            synthetic_task = _build_lookup_producer_task_from_binding(
                binding=binding,
                consumer_task=task,
                next_task_id=f"task_{next_index}",
                report_scope=report_scope,
            )
            next_index += 1
            synthetic_tasks.append(synthetic_task)
            created_keys.add(binding_key)
            producer_catalog.append(
                (
                    str(synthetic_task.get("task_id") or "").strip(),
                    {
                        "slot": "primary_value",
                        "role": _normalise_spaces(str(binding.get("role") or "")) or "primary_value",
                        "concept": _normalise_spaces(str(binding.get("concept") or "")),
                        "period": _normalise_spaces(str(binding.get("period") or "")),
                        "label": _normalise_spaces(str(binding.get("label") or "")),
                        "segment_label": _normalise_spaces(str(binding.get("segment_label") or "")),
                    },
                )
            )
    return base_tasks + synthetic_tasks


def _dependency_binding_matches_output(
    binding: Dict[str, Any],
    output: Dict[str, Any],
) -> bool:
    if _normalise_spaces(str(binding.get("concept") or "")) != _normalise_spaces(str(output.get("concept") or "")):
        return False
    binding_period = _normalise_spaces(str(binding.get("period") or ""))
    output_period = _normalise_spaces(str(output.get("period") or ""))
    if binding_period and output_period and binding_period != output_period:
        return False
    binding_segment = _normalise_spaces(str(binding.get("segment_label") or ""))
    output_segment = _normalise_spaces(str(output.get("segment_label") or ""))
    if binding_segment and output_segment and binding_segment != output_segment:
        return False
    if binding_segment and not output_segment:
        label_text = _normalise_spaces(str(output.get("label") or "")).lower()
        if binding_segment.lower() not in label_text:
            return False
    return True


def _topologically_order_dependency_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    task_ids = [str(task.get("task_id") or "").strip() for task in tasks]
    if not task_ids:
        return tasks
    indegree: Dict[str, int] = {task_id: 0 for task_id in task_ids if task_id}
    adjacency: Dict[str, List[str]] = {task_id: [] for task_id in indegree}
    original_index = {task_id: index for index, task_id in enumerate(task_ids) if task_id}
    task_by_id = {str(task.get("task_id") or "").strip(): dict(task) for task in tasks if str(task.get("task_id") or "").strip()}

    for task in tasks:
        task_id = str(task.get("task_id") or "").strip()
        if not task_id:
            continue
        for dependency in list(task.get("depends_on") or []):
            dependency_id = _normalise_spaces(str(dependency or ""))
            if not dependency_id or dependency_id not in indegree or dependency_id == task_id:
                continue
            indegree[task_id] += 1
            adjacency[dependency_id].append(task_id)

    ready = sorted(
        [task_id for task_id, count in indegree.items() if count == 0],
        key=lambda value: original_index.get(value, 10_000),
    )
    ordered_ids: List[str] = []
    while ready:
        task_id = ready.pop(0)
        ordered_ids.append(task_id)
        for child in sorted(adjacency.get(task_id, []), key=lambda value: original_index.get(value, 10_000)):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort(key=lambda value: original_index.get(value, 10_000))

    if len(ordered_ids) != len(indegree):
        return [dict(task) for task in tasks]
    return [task_by_id[task_id] for task_id in ordered_ids]


def _annotate_task_dependencies(
    tasks: List[Dict[str, Any]],
    *,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    annotated_tasks = _synthesize_missing_lookup_dependency_tasks(
        tasks,
        report_scope=report_scope,
    )
    producer_catalog: List[tuple[str, Dict[str, Any]]] = []

    for task in annotated_tasks:
        outputs = _task_output_slots_for_dependency(task, report_scope=report_scope)
        task["produces"] = outputs
        producer_task_id = _normalise_spaces(str(task.get("task_id") or ""))
        if not producer_task_id:
            continue
        for output in outputs:
            producer_catalog.append((producer_task_id, dict(output)))

    for task in annotated_tasks:
        inputs = _task_input_bindings_for_dependency(task, report_scope=report_scope)
        dependencies: List[str] = []
        for binding in inputs:
            for producer_task_id, output in producer_catalog:
                if producer_task_id == _normalise_spaces(str(task.get("task_id") or "")):
                    continue
                if not _dependency_binding_matches_output(binding, output):
                    continue
                binding["preferred_task_id"] = producer_task_id
                binding["source_preference"] = ["task_output", "retrieval"]
                if producer_task_id not in dependencies:
                    dependencies.append(producer_task_id)
                break
        task["inputs"] = inputs
        task["depends_on"] = dependencies

    return _topologically_order_dependency_tasks(annotated_tasks)


def _infer_period_focus(query: str, default_value: str = "unknown") -> str:
    text = _normalise_spaces(query)
    period_policy = dict(PERIOD_FOCUS_POLICY)
    if any(keyword in text for keyword in (period_policy.get("prior_markers") or ())):
        return "prior"
    if any(keyword in text for keyword in (period_policy.get("current_markers") or ())):
        return "current"
    explicit_years = list(dict.fromkeys(re.findall(str(period_policy.get("explicit_year_pattern") or r"$^"), text)))
    if len(explicit_years) == 1:
        return "current"
    return default_value or "unknown"


def _task_period_focus_from_operands(
    operation_family: str,
    operand_specs: List[Dict[str, Any]],
    default_value: str,
) -> str:
    roles = {
        str(spec.get("role") or "").strip()
        for spec in operand_specs
        if str(spec.get("role") or "").strip()
    }
    if not roles:
        return default_value or "unknown"
    if operation_family in {"lookup", "single_value"}:
        if roles == {"current_period"}:
            return "current"
        if roles == {"prior_period"}:
            return "prior"
    if operation_family in {"difference", "growth_rate"}:
        if "current_period" in roles and "prior_period" in roles:
            return "multi_period"
        if roles == {"current_period"}:
            return "current"
        if roles == {"prior_period"}:
            return "prior"
    return default_value or "unknown"


def _build_task_constraints(
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    metric_key: str,
) -> Dict[str, str]:
    defaults = dict(ontology.default_constraints_for_metric(metric_key) or {})
    defaults["consolidation_scope"] = _desired_consolidation_scope(query, report_scope)
    defaults["period_focus"] = _infer_period_focus(query, str(defaults.get("period_focus") or "unknown"))
    return {
        "consolidation_scope": str(defaults.get("consolidation_scope") or "unknown"),
        "period_focus": str(defaults.get("period_focus") or "unknown"),
        "entity_scope": str(defaults.get("entity_scope") or "unknown"),
        "segment_scope": str(defaults.get("segment_scope") or "none"),
    }


def _build_retrieval_query_bundle(
    query: str,
    topic: str,
    metric_key: str,
    ontology: Any,
) -> List[str]:
    metric = ontology.metric_family(metric_key) or {}
    display_name = str(metric.get("display_name") or "").strip()
    keywords = ontology.retrieval_keywords_for_metric(metric_key)
    preferred_sections = ontology.preferred_sections(display_name or query, topic, "comparison")
    primary_bits = [query, display_name]
    primary_bits.extend(keywords[:4])
    if preferred_sections:
        primary_bits.extend(preferred_sections[:2])
    primary = _normalise_spaces(" ".join(primary_bits))

    bundles = [primary] if primary else []
    for operand in ontology.build_operand_spec(metric_key):
        operand_bits = [query, display_name, str(operand.get("label") or "")]
        operand_bits.extend(list(operand.get("aliases") or [])[:2])
        operand_bits.extend(list(operand.get("preferred_sections") or [])[:1])
        operand_query = _normalise_spaces(" ".join(operand_bits))
        if operand_query:
            bundles.append(operand_query)
    return list(dict.fromkeys(item for item in bundles if item))


def _build_metric_task_query(
    *,
    original_query: str,
    metric_label: str,
    constraints: Dict[str, str],
    operand_specs: List[Dict[str, Any]],
    report_scope: Dict[str, Any],
) -> str:
    query_text = _normalise_spaces(original_query)
    year = report_scope.get("year")
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    year_suffix_template = str(period_policy.get("year_suffix_template") or "{year}")
    year_text = f"{year_suffix_template.format(year=year)} " if str(year or "").strip() else ""
    consolidation_scope = str((constraints or {}).get("consolidation_scope") or "unknown").strip()
    consolidation_text = ""
    scope_prefix_labels = dict(CONSOLIDATION_SCOPE_POLICY.get("query_prefix_labels") or {})
    if consolidation_scope == "consolidated":
        consolidation_text = f"{scope_prefix_labels.get('consolidated') or ''} "
    elif consolidation_scope == "separate":
        consolidation_text = f"{scope_prefix_labels.get('separate') or ''} "

    query_policy = dict(METRIC_TASK_QUERY_POLICY)
    operand_labels = [str(spec.get("label") or "").strip() for spec in operand_specs if str(spec.get("label") or "").strip()]
    operand_joiner = str(query_policy.get("operand_joiner") or "/")
    operand_hint = (
        str(query_policy.get("operand_hint_template") or "{labels}").format(labels=operand_joiner.join(operand_labels))
        if len(operand_labels) >= 2
        else ""
    )
    canonical_query = _normalise_spaces(
        str(query_policy.get("canonical_query_template") or "{metric_label}").format(
            year_text=year_text,
            consolidation_text=consolidation_text,
            metric_label=metric_label,
            operand_hint=operand_hint,
        )
    )
    if canonical_query:
        return canonical_query
    return query_text or metric_label


def _build_semantic_numeric_plan(
    query: str,
    topic: str,
    intent: str,
    report_scope: Dict[str, Any],
    target_metric_family: str,
) -> Dict[str, Any]:
    """Translate a query into one or more numeric subtasks.

    This is the main pure planning entrypoint. It prefers ontology-backed tasks
    and falls back to heuristic generic-numeric tasks when no clean ontology
    match is available.
    """
    ontology = get_financial_ontology()
    matches = ontology.match_metric_families(query, topic, intent)
    operation_family = _infer_operation_family_from_query(query, ontology)
    concept_specs = ontology.concept_specs(query, topic, intent)
    planner_notes: List[str] = [
        f"planner_input_intent:{str(intent or 'unknown').strip() or 'unknown'}",
        f"planner_inferred_operation:{operation_family or 'unknown'}",
        f"planner_ontology_matches:{len(matches)}",
        f"planner_concept_specs:{len(concept_specs)}",
    ]
    matched_metric_keys = {
        str(item.get("key") or "").strip()
        for item in matches
        if str(item.get("key") or "").strip()
    }
    strong_metric_keys = [
        str(item.get("key") or "").strip()
        for item in matches
        if str(item.get("key") or "").strip()
        and _query_mentions_metric(query, item)
        and str(item.get("formula_family") or "").strip().lower() == operation_family
    ]
    strong_metric_keys = list(dict.fromkeys(strong_metric_keys))
    metric_keys: List[str] = []
    entity_scoped_specs = _build_entity_scoped_concept_specs(
        query=query,
        report_scope=report_scope,
        ontology=ontology,
        operation_family=operation_family,
    )
    planner_notes.append(f"planner_entity_scoped_specs:{len(entity_scoped_specs)}")
    concept_specs_have_segment_binding = any(
        _normalise_spaces(str(dict(spec.get("binding_policy") or {}).get("segment_label") or ""))
        for spec in concept_specs
    )
    if entity_scoped_specs and (
        not concept_specs
        or (
            operation_family in {"sum", "difference"}
            and len(concept_specs) == 1
            and len(entity_scoped_specs) >= 2
        )
        or (
            operation_family in {"growth_rate", "lookup", "single_value"}
            and not concept_specs_have_segment_binding
        )
    ):
        concept_specs = entity_scoped_specs
        planner_notes.append("entity_scoped_concept_fallback")
    if strong_metric_keys and concept_specs:
        planner_notes.append("metric_match_preferred_over_concept")
    if not target_metric_family and concept_specs and strong_metric_keys and _extract_generic_ratio_operand_specs(query):
        concept_task = _build_concept_numeric_task(
            query=query,
            topic=topic,
            report_scope=report_scope,
            ontology=ontology,
            concept_specs=concept_specs,
        )
        if concept_task:
            concept_tasks = _split_multi_lookup_concept_task(
                concept_task,
                query=query,
                report_scope=report_scope,
                ontology=ontology,
            )
            return {
                "status": "concept_fallback",
                "fallback_to_general_search": False,
                "planned_metric_families": [
                    str(task.get("metric_family") or "").strip()
                    for task in concept_tasks
                    if str(task.get("metric_family") or "").strip()
                ],
                "tasks": concept_tasks,
                "planner_notes": planner_notes
                + ["explicit_ratio_concept_preferred", "planner_fallback:explicit_ratio_concept_preferred"],
            }
    if not target_metric_family and concept_specs and not strong_metric_keys:
        concept_task = _build_concept_numeric_task(
            query=query,
            topic=topic,
            report_scope=report_scope,
            ontology=ontology,
            concept_specs=concept_specs,
        )
        if concept_task:
            concept_tasks = _split_multi_lookup_concept_task(
                concept_task,
                query=query,
                report_scope=report_scope,
                ontology=ontology,
            )
            return {
                "status": "concept_fallback",
                "fallback_to_general_search": False,
                "planned_metric_families": [
                    str(task.get("metric_family") or "").strip()
                    for task in concept_tasks
                    if str(task.get("metric_family") or "").strip()
                ],
                "tasks": concept_tasks,
                "planner_notes": planner_notes + ["concept_first_preferred", "planner_fallback:concept_first_preferred"],
            }
    if target_metric_family:
        planner_notes.append(f"planner_target_metric:{target_metric_family}")
        target_metric = ontology.metric_family(target_metric_family) or {}
        target_operand_specs = ontology.build_operand_spec(target_metric_family) if target_metric else []
        component_match_count = _query_component_match_count(query, target_operand_specs)
        if target_metric and (
            _query_mentions_metric(query, target_metric)
            or (
                target_metric_family in matched_metric_keys
                and component_match_count >= 2
            )
        ):
            metric_keys.append(target_metric_family)
        else:
            planner_notes.append(f"drop_weak_target:{target_metric_family}")
    metric_keys.extend(strong_metric_keys)
    metric_keys = list(dict.fromkeys(metric_keys))

    tasks: List[Dict[str, Any]] = []
    if not metric_keys:
        planner_notes.append("planner_no_metric_keys")
        concept_task = _build_concept_numeric_task(
            query=query,
            topic=topic,
            report_scope=report_scope,
            ontology=ontology,
            concept_specs=concept_specs,
        )
        if concept_task:
            concept_tasks = _split_multi_lookup_concept_task(
                concept_task,
                query=query,
                report_scope=report_scope,
                ontology=ontology,
            )
            return {
                "status": "concept_fallback",
                "fallback_to_general_search": False,
                "planned_metric_families": [
                    str(task.get("metric_family") or "").strip()
                    for task in concept_tasks
                    if str(task.get("metric_family") or "").strip()
                ],
                "tasks": concept_tasks,
                "planner_notes": planner_notes + ["concept_numeric_task", "planner_fallback:concept_numeric_task"],
            }
        heuristic_task = _build_heuristic_numeric_task(
            query=query,
            topic=topic,
            intent=intent,
            report_scope=report_scope,
        )
        if heuristic_task:
            return {
                "status": "heuristic_fallback",
                "fallback_to_general_search": False,
                "planned_metric_families": [str(heuristic_task.get("metric_family") or "").strip()],
                "tasks": [heuristic_task],
                "planner_notes": planner_notes + ["heuristic_numeric_task", "planner_fallback:heuristic_numeric_task"],
            }
        return {
            "status": "fallback_general_search",
            "fallback_to_general_search": True,
            "planned_metric_families": [],
            "tasks": [],
            "planner_notes": planner_notes + ["ontology_match_missing", "planner_fallback:general_search"],
        }

    for index, metric_key in enumerate(metric_keys, start=1):
        metric = ontology.metric_family(metric_key) or {}
        if not metric:
            continue
        display_name = str(metric.get("display_name") or metric_key).strip()
        if matches and not _query_mentions_metric(query, metric) and metric_key != target_metric_family:
            # Avoid over-expanding to weak secondary matches unless explicitly targeted.
            planner_notes.append(f"skip_weak_match:{metric_key}")
            continue
        constraints = _build_task_constraints(query, report_scope, ontology, metric_key)
        operand_specs = ontology.build_operand_spec(metric_key)
        retrieval_queries = _build_retrieval_query_bundle(query, topic, metric_key, ontology)
        task_query = _build_metric_task_query(
            original_query=query,
            metric_label=display_name,
            constraints=constraints,
            operand_specs=operand_specs,
            report_scope=report_scope,
        )
        tasks.append(
            {
                "task_id": f"task_{index}",
                "metric_family": metric_key,
                "metric_label": display_name,
                "query": task_query,
                "operation_family": str(metric.get("formula_family") or "").strip(),
                "required_operands": [
                    {
                        "label": str(spec.get("label") or ""),
                        "concept": str(spec.get("concept") or ""),
                        "aliases": list(spec.get("aliases") or []),
                        "keywords": list(spec.get("keywords") or []),
                        "role": str(spec.get("role") or ""),
                        "required": bool(spec.get("required", True)),
                        "preferred_sections": list(spec.get("preferred_sections") or []),
                        "preferred_statement_types": list(spec.get("preferred_statement_types") or []),
                        "binding_policy": dict(spec.get("binding_policy") or {}),
                        "surface_contract": dict(spec.get("surface_contract") or {}),
                    }
                    for spec in operand_specs
                    if str(spec.get("label") or "").strip()
                ],
                "preferred_statement_types": list(ontology.statement_type_hints_for_metric(metric_key)),
                "preferred_sections": list(metric.get("preferred_sections") or []),
                "retrieval_queries": retrieval_queries,
                "constraints": constraints,
            }
        )

    if not tasks:
        return {
            "status": "fallback_general_search",
            "fallback_to_general_search": True,
            "planned_metric_families": [],
            "tasks": [],
            "planner_notes": planner_notes or ["no_viable_tasks"],
        }

    return {
        "status": "ok",
        "fallback_to_general_search": False,
        "planned_metric_families": [
            str(task.get("metric_family") or "").strip()
            for task in tasks
            if str(task.get("metric_family") or "").strip()
        ],
        "tasks": tasks,
        "planner_notes": planner_notes,
    }


# ---------------------------------------------------------------------------
# Reconciliation and operand matching helpers
# ---------------------------------------------------------------------------

def _build_reconciliation_candidate(
    *,
    candidate_id: str,
    anchor: str,
    text: str,
    metadata: Dict[str, Any],
    candidate_kind: str = "chunk",
    row_label: str = "",
    row_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Normalize a raw evidence/doc fragment into reconciliation candidate form."""
    candidate_metadata = dict(metadata or {})
    if row_label:
        candidate_metadata["row_label"] = row_label
    if row_index is not None:
        candidate_metadata["row_index"] = row_index
    return {
        "candidate_id": candidate_id,
        "source_anchor": anchor,
        "text": _normalise_spaces(text),
        "metadata": candidate_metadata,
        "candidate_kind": candidate_kind,
    }


def _query_years_from_state(state: Dict[str, Any]) -> List[int]:
    years: List[int] = []
    for value in list(state.get("years") or []):
        try:
            year = int(value)
        except (TypeError, ValueError):
            continue
        if year not in years:
            years.append(year)
    report_scope = dict(state.get("report_scope") or {})
    scope_year_raw = report_scope.get("year")
    try:
        if scope_year_raw not in (None, ""):
            scope_year = int(scope_year_raw)
            if scope_year not in years:
                years.insert(0, scope_year)
    except (TypeError, ValueError):
        pass
    return years


def _structured_cell_period_text(cell: Dict[str, Any], query_years: List[int], period_focus: str) -> str:
    focus_policy = dict(PERIOD_FOCUS_POLICY)
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    current_markers = tuple(str(item) for item in (focus_policy.get("current_markers") or ()) if str(item))
    prior_markers = tuple(str(item) for item in (focus_policy.get("prior_markers") or ()) if str(item))
    current_hint = str(period_policy.get("current_period_hint") or "current")
    prior_hint = str(period_policy.get("prior_period_hint") or "prior")
    headers = [str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()]
    report_year: Optional[int] = None
    for raw_year in (cell.get("_report_year"), cell.get("report_year"), cell.get("year")):
        try:
            if raw_year not in (None, ""):
                report_year = int(raw_year)
                break
        except (TypeError, ValueError):
            continue
    if query_years:
        for year in query_years:
            year_text = str(year)
            if any(year_text in header for header in headers):
                return year_text
    header_text = " ".join(headers)
    if period_focus == "current" and any(token in header_text for token in current_markers):
        if report_year is not None:
            return str(report_year)
        return current_hint
    if period_focus == "prior" and any(token in header_text for token in prior_markers):
        if report_year is not None:
            return str(report_year - 1)
        return prior_hint
    fiscal_rank = _structured_cell_fiscal_rank(cell)
    if fiscal_rank is not None and (report_year is not None or query_years):
        current_year = report_year if report_year is not None else max(query_years)
        return str(current_year - fiscal_rank)
    return header_text


def _structured_cell_fiscal_ordinal(cell: Dict[str, Any]) -> Optional[int]:
    headers = [str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()]
    header_text = " ".join(headers)
    match = re.search(r"제\s*(\d+)\s*기", header_text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _structured_cell_fiscal_rank(cell: Dict[str, Any]) -> Optional[int]:
    ordinal = _structured_cell_fiscal_ordinal(cell)
    if ordinal is None:
        return None
    ordinal_candidates = [ordinal]
    for sibling in list(cell.get("_sibling_cells") or []):
        sibling_ordinal = _structured_cell_fiscal_ordinal(dict(sibling))
        if sibling_ordinal is not None and sibling_ordinal not in ordinal_candidates:
            ordinal_candidates.append(sibling_ordinal)
    ordered = sorted(ordinal_candidates, reverse=True)
    try:
        return ordered.index(ordinal)
    except ValueError:
        return None


def _select_structured_cell(
    cells: List[Dict[str, Any]],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
    period_focus: str,
) -> Optional[Dict[str, Any]]:
    if not cells:
        return None

    enriched_cells: List[Dict[str, Any]] = []
    for cell in cells:
        enriched = dict(cell)
        enriched["_sibling_cells"] = [dict(item) for item in cells]
        enriched_cells.append(enriched)

    all_have_fiscal_ordinals = bool(enriched_cells) and all(
        _structured_cell_fiscal_ordinal(cell) is not None for cell in enriched_cells
    )
    if all_have_fiscal_ordinals and period_focus in {"current", "prior"}:
        ordered = sorted(
            enriched_cells,
            key=lambda current: _structured_cell_fiscal_ordinal(current) or -1,
            reverse=True,
        )
        if period_focus == "current":
            return ordered[0]
        if len(ordered) >= 2:
            return ordered[1]
        return ordered[0]

    ranked_cells = sorted(
        enriched_cells,
        key=lambda cell: _score_structured_cell(
            cell,
            query_years=_operand_target_years(operand, query_years),
            period_focus=period_focus,
            operand=operand,
        ),
        reverse=True,
    )
    return ranked_cells[0] if ranked_cells else None


def _operand_target_years(operand: Dict[str, Any], query_years: List[int]) -> List[int]:
    hint = str(operand.get("period_hint") or "").strip()
    years: List[int] = []
    for token in re.findall(r"20\d{2}", f"{hint} {operand.get('label') or ''}"):
        year = int(token)
        if year not in years:
            years.append(year)
    if years:
        return years
    ordered_years: List[int] = []
    for raw_year in list(query_years or []):
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            continue
        if year not in ordered_years:
            ordered_years.append(year)
    if not ordered_years:
        return []

    period_focus = _operand_period_focus(operand, "unknown")
    if period_focus == "current":
        return [max(ordered_years)]
    if period_focus == "prior":
        ranked_years = sorted(ordered_years, reverse=True)
        if len(ranked_years) >= 2:
            return [ranked_years[1]]
        return [ranked_years[0] - 1]
    return ordered_years


def _operand_period_focus(operand: Dict[str, Any], default_period_focus: str) -> str:
    hint = str(operand.get("period_hint") or "").strip()
    role = str(operand.get("role") or "").strip()
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    current_hints = set(str(item) for item in (period_policy.get("current_period_hints") or ()) if str(item))
    prior_hints = set(str(item) for item in (period_policy.get("prior_period_hints") or ()) if str(item))
    if hint in current_hints or role == "current_period":
        return "current"
    if hint in prior_hints or role == "prior_period":
        return "prior"
    return default_period_focus


def _structured_cell_operand_affinity(cell: Dict[str, Any], operand: Dict[str, Any]) -> float:
    headers = [
        _normalise_spaces(str(item))
        for item in (cell.get("column_headers") or [])
        if _normalise_spaces(str(item))
    ]
    if not headers:
        return 0.0

    generic_headers = _generic_column_headers()
    non_generic_headers = [header for header in headers if header not in generic_headers]
    last_header = non_generic_headers[-1] if non_generic_headers else headers[-1]
    needles = [_normalise_spaces(needle) for needle in _operand_needles(operand) if _normalise_spaces(needle)]
    if not needles:
        return 0.0

    score = 0.0
    if any(last_header == needle for needle in needles):
        score += 4.0
    elif _operand_text_match(last_header, operand):
        score += 2.0

    if any(header == needle for header in headers for needle in needles):
        score += 0.75
    elif any(_operand_text_match(header, operand) for header in headers):
        score += 0.35

    row_label = _normalise_spaces(str(cell.get("row_label") or ""))
    operand_label = _normalise_spaces(str(operand.get("label") or operand.get("name") or ""))
    affinity_policy = dict(STRUCTURED_CELL_AFFINITY_POLICY)
    metric_terms = tuple(str(item) for item in (affinity_policy.get("metric_terms") or ()) if str(item))
    if row_label and operand_label and any(term in row_label for term in metric_terms) and any(
        term in operand_label for term in metric_terms
    ):
        entity_surface = operand_label
        entity_surface = re.sub(str(affinity_policy.get("year_pattern") or r"$^"), " ", entity_surface)
        for term in (*metric_terms, *(affinity_policy.get("entity_surface_drop_terms") or ())):
            entity_surface = entity_surface.replace(term, " ")
        entity_tokens = [
            token
            for token in re.split(str(affinity_policy.get("entity_token_split_pattern") or r"\s+"), _normalise_spaces(entity_surface))
            if token
        ]
        header_blob = _normalise_spaces(" ".join(headers))
        header_compact = re.sub(r"\s+", "", header_blob)
        if any(token in header_blob or token in header_compact for token in entity_tokens):
            score += 3.0

    aggregate_tokens = tuple(str(item) for item in (affinity_policy.get("aggregate_tokens") or ()) if str(item))
    if any(token in last_header for token in aggregate_tokens) and _operand_text_match(last_header, operand):
        score += 4.0

    return score


def _score_structured_cell(
    cell: Dict[str, Any],
    *,
    query_years: List[int],
    period_focus: str,
    operand: Optional[Dict[str, Any]] = None,
) -> float:
    headers = [str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()]
    header_text = " ".join(headers)
    score = 0.0
    if query_years:
        for index, year in enumerate(query_years):
            if str(year) in header_text:
                score += 10.0 - index
    period_policy = dict(STRUCTURED_CELL_PERIOD_SCORING_POLICY)
    if period_focus == "current":
        if any(token in header_text for token in period_policy.get("current_positive_markers") or ()):
            score += 4.0
        if any(token in header_text for token in period_policy.get("current_negative_markers") or ()):
            score -= 1.0
    elif period_focus == "prior":
        if any(token in header_text for token in period_policy.get("prior_positive_markers") or ()):
            score += 4.0
        if any(token in header_text for token in period_policy.get("prior_negative_markers") or ()):
            score -= 1.0
    if operand:
        score += _structured_cell_operand_affinity(cell, operand)
        binding_policy = dict(operand.get("binding_policy") or {})
        preferred_value_roles = {
            _normalise_spaces(str(item))
            for item in (binding_policy.get("prefer_value_roles") or [])
            if str(item).strip()
        }
        preferred_aggregation_stages = {
            _normalise_spaces(str(item))
            for item in (binding_policy.get("prefer_aggregation_stages") or [])
            if str(item).strip()
        }
        value_role = _normalise_spaces(str(cell.get("value_role") or ""))
        aggregation_stage = _normalise_spaces(str(cell.get("aggregation_stage") or ""))
        aggregate_role = _normalise_spaces(str(cell.get("aggregate_role") or ""))
        aggregate_label = _normalise_spaces(str(cell.get("aggregate_label") or ""))
        aggregate_tokens = tuple(
            str(item)
            for item in (STRUCTURED_CELL_AFFINITY_POLICY.get("aggregate_tokens") or ())
            if str(item)
        )
        aggregate_surface = _normalise_spaces(" ".join([header_text, aggregate_label, aggregate_role]))
        aggregate_like = (
            value_role == "aggregate"
            or aggregation_stage in {"final", "direct", "subtotal"}
            or aggregate_role in {"direct_total", "subtotal", "final_total"}
            or any(token in aggregate_surface for token in aggregate_tokens)
        )
        if aggregate_like:
            if "aggregate" in preferred_value_roles:
                score += 3.0
            if preferred_aggregation_stages and aggregation_stage in preferred_aggregation_stages:
                score += 2.0
            if not _normalise_spaces(str(operand.get("segment_label") or "")):
                score += 1.25
        elif preferred_value_roles and "aggregate" in preferred_value_roles and value_role == "detail":
            score -= 1.0
    if not header_text:
        score -= 0.25
    return score


def _operand_needles(operand: Dict[str, Any]) -> List[str]:
    label = str(operand.get("label") or "").strip()
    aliases = [str(item).strip() for item in (operand.get("aliases") or []) if str(item).strip()]
    return [needle for needle in [label, *aliases] if needle]


def _operand_surface_contract(operand: Dict[str, Any]) -> Dict[str, List[str]]:
    explicit_contract = dict(operand.get("surface_contract") or {})
    if explicit_contract:
        return {
            "positive": [str(item).strip() for item in (explicit_contract.get("positive") or []) if str(item).strip()],
            "negative": [str(item).strip() for item in (explicit_contract.get("negative") or []) if str(item).strip()],
        }

    concept_key = _normalise_spaces(str(operand.get("concept") or ""))
    legacy_contracts = {
        str(key): dict(value or {})
        for key, value in dict(HELPER_RUNTIME_POLICY.get("legacy_concept_surface_contracts") or {}).items()
    }
    if concept_key and concept_key in legacy_contracts:
        return dict(legacy_contracts[concept_key])

    needles = " ".join(_operand_needles(operand))
    for contract in legacy_contracts.values():
        positive_terms = [str(item).strip() for item in (contract.get("positive") or []) if str(item).strip()]
        if any(_normalise_spaces(term) in _normalise_spaces(needles) for term in positive_terms):
            return dict(contract)
    return {}


def _text_has_contract_term(text: str, terms: List[str]) -> bool:
    haystack = _normalise_spaces(text or "")
    if not haystack:
        return False
    haystack_compact = re.sub(r"\s+", "", haystack)
    for raw_term in terms:
        normalized_term = _normalise_spaces(raw_term)
        if not normalized_term:
            continue
        term_compact = re.sub(r"\s+", "", normalized_term)
        if normalized_term in haystack or (term_compact and term_compact in haystack_compact):
            return True
    return False


def _text_has_positive_surface(text: str, operand: Dict[str, Any]) -> bool:
    contract = _operand_surface_contract(operand)
    return _text_has_contract_term(text, list(contract.get("positive") or []))


def _text_has_negative_surface(text: str, operand: Dict[str, Any]) -> bool:
    contract = _operand_surface_contract(operand)
    return _text_has_contract_term(text, list(contract.get("negative") or []))


def _candidate_has_required_surface_contract(
    candidate: Dict[str, Any],
    operand: Dict[str, Any],
    *,
    selected_cell: Optional[Dict[str, Any]] = None,
) -> bool:
    contract = _operand_surface_contract(operand)
    positive_terms = [str(item).strip() for item in (contract.get("positive") or []) if str(item).strip()]
    if not positive_terms:
        return True

    metadata = dict(candidate.get("metadata") or {})
    surfaces = [
        str(metadata.get("semantic_label") or "").strip(),
        str(metadata.get("row_label") or "").strip(),
        str(metadata.get("aggregate_label") or "").strip(),
        " ".join(str(item).strip() for item in (metadata.get("semantic_aliases") or []) if str(item).strip()),
        " ".join(str(item).strip() for item in (metadata.get("row_headers") or []) if str(item).strip()),
        " ".join(str(item).strip() for item in ((selected_cell or {}).get("column_headers") or []) if str(item).strip()),
        str(metadata.get("table_row_labels_text") or "").strip(),
        str(metadata.get("table_value_labels_text") or "").strip(),
        str(metadata.get("row_text") or "").strip(),
        str(candidate.get("text") or "").strip(),
    ]
    return any(_text_has_contract_term(surface, positive_terms) for surface in surfaces if surface)


def _candidate_conflicts_with_operand_concept(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    normalized_needles = [_normalise_spaces(needle) for needle in _operand_needles(operand) if _normalise_spaces(needle)]
    expects_liability = any("부채" in needle for needle in normalized_needles)

    metadata = dict(candidate.get("metadata") or {})
    authoritative_surfaces = [
        str(metadata.get("semantic_label") or "").strip(),
        str(metadata.get("row_label") or "").strip(),
        str(metadata.get("aggregate_label") or "").strip(),
        " ".join(str(item).strip() for item in (metadata.get("semantic_aliases") or []) if str(item).strip()),
        " ".join(str(item).strip() for item in (metadata.get("row_headers") or []) if str(item).strip()),
    ]
    authoritative_surfaces = [surface for surface in authoritative_surfaces if surface]
    if not expects_liability and any("부채" in _normalise_spaces(surface) for surface in authoritative_surfaces):
        return True

    contract = _operand_surface_contract(operand)
    if not contract:
        return False

    if any(_text_has_negative_surface(surface, operand) for surface in authoritative_surfaces):
        return True

    if any(_text_has_positive_surface(surface, operand) for surface in authoritative_surfaces):
        return False

    return _text_has_negative_surface(str(candidate.get("text") or ""), operand)


def _operand_row_conflicts_with_requirement(row: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    operand_concept = _normalise_spaces(str(operand.get("concept") or ""))
    row_concepts = [
        _normalise_spaces(str(row.get("matched_operand_concept") or "")),
        _normalise_spaces(str(row.get("concept") or "")),
    ]
    if operand_concept and any(row_concept and row_concept != operand_concept for row_concept in row_concepts):
        return True

    operand_period_text = " ".join(
        str(value or "")
        for value in (
            operand.get("period_hint"),
            operand.get("label"),
            operand.get("name"),
        )
    )
    row_period_text = " ".join(
        str(value or "")
        for value in (
            row.get("period"),
            row.get("label"),
            row.get("matched_operand_label"),
        )
    )
    operand_years = set(re.findall(r"20\d{2}", operand_period_text))
    row_years = set(re.findall(r"20\d{2}", row_period_text))
    if str(row.get("period_source") or "").strip() == "evidence_surface":
        row_period_years = set(re.findall(r"20\d{2}", str(row.get("period") or "")))
        if operand_years and row_period_years and operand_years.isdisjoint(row_period_years):
            return True
    if operand_years and row_years and operand_years.isdisjoint(row_years):
        return True

    normalized_needles = [_normalise_spaces(needle) for needle in _operand_needles(operand) if _normalise_spaces(needle)]
    expects_liability = any("부채" in needle for needle in normalized_needles)
    authoritative_surfaces = [
        str(row.get("matched_operand_label") or "").strip(),
        str(row.get("label") or "").strip(),
    ]
    authoritative_surfaces = [surface for surface in authoritative_surfaces if surface]
    row_unit_family = _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
    if not row_unit_family:
        _value, row_unit_family = _normalise_operand_value(
            str(row.get("raw_value") or ""),
            str(row.get("raw_unit") or ""),
        )
        row_unit_family = _normalise_spaces(str(row_unit_family or "")).upper()
    operand_unit_family = _normalise_spaces(str(operand.get("unit_family") or "")).upper()
    operand_label = _normalise_spaces(str(operand.get("label") or ""))
    if row_unit_family == "PERCENT" and operand_unit_family in {"KRW", "CURRENCY", "MONEY", "AMOUNT"}:
        return True
    if row_unit_family in {"KRW", "CURRENCY", "MONEY", "AMOUNT"} and operand_unit_family == "PERCENT":
        return True
    if (
        row_unit_family == "PERCENT"
        and operand_unit_family != "PERCENT"
        and not _label_implies_percent_metric(operand_label)
        and any(_label_implies_percent_metric(surface) for surface in authoritative_surfaces)
    ):
        return True

    if not expects_liability and any("부채" in _normalise_spaces(surface) for surface in authoritative_surfaces):
        return True

    contract = _operand_surface_contract(operand)
    if not contract:
        return False

    if any(_text_has_negative_surface(surface, operand) for surface in authoritative_surfaces):
        return True
    return False


def _operand_text_match(text: str, operand: Dict[str, Any]) -> bool:
    haystack_variants = _surface_match_variants(text)
    if not haystack_variants:
        return False
    for haystack in haystack_variants:
        haystack_compact = re.sub(r"\s+", "", haystack)
        for needle in _operand_needles(operand):
            for normalized_needle in _surface_match_variants(needle):
                needle_compact = re.sub(r"\s+", "", normalized_needle)
                if (
                    haystack == normalized_needle
                    or normalized_needle in haystack
                    or (needle_compact and needle_compact in haystack_compact)
                ):
                    return True
    return False


def _strip_financial_label_annotations(text: str) -> str:
    normalized = _normalise_spaces(text or "")
    if not normalized:
        return ""
    # Strip footnote-style parentheticals such as "(주25)" or "(*)", but keep
    # other semantic qualifiers intact.
    normalized = re.sub(r"\((?:주\s*\d+[^\)]*|\*)\)", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _strip_leading_period_qualifiers(text: str) -> str:
    normalized = _normalise_spaces(text or "")
    if not normalized:
        return ""
    pattern = re.compile(
        r"^(?:(?:20\d{2}\s*년?)|(?:제\s*\d+\s*기)|(?:당기|전기|현재|이전|직전|이번|금년)(?:\s*연도)?)(?:\s+|$)"
    )
    stripped = normalized
    while True:
        updated = pattern.sub("", stripped, count=1).strip()
        if updated == stripped:
            break
        stripped = updated
    return stripped


def _surface_match_variants(text: str) -> List[str]:
    normalized = _normalise_spaces(text or "")
    if not normalized:
        return []
    variants = [
        normalized,
        _strip_financial_label_annotations(normalized),
        _strip_leading_period_qualifiers(normalized),
        _strip_leading_period_qualifiers(_strip_financial_label_annotations(normalized)),
    ]
    return list(dict.fromkeys(item for item in variants if item))


def _extract_numeric_value_after_operand_text(text: str, operand: Dict[str, Any]) -> str:
    normalized = _normalise_spaces(text or "")
    if not normalized:
        return ""
    value_pattern = re.compile(
        r"[\d,]+(?:\.\d+)?\s*조(?:\s*[\d,]+(?:\.\d+)?\s*억(?:원)?)?"
        r"|[\d,]+(?:\.\d+)?\s*(?:조|억|백만|천)\s*원?"
        r"|[\d,]+(?:\.\d+)?\s*원"
        r"|[\d,]+(?:\.\d+)?"
    )

    def _parenthetical_exact_value_after(value_text: str, end: int) -> str:
        compact_value = re.sub(r"\s+", "", value_text or "")
        if not any(unit in compact_value for unit in ("조", "억")):
            return ""
        tail = normalized[end : end + 40]
        exact_match = re.match(
            r"\s*\(\s*(?P<value>[\d,]+(?:\.\d+)?)\s*(?P<unit>백\s*만\s*원|천\s*원|원)\s*\)",
            tail,
        )
        if not exact_match:
            return ""
        unit = re.sub(r"\s+", "", exact_match.group("unit"))
        return f"{exact_match.group('value')}{unit}"

    def _parenthetical_unit_after(value_text: str, end: int) -> str:
        if re.search(r"(?:조|억|백만|천)\s*원?|원", value_text or ""):
            return ""
        tail = normalized[end : end + 24]
        unit_match = re.match(
            r"\s*\(\s*(?P<unit>조\s*원|억\s*원|백\s*만\s*원|천\s*원|원)\s*\)",
            tail,
        )
        if not unit_match:
            return ""
        unit = re.sub(r"\s+", "", unit_match.group("unit"))
        return f"{_normalise_spaces(value_text)}{unit}"

    def _value_from_match(match: re.Match[str], absolute_end: int) -> str:
        exact_parenthetical = _parenthetical_exact_value_after(match.group(0), absolute_end)
        if exact_parenthetical:
            return exact_parenthetical
        parenthetical_unit = _parenthetical_unit_after(match.group(0), absolute_end)
        if parenthetical_unit:
            return parenthetical_unit
        return _normalise_spaces(match.group(0))

    def _valid_value_matches(surface: str) -> List[re.Match[str]]:
        return [match for match in value_pattern.finditer(surface) if re.search(r"\d", match.group(0))]

    def _recent_parenthetical_exact_value_before(end: int) -> str:
        context = normalized[max(0, end - 140) : end]
        exact_matches = list(
            re.finditer(
                r"[\d,]+(?:\.\d+)?\s*(?:조|억)(?:\s*[\d,]+(?:\.\d+)?\s*억)?\s*원?"
                r"\s*\(\s*(?P<value>[\d,]+(?:\.\d+)?)\s*(?P<unit>백\s*만\s*원|천\s*원|원)\s*\)",
                context,
            )
        )
        if not exact_matches:
            return ""
        exact_match = exact_matches[-1]
        unit = re.sub(r"\s+", "", exact_match.group("unit"))
        return f"{exact_match.group('value')}{unit}"

    for needle in _operand_needles(operand):
        compact = re.sub(r"\s+", "", _normalise_spaces(needle))
        if not compact:
            continue
        spaced_pattern = r"\s*".join(re.escape(char) for char in compact)
        match = re.search(spaced_pattern, normalized)
        if not match:
            continue
        prefix = normalized[: match.start()]
        candidates: List[tuple[int, str]] = []
        prefix_matches = _valid_value_matches(prefix)
        if prefix_matches:
            nearest = prefix_matches[-1]
            if match.start() - nearest.end() <= 20:
                exact_parenthetical = _parenthetical_exact_value_after(nearest.group(0), nearest.end())
                if exact_parenthetical:
                    candidates.append((match.start() - nearest.end(), exact_parenthetical))
                else:
                    recent_exact_parenthetical = _recent_parenthetical_exact_value_before(match.start())
                    if recent_exact_parenthetical:
                        candidates.append((match.start() - nearest.end(), recent_exact_parenthetical))
                    else:
                        candidates.append(
                            (
                                match.start() - nearest.end(),
                                _value_from_match(nearest, nearest.end()),
                            )
                        )
        suffix = normalized[match.end() :]
        suffix_matches = _valid_value_matches(suffix)
        if suffix_matches:
            value_match = suffix_matches[0]
            absolute_end = match.end() + value_match.end()
            candidates.append(
                (
                    value_match.start(),
                    _value_from_match(value_match, absolute_end),
                )
            )
        if candidates:
            return sorted(candidates, key=lambda item: item[0])[0][1]
    return ""


def _operand_row_matches_requirement(row: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    if _operand_row_conflicts_with_requirement(row, operand):
        return False

    bound_role = str(row.get("matched_operand_role") or "").strip()
    operand_role = str(operand.get("role") or "").strip()
    if bound_role and operand_role and _normalise_spaces(bound_role) != _normalise_spaces(operand_role):
        return False

    bound_label = str(row.get("matched_operand_label") or "").strip()
    operand_label = str(operand.get("label") or "").strip()
    if bound_label and operand_label and _normalise_spaces(bound_label) == _normalise_spaces(operand_label):
        return True

    bound_concept = str(row.get("matched_operand_concept") or "").strip()
    operand_concept = str(operand.get("concept") or "").strip()
    if bound_concept and operand_concept and _normalise_spaces(bound_concept) == _normalise_spaces(operand_concept):
        return True

    surfaces = [
        str(row.get("label") or "").strip(),
        str(row.get("source_anchor") or "").strip(),
    ]
    return any(_operand_text_match(surface, operand) for surface in surfaces if surface)


def _missing_required_operands(
    required_operands: List[Dict[str, Any]],
    operand_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    missing: List[Dict[str, Any]] = []
    for operand in required_operands:
        if any(_operand_row_matches_requirement(row, operand) for row in operand_rows):
            continue
        missing.append(dict(operand))
    return missing


def _merge_operand_rows(
    preferred_rows: List[Dict[str, Any]],
    supplemental_rows: List[Dict[str, Any]],
    *,
    required_operands: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Keep trusted rows first and only fill still-missing operands from fallback."""
    merged: List[Dict[str, Any]] = [dict(row) for row in preferred_rows]
    if not supplemental_rows:
        return merged

    remaining_required = _missing_required_operands(required_operands, merged) if required_operands else []
    seen_keys: set[tuple[str, str, str]] = {
        (
            _normalise_spaces(str(row.get("label") or "")),
            _normalise_spaces(str(row.get("period") or "")),
            _normalise_spaces(str(row.get("source_anchor") or "")),
        )
        for row in merged
    }
    covered_required: set[str] = set()

    for row in supplemental_rows:
        candidate = dict(row)
        row_key = (
            _normalise_spaces(str(candidate.get("label") or "")),
            _normalise_spaces(str(candidate.get("period") or "")),
            _normalise_spaces(str(candidate.get("source_anchor") or "")),
        )
        if row_key in seen_keys:
            continue

        matched_operand: Optional[Dict[str, Any]] = None
        for operand in remaining_required:
            label_key = _normalise_spaces(str(operand.get("label") or ""))
            if label_key in covered_required:
                continue
            if _operand_row_matches_requirement(candidate, operand):
                matched_operand = operand
                covered_required.add(label_key)
                break

        if matched_operand is None and required_operands:
            continue

        seen_keys.add(row_key)
        merged.append(candidate)

    return merged


def _extract_table_row_label(row_text: str) -> str:
    normalized = _normalise_spaces(row_text)
    if not normalized:
        return ""
    if "|" in normalized:
        first_cell = _normalise_spaces(normalized.split("|", 1)[0])
        if first_cell:
            return first_cell
    return normalized


def _aggregate_like_row_stage(label: str) -> str:
    compact = re.sub(r"\s+", "", _normalise_spaces(str(label or "")))
    if not compact:
        return "none"
    affinity_policy = dict(STRUCTURED_CELL_AFFINITY_POLICY)
    aggregate_stage_tokens = dict(affinity_policy.get("aggregate_stage_tokens") or {})
    for stage, tokens in aggregate_stage_tokens.items():
        if compact in {re.sub(r"\s+", "", _normalise_spaces(str(token))) for token in tokens}:
            return str(stage)
    return "none"


def _aggregate_like_row_role(label: str) -> str:
    return "aggregate" if _aggregate_like_row_stage(label) != "none" else "detail"


def _parse_unstructured_table_row_cells(row_text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    normalized_row = _normalise_spaces(str(row_text or ""))
    if "|" not in normalized_row:
        return []
    row_parts = [part.strip() for part in normalized_row.split("|")]
    row_parts = [part for part in row_parts if part]
    if len(row_parts) <= 1:
        return []

    header_text = _normalise_spaces(str(metadata.get("table_header_context") or ""))
    header_parts = [part.strip() for part in header_text.split("|") if part.strip()] if "|" in header_text else []
    period_labels = [str(item).strip() for item in (metadata.get("period_labels") or []) if str(item).strip()]

    value_parts = row_parts[1:]
    header_candidates = header_parts[-len(value_parts):] if len(header_parts) >= len(value_parts) else []
    if not header_candidates and len(period_labels) >= len(value_parts):
        header_candidates = period_labels[-len(value_parts):]
    if not header_candidates:
        header_candidates = [f"col_{index}" for index in range(1, len(value_parts) + 1)]

    cells: List[Dict[str, Any]] = []
    for header, value in zip(header_candidates, value_parts):
        raw_value = str(value).strip()
        if not raw_value or not re.search(r"[0-9]", raw_value):
            continue
        value_headers = [str(header).strip()] if str(header).strip() else []
        unit_hint = str(metadata.get("unit_hint") or "").strip()
        labeled_value_match = re.match(
            r"^(?P<label>.*?)(?P<value>[\(\)\-]?\d[\d,]*(?:\.\d+)?)\s*"
            r"(?P<unit>백만원|천원|억원|원|%|퍼센트)?$",
            raw_value,
        )
        if labeled_value_match:
            label = _normalise_spaces(labeled_value_match.group("label") or "")
            if label:
                value_headers.append(label)
            raw_value = _normalise_spaces(labeled_value_match.group("value") or raw_value)
            unit_hint = _normalise_spaces(labeled_value_match.group("unit") or unit_hint)
        cells.append(
            {
                "column_headers": value_headers,
                "row_label": row_parts[0],
                "value_text": raw_value,
                "unit_hint": unit_hint,
            }
        )
    return cells


def _format_structured_candidate_row_text(
    label: str,
    headers: List[str],
    cells: List[Dict[str, Any]],
) -> str:
    row_parts: List[str] = []
    for part in [label, *headers]:
        cleaned = _normalise_spaces(str(part or ""))
        if cleaned and cleaned not in row_parts:
            row_parts.append(cleaned)
    for cell in cells:
        cell_parts = [
            " / ".join(
                _normalise_spaces(str(item))
                for item in (cell.get("column_headers") or [])
                if _normalise_spaces(str(item))
            ),
            _normalise_spaces(str(cell.get("value_text") or "")),
            _normalise_spaces(str(cell.get("unit_hint") or "")),
        ]
        cleaned_cell = _normalise_spaces(" ".join(part for part in cell_parts if part))
        if cleaned_cell:
            row_parts.append(cleaned_cell)
    return " | ".join(row_parts)


def _generic_column_headers() -> set[str]:
    return set(str(item) for item in (HELPER_RUNTIME_POLICY.get("generic_column_headers") or ()) if str(item))


def _build_table_value_reconciliation_candidates(
    *,
    candidate_id_prefix: str,
    anchor: str,
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build value-cell-first candidates from parser-normalized table values."""
    value_records_json = str(metadata.get("table_value_records_json") or "").strip()
    if not value_records_json:
        return []
    try:
        value_records = json.loads(value_records_json)
    except json.JSONDecodeError:
        return []

    header_context = str(metadata.get("table_header_context") or "").strip()
    summary_text = str(metadata.get("table_summary_text") or "").strip()
    local_heading = str(metadata.get("local_heading") or "").strip()
    section_path = str(metadata.get("section_path") or metadata.get("section") or "").strip()
    row_groups: Dict[tuple[Any, str], List[Dict[str, Any]]] = {}
    for record in value_records:
        row_key = (
            record.get("row_index"),
            _normalise_spaces(str(record.get("row_label") or record.get("semantic_label") or "")),
        )
        row_groups.setdefault(row_key, []).append(dict(record))
    for grouped_records in row_groups.values():
        grouped_records.sort(key=lambda current: int(current.get("column_index") or 0))

    candidates: List[Dict[str, Any]] = []
    for idx, record in enumerate(value_records):
        semantic_label = _normalise_spaces(str(record.get("semantic_label") or ""))
        value_text = _normalise_spaces(str(record.get("value_text") or ""))
        if not semantic_label or not value_text or not re.search(r"\d", value_text):
            continue
        period_text = _normalise_spaces(str(record.get("period_text") or ""))
        semantic_aliases = [
            _normalise_spaces(str(item))
            for item in (record.get("semantic_aliases") or [])
            if _normalise_spaces(str(item))
        ]
        row_headers = [
            _normalise_spaces(str(item))
            for item in (record.get("row_headers") or [])
            if _normalise_spaces(str(item))
        ]
        column_headers = [
            _normalise_spaces(str(item))
            for item in (record.get("column_headers") or [])
            if _normalise_spaces(str(item))
        ]
        row_key = (
            record.get("row_index"),
            _normalise_spaces(str(record.get("row_label") or record.get("semantic_label") or "")),
        )
        sibling_records = row_groups.get(row_key) or [dict(record)]
        structured_cell_headers = [period_text] if period_text else list(record.get("period_labels") or []) or column_headers
        sibling_cells: List[Dict[str, Any]] = []
        for sibling in sibling_records:
            sibling_period_text = _normalise_spaces(str(sibling.get("period_text") or ""))
            sibling_column_headers = [
                _normalise_spaces(str(item))
                for item in (sibling.get("column_headers") or [])
                if _normalise_spaces(str(item))
            ]
            sibling_headers = (
                [sibling_period_text]
                if sibling_period_text
                else list(sibling.get("period_labels") or []) or sibling_column_headers
            )
            sibling_cells.append(
                {
                    "column_headers": sibling_headers,
                    "value_text": _normalise_spaces(str(sibling.get("value_text") or "")),
                    "unit_hint": str(sibling.get("unit_hint") or metadata.get("unit_hint") or "").strip(),
                    "value_role": _normalise_spaces(str(sibling.get("value_role") or "")),
                    "aggregation_stage": _normalise_spaces(str(sibling.get("aggregation_stage") or "")),
                    "aggregate_role": _normalise_spaces(str(sibling.get("aggregate_role") or "")),
                    "aggregate_label": _normalise_spaces(str(sibling.get("aggregate_label") or "")),
                }
            )
        composite_text = " ".join(
            part
            for part in (
                semantic_label,
                " ".join(semantic_aliases),
                " ".join(row_headers),
                " ".join(column_headers),
                period_text,
                value_text,
                header_context,
                summary_text,
                local_heading,
                section_path,
                anchor,
            )
            if part
        )
        candidate = _build_reconciliation_candidate(
            candidate_id=f"{candidate_id_prefix}::value:{idx}",
            anchor=anchor,
            text=composite_text,
            metadata=metadata,
            candidate_kind="structured_value",
            row_label=semantic_label,
            row_index=record.get("row_index"),
        )
        candidate["metadata"]["row_headers"] = row_headers
        candidate["metadata"]["column_headers_chain"] = column_headers
        candidate["metadata"]["semantic_label"] = semantic_label
        candidate["metadata"]["semantic_aliases"] = semantic_aliases
        candidate["metadata"]["label_source"] = str(record.get("label_source") or "")
        candidate["metadata"]["value_role"] = _normalise_spaces(str(record.get("value_role") or "detail"))
        candidate["metadata"]["aggregation_stage"] = _normalise_spaces(str(record.get("aggregation_stage") or "none"))
        candidate["metadata"]["aggregate_label"] = _normalise_spaces(str(record.get("aggregate_label") or ""))
        candidate["metadata"]["aggregate_role"] = _normalise_spaces(str(record.get("aggregate_role") or "none"))
        candidate["metadata"]["period_text"] = period_text
        candidate["metadata"]["structured_cells"] = sibling_cells or [
            {
                "column_headers": structured_cell_headers,
                "value_text": value_text,
                "unit_hint": str(record.get("unit_hint") or metadata.get("unit_hint") or "").strip(),
            }
        ]
        candidate["metadata"]["row_text"] = _format_structured_candidate_row_text(
            semantic_label,
            row_headers,
            list(candidate["metadata"]["structured_cells"] or []),
        )
        candidates.append(candidate)
    return candidates


def _column_candidate_label(column_headers: List[str]) -> str:
    cleaned = [_normalise_spaces(header) for header in column_headers if _normalise_spaces(header)]
    if not cleaned:
        return ""
    generic_headers = _generic_column_headers()
    filtered = [header for header in cleaned if header not in generic_headers]
    target = filtered[-1] if filtered else cleaned[-1]
    if re.fullmatch(r"20\d{2}(?:년)?", target):
        return ""
    return target


def _build_table_column_reconciliation_candidates(
    *,
    candidate_id_prefix: str,
    anchor: str,
    metadata: Dict[str, Any],
    row_records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Transpose row records into column-oriented aggregate candidates.

    This is the complement to row-based reconciliation. Some wide DART tables
    store the metric identity in the merged column header chain while each row
    carries period or range context. In that case we synthesize a candidate per
    meaningful column header and attach the row labels as the per-cell period
    headers so the normal direct structured extraction path can still work.
    """
    grouped: Dict[tuple[str, ...], Dict[str, Any]] = {}
    for record in row_records:
        row_label = _normalise_spaces(str(record.get("row_label") or ""))
        row_headers = [row_label] + [
            _normalise_spaces(str(item))
            for item in (record.get("row_headers") or [])
            if _normalise_spaces(str(item)) and _normalise_spaces(str(item)) != row_label
        ]
        for cell in (record.get("cells") or []):
            value_text = _normalise_spaces(str(cell.get("value_text") or ""))
            if not value_text or not re.search(r"\d", value_text):
                continue
            original_headers = [
                _normalise_spaces(str(item))
                for item in (cell.get("column_headers") or [])
                if _normalise_spaces(str(item))
            ]
            label = _column_candidate_label(original_headers)
            if not label:
                continue
            key = tuple(original_headers) or (label,)
            bucket = grouped.setdefault(
                key,
                {
                    "label": label,
                    "column_headers_chain": original_headers,
                    "cells": [],
                },
            )
            transformed_headers = [item for item in row_headers if item]
            if not transformed_headers:
                transformed_headers = [label]
            bucket["cells"].append(
                {
                    "column_headers": transformed_headers,
                    "value_text": value_text,
                    "unit_hint": str(cell.get("unit_hint") or metadata.get("unit_hint") or "").strip(),
                }
            )

    header_context = str(metadata.get("table_header_context") or "").strip()
    summary_text = str(metadata.get("table_summary_text") or "").strip()
    local_heading = str(metadata.get("local_heading") or "").strip()
    section_path = str(metadata.get("section_path") or metadata.get("section") or "").strip()
    candidates: List[Dict[str, Any]] = []
    for idx, bucket in enumerate(grouped.values()):
        cells = [dict(cell) for cell in bucket.get("cells") or [] if dict(cell)]
        if not cells:
            continue
        label = str(bucket.get("label") or "").strip()
        if not label:
            continue
        cell_text = " ".join(
            _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        " / ".join(str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()),
                        str(cell.get("value_text") or "").strip(),
                        str(cell.get("unit_hint") or "").strip(),
                    )
                    if part
                )
            )
            for cell in cells
        )
        full_headers = [str(item).strip() for item in (bucket.get("column_headers_chain") or []) if str(item).strip()]
        composite_text = " ".join(
            part
            for part in (
                label,
                " ".join(full_headers),
                cell_text,
                header_context,
                summary_text,
                local_heading,
                section_path,
                anchor,
            )
            if part
        )
        candidate = _build_reconciliation_candidate(
            candidate_id=f"{candidate_id_prefix}::colrec:{idx}",
            anchor=anchor,
            text=composite_text,
            metadata=metadata,
            candidate_kind="structured_column_value",
            row_label=label,
        )
        candidate["metadata"]["row_headers"] = full_headers
        candidate["metadata"]["column_headers_chain"] = full_headers
        candidate["metadata"]["structured_cells"] = cells
        candidates.append(candidate)
    return candidates


def _build_table_row_reconciliation_candidates(
    *,
    candidate_id_prefix: str,
    anchor: str,
    table_text: str,
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Explode table metadata into row-level reconciliation candidates."""
    header_context = str(metadata.get("table_header_context") or "").strip()
    summary_text = str(metadata.get("table_summary_text") or "").strip()
    local_heading = str(metadata.get("local_heading") or "").strip()
    section_path = str(metadata.get("section_path") or metadata.get("section") or "").strip()
    candidates: List[Dict[str, Any]] = []
    seen_row_texts: set[str] = set()

    value_candidates = _build_table_value_reconciliation_candidates(
        candidate_id_prefix=candidate_id_prefix,
        anchor=anchor,
        metadata=metadata,
    )
    if value_candidates:
        candidates.extend(value_candidates)

    row_records_json = str(metadata.get("table_row_records_json") or "").strip()
    if not row_records_json:
        table_object_json = str(metadata.get("table_object_json") or "").strip()
        if table_object_json:
            try:
                table_object = json.loads(table_object_json)
            except json.JSONDecodeError:
                table_object = {}
            table_rows = table_object.get("rows") if isinstance(table_object, dict) else None
            if isinstance(table_rows, list):
                row_records_json = json.dumps(table_rows, ensure_ascii=False)

    if row_records_json:
        try:
            row_records = json.loads(row_records_json)
        except json.JSONDecodeError:
            row_records = []
        for idx, record in enumerate(row_records):
            row_headers = [str(item).strip() for item in (record.get("row_headers") or []) if str(item).strip()]
            row_label = str(record.get("row_label") or "").strip() or (row_headers[0] if row_headers else "")
            cells = [dict(cell) for cell in (record.get("cells") or []) if dict(cell)]
            if not row_label or not cells:
                continue
            cell_text = " ".join(
                _normalise_spaces(
                    " ".join(
                        part
                        for part in (
                            " / ".join(str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()),
                            str(cell.get("value_text") or "").strip(),
                            str(cell.get("unit_hint") or "").strip(),
                        )
                        if part
                    )
                )
                for cell in cells
            )
            composite_text = " ".join(
                part
                for part in (
                    row_label,
                    " ".join(row_headers),
                    cell_text,
                    header_context,
                    summary_text,
                    local_heading,
                    section_path,
                    anchor,
                )
                if part
            )
            candidate = _build_reconciliation_candidate(
                candidate_id=f"{candidate_id_prefix}::rowrec:{idx}",
                anchor=anchor,
                text=composite_text,
                metadata=metadata,
                candidate_kind="structured_row",
                row_label=row_label,
                row_index=idx,
            )
            candidate["metadata"]["row_headers"] = row_headers
            candidate["metadata"]["semantic_label"] = row_label
            candidate["metadata"]["semantic_aliases"] = [
                item for item in row_headers if _normalise_spaces(item) and _normalise_spaces(item) != _normalise_spaces(row_label)
            ]
            candidate["metadata"]["structured_cells"] = cells
            candidate["metadata"]["row_text"] = _format_structured_candidate_row_text(row_label, row_headers, cells)
            row_text = _normalise_spaces(str(candidate["metadata"].get("row_text") or ""))
            if row_text:
                seen_row_texts.add(row_text)
            candidates.append(candidate)
        column_candidates = _build_table_column_reconciliation_candidates(
            candidate_id_prefix=candidate_id_prefix,
            anchor=anchor,
            metadata=metadata,
            row_records=row_records if isinstance(row_records, list) else [],
        )
        for candidate in column_candidates:
            row_text = _normalise_spaces(str((candidate.get("metadata") or {}).get("row_text") or ""))
            if row_text:
                seen_row_texts.add(row_text)
            candidates.append(candidate)

    rows = [_normalise_spaces(row) for row in str(table_text or "").splitlines() if _normalise_spaces(row)]
    if not rows:
        return candidates

    for idx, row_text in enumerate(rows):
        if "|" not in row_text:
            continue
        if row_text in seen_row_texts:
            continue
        row_label = _extract_table_row_label(row_text)
        inferred_stage = _aggregate_like_row_stage(row_label)
        inferred_role = _aggregate_like_row_role(row_label)
        composite_text = " ".join(
            part
            for part in (
                row_label,
                row_text,
                header_context,
                summary_text,
                local_heading,
                section_path,
                anchor,
            )
            if part
        )
        candidates.append(
            _build_reconciliation_candidate(
                candidate_id=f"{candidate_id_prefix}::row:{idx}",
                anchor=anchor,
                text=composite_text,
                metadata={
                    **metadata,
                    "row_text": row_text,
                    "row_context_text": str(table_text or ""),
                    "structured_cells": _parse_unstructured_table_row_cells(row_text, metadata),
                    "aggregate_label": row_label if inferred_stage != "none" else str(metadata.get("aggregate_label") or "").strip(),
                    "aggregate_role": (
                        "subtotal"
                        if inferred_stage == "subtotal"
                        else "final_total"
                        if inferred_stage == "final"
                        else str(metadata.get("aggregate_role") or "").strip()
                    ),
                    "value_role": (
                        inferred_role
                        if not str(metadata.get("value_role") or "").strip()
                        else str(metadata.get("value_role") or "").strip()
                    ),
                    "aggregation_stage": (
                        inferred_stage
                        if not str(metadata.get("aggregation_stage") or "").strip()
                        else str(metadata.get("aggregation_stage") or "").strip()
                    ),
                },
                candidate_kind="table_row",
                row_label=row_label,
                row_index=idx,
            )
        )
    return candidates


def _candidate_row_block_signature(candidate: Dict[str, Any]) -> str:
    metadata = dict(candidate.get("metadata") or {})
    row_context_text = str(metadata.get("row_context_text") or "").strip()
    if not row_context_text:
        return ""
    try:
        row_index = int(metadata.get("row_index"))
    except (TypeError, ValueError):
        return ""

    rows = [_normalise_spaces(line) for line in row_context_text.splitlines() if _normalise_spaces(line)]
    if row_index < 0 or row_index >= len(rows):
        return ""

    header_end: Optional[int] = None
    for current_index in range(row_index - 1, -1, -1):
        if rows[current_index].startswith("|"):
            header_end = current_index
            break
    if header_end is None:
        return ""

    header_start = header_end
    while header_start - 1 >= 0 and rows[header_start - 1].startswith("|"):
        header_start -= 1

    header_block = " || ".join(rows[header_start : header_end + 1])
    table_source_id = str(metadata.get("table_source_id") or "").strip()
    return f"{table_source_id}::{header_start}:{header_block}".strip(":")


@lru_cache(maxsize=64)
def _cached_report_text(report_path: str) -> str:
    try:
        return Path(report_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


@lru_cache(maxsize=128)
def _resolve_report_path_from_receipt(receipt_no: str, report_year: str = "") -> str:
    receipt_no = str(receipt_no or "").strip()
    report_year = str(report_year or "").strip()
    if not receipt_no:
        return ""
    pattern = f"*_{receipt_no}.html"
    try:
        candidates = sorted(_REPORT_ROOT.rglob(pattern))
    except OSError:
        return ""
    if report_year:
        for candidate in candidates:
            if candidate.name.startswith(f"{report_year}_"):
                return str(candidate)
    return str(candidates[0]) if candidates else ""


def _resolve_candidate_local_unit_hint(candidate: Dict[str, Any], raw_value: str) -> str:
    metadata = dict(candidate.get("metadata") or {})
    receipt_no = str(metadata.get("rcept_no") or "").strip()
    if not receipt_no:
        chunk_uid = str(metadata.get("chunk_uid") or "").strip()
        if ":" in chunk_uid:
            receipt_no = chunk_uid.split(":", 1)[0].strip()
    report_year = str(metadata.get("year") or "").strip()
    if not receipt_no or not str(raw_value or "").strip():
        return ""

    report_path = _resolve_report_path_from_receipt(receipt_no, report_year)
    if not report_path:
        return ""

    report_text = _cached_report_text(report_path)
    if not report_text:
        return ""

    row_label = str(metadata.get("row_label") or "").strip()
    search_value = str(raw_value or "").strip()
    candidate_positions = [match.start() for match in re.finditer(re.escape(search_value), report_text)]
    if row_label:
        narrowed_positions = [
            position
            for position in candidate_positions
            if row_label in report_text[max(0, position - 500) : position + 100]
        ]
        if narrowed_positions:
            candidate_positions = narrowed_positions
    if not candidate_positions:
        return ""

    position = candidate_positions[0]
    window = report_text[max(0, position - 2500) : position]
    unit_matches = list(_UNIT_HINT_HTML_PATTERN.finditer(window))
    if not unit_matches:
        return ""

    resolved = _normalise_spaces(unit_matches[-1].group(1)).replace(" ", "")
    if not resolved:
        return ""
    return resolved


def _candidate_value_role(candidate: Dict[str, Any]) -> str:
    metadata = dict(candidate.get("metadata") or {})
    explicit = _normalise_spaces(str(metadata.get("value_role") or ""))
    if explicit:
        return explicit
    aggregate_role = _normalise_spaces(str(metadata.get("aggregate_role") or ""))
    if aggregate_role == "adjustment":
        return "adjustment"
    if aggregate_role in {"direct_total", "subtotal", "final_total"}:
        return "aggregate"
    inferred_role = _aggregate_like_row_role(
        str(metadata.get("row_label") or metadata.get("semantic_label") or "")
    )
    if inferred_role == "aggregate":
        return inferred_role
    return "detail"


def _candidate_aggregation_stage(candidate: Dict[str, Any]) -> str:
    metadata = dict(candidate.get("metadata") or {})
    explicit = _normalise_spaces(str(metadata.get("aggregation_stage") or ""))
    if explicit:
        return explicit
    aggregate_role = _normalise_spaces(str(metadata.get("aggregate_role") or ""))
    if aggregate_role == "direct_total":
        return "direct"
    if aggregate_role == "subtotal":
        return "subtotal"
    if aggregate_role == "final_total":
        return "final"
    inferred_stage = _aggregate_like_row_stage(
        str(metadata.get("row_label") or metadata.get("semantic_label") or "")
    )
    if inferred_stage != "none":
        return inferred_stage
    return "none"


def _preference_bonus(value: str, preferred: List[str], *, base: float = 0.4) -> float:
    ordered = [_normalise_spaces(item) for item in preferred if _normalise_spaces(item)]
    target = _normalise_spaces(value)
    if not target or target not in ordered:
        return 0.0
    index = ordered.index(target)
    return base * max(len(ordered) - index, 1)


def _candidate_has_numeric_value_signal(candidate: Dict[str, Any]) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
    if structured_cells:
        for cell in structured_cells:
            if re.search(r"\d", str(cell.get("value_text") or "")):
                return True
        return False

    row_text = _normalise_spaces(str(metadata.get("row_text") or ""))
    if row_text and "|" in row_text:
        parts = [part.strip() for part in row_text.split("|")[1:] if part.strip()]
        return any(re.search(r"\d", part) for part in parts)

    return bool(re.search(r"\d", str(candidate.get("text") or "")))


def _candidate_explicit_years(candidate: Dict[str, Any]) -> List[int]:
    metadata = dict(candidate.get("metadata") or {})
    years: set[int] = set()
    period_policy = dict(PERIOD_FOCUS_POLICY)
    scoring_policy = dict(STRUCTURED_CELL_PERIOD_SCORING_POLICY)
    year_pattern = str(period_policy.get("explicit_year_pattern") or r"20\d{2}")
    current_markers = tuple(str(item) for item in (scoring_policy.get("current_positive_markers") or ()) if str(item))
    prior_markers = tuple(str(item) for item in (scoring_policy.get("prior_positive_markers") or ()) if str(item))
    for raw in metadata.get("period_labels") or []:
        years.update(int(token) for token in re.findall(year_pattern, str(raw or "")))
    report_year: Optional[int] = None
    try:
        raw_year = metadata.get("year")
        if raw_year not in (None, ""):
            report_year = int(raw_year)
    except (TypeError, ValueError):
        report_year = None
    for cell in metadata.get("structured_cells") or []:
        cell_data = dict(cell or {})
        for raw in (
            str(cell_data.get("period_text") or ""),
            " ".join(str(item).strip() for item in (cell_data.get("column_headers") or []) if str(item).strip()),
        ):
            years.update(int(token) for token in re.findall(year_pattern, raw))
        if report_year is None:
            continue
        period_headers = _normalise_spaces(
            " ".join(str(item).strip() for item in (cell_data.get("column_headers") or []) if str(item).strip())
        )
        if not period_headers:
            continue
        if any(token in period_headers for token in current_markers):
            years.add(report_year)
        if any(token in period_headers for token in prior_markers):
            years.add(report_year - 1)
    return sorted(years)


def _candidate_is_descriptor_row(candidate: Dict[str, Any]) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    row_label = _normalise_spaces(str(metadata.get("row_label") or ""))
    non_value_row_labels = set(str(item) for item in (HELPER_RUNTIME_POLICY.get("non_value_row_labels") or ()) if str(item))
    if row_label in non_value_row_labels:
        return True

    structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
    if structured_cells and not any(re.search(r"\d", str(cell.get("value_text") or "")) for cell in structured_cells):
        return True

    row_text = _normalise_spaces(str(metadata.get("row_text") or ""))
    if row_text and "|" in row_text:
        parts = [part.strip() for part in row_text.split("|")]
        if parts and _normalise_spaces(parts[0]) in non_value_row_labels:
            numeric_parts = [part for part in parts[1:] if re.search(r"\d", part)]
            if not numeric_parts:
                return True

    return False


def _is_balance_sheet_aggregate_operand(operand: Dict[str, Any]) -> bool:
    needles = {re.sub(r"\s+", "", _normalise_spaces(needle)) for needle in _operand_needles(operand)}
    needles.discard("")
    aggregate_labels = set(
        re.sub(r"\s+", "", _normalise_spaces(str(item)))
        for item in (HELPER_RUNTIME_POLICY.get("balance_sheet_aggregate_labels") or ())
        if str(item)
    )
    return any(needle in aggregate_labels for needle in needles)


def _is_capex_total_operand(operand: Dict[str, Any]) -> bool:
    concept = str(operand.get("concept") or "").strip()
    if concept == "capital_expenditure_total":
        return True
    needles = {re.sub(r"\s+", "", _normalise_spaces(needle)) for needle in _operand_needles(operand)}
    needles.discard("")
    scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
    capex_surfaces = {
        re.sub(r"\s+", "", _normalise_spaces(str(surface)))
        for surface in (scoring_policy.get("capex_total_surfaces") or ())
        if str(surface).strip()
    }
    return any(needle in capex_surfaces for needle in needles)


def _operand_prefers_contextual_aggregate_match(operand: Dict[str, Any]) -> bool:
    binding_policy = dict(operand.get("binding_policy") or {})
    preferred_value_roles = [
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_value_roles") or [])
        if str(item).strip()
    ]
    preferred_aggregation_stages = [
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_aggregation_stages") or [])
        if str(item).strip()
    ]
    if "aggregate" not in preferred_value_roles:
        return False
    if not any(stage in {"final", "subtotal", "direct"} for stage in preferred_aggregation_stages):
        return False
    return bool(_operand_surface_contract(operand).get("positive"))


def _operand_prefers_note_aggregate_lookup(operand: Dict[str, Any]) -> bool:
    preferred_statement_types = {
        _normalise_spaces(str(item))
        for item in (operand.get("preferred_statement_types") or [])
        if str(item).strip()
    }
    if "notes" not in preferred_statement_types:
        return False

    binding_policy = dict(operand.get("binding_policy") or {})
    preferred_value_roles = {
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_value_roles") or [])
        if str(item).strip()
    }
    preferred_aggregation_stages = {
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_aggregation_stages") or [])
        if str(item).strip()
    }
    return "aggregate" in preferred_value_roles and bool(
        {"final", "subtotal", "direct"} & preferred_aggregation_stages
    )


def _candidate_contextual_aggregate_context(candidate: Dict[str, Any]) -> str:
    metadata = dict(candidate.get("metadata") or {})
    return " ".join(
        part
        for part in (
            str(metadata.get("local_heading") or "").strip(),
            str(metadata.get("table_context") or "").strip(),
            str(metadata.get("table_header_context") or "").strip(),
            str(metadata.get("table_summary_text") or "").strip(),
            str(metadata.get("row_context_text") or "").strip(),
            str(metadata.get("section_path") or "").strip(),
        )
        if part
    )


def _candidate_local_aggregate_context(candidate: Dict[str, Any]) -> str:
    metadata = dict(candidate.get("metadata") or {})
    return " ".join(
        part
        for part in (
            str(metadata.get("local_heading") or "").strip(),
            str(metadata.get("table_context") or "").strip(),
            str(metadata.get("table_header_context") or "").strip(),
            str(metadata.get("table_summary_text") or "").strip(),
        )
        if part
    )


def _candidate_consolidation_scope(metadata: Dict[str, Any]) -> str:
    explicit = _normalise_spaces(str(metadata.get("consolidation_scope") or "unknown"))
    if explicit and explicit != "unknown":
        return explicit

    context_text = " ".join(
        part
        for part in (
            str(metadata.get("local_heading") or "").strip(),
            str(metadata.get("table_context") or "").strip(),
            str(metadata.get("section_path") or "").strip(),
            str(metadata.get("table_header_context") or "").strip(),
        )
        if part
    )
    normalized_context = _normalise_spaces(context_text)
    scope_policy = dict(CONSOLIDATION_SCOPE_POLICY)
    context_markers = dict(scope_policy.get("context_markers") or {})
    if any(marker in normalized_context for marker in context_markers.get("consolidated") or ()):
        return "consolidated"
    if any(marker in normalized_context for marker in context_markers.get("separate") or ()):
        return "separate"
    for pattern in scope_policy.get("separate_section_patterns") or ():
        if re.search(str(pattern), normalized_context):
            return "separate"
    return explicit or "unknown"


def _operand_segment_label(operand: Dict[str, Any]) -> str:
    binding_policy = dict(operand.get("binding_policy") or {})
    return _normalise_spaces(str(binding_policy.get("segment_label") or ""))


def _candidate_segment_surfaces(candidate: Dict[str, Any], *, strict: bool = False) -> List[str]:
    metadata = dict(candidate.get("metadata") or {})
    surfaces = [
        str(metadata.get("semantic_label") or "").strip(),
        str(metadata.get("row_label") or "").strip(),
        str(metadata.get("aggregate_label") or "").strip(),
        " ".join(str(item).strip() for item in (metadata.get("semantic_aliases") or []) if str(item).strip()),
        " ".join(str(item).strip() for item in (metadata.get("row_headers") or []) if str(item).strip()),
        str(metadata.get("row_text") or "").strip(),
    ]
    if not strict:
        surfaces.extend(
            [
                str(metadata.get("table_row_labels_text") or "").strip(),
                str(metadata.get("table_context") or "").strip(),
                str(metadata.get("local_heading") or "").strip(),
                str(metadata.get("section_path") or "").strip(),
                str(metadata.get("table_summary_text") or "").strip(),
                str(candidate.get("text") or "").strip(),
                str(candidate.get("source_anchor") or "").strip(),
            ]
        )
    return [_normalise_spaces(surface) for surface in surfaces if _normalise_spaces(surface)]


def _candidate_matches_segment_binding(candidate: Dict[str, Any], operand: Dict[str, Any], *, strict: bool = False) -> bool:
    segment_label = _operand_segment_label(operand)
    if not segment_label:
        return True

    normalized_segment = _normalise_spaces(segment_label)
    compact_segment = re.sub(r"\s+", "", normalized_segment)
    for surface in _candidate_segment_surfaces(candidate, strict=strict):
        compact_surface = re.sub(r"\s+", "", surface)
        if normalized_segment in surface or (compact_segment and compact_segment in compact_surface):
            return True
    return False


def _candidate_has_segment_local_binding(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    segment_label = _operand_segment_label(operand)
    if not segment_label:
        return True
    if _candidate_matches_segment_binding(candidate, operand, strict=True):
        return True
    return _candidate_supports_segment_metric_combo(candidate, operand)


def _candidate_supports_segment_metric_combo(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    segment_label = _operand_segment_label(operand)
    if not segment_label:
        return False
    if not _candidate_matches_segment_binding(candidate, operand, strict=True):
        return False

    metadata = dict(candidate.get("metadata") or {})
    metric_surfaces = [
        str(metadata.get("table_row_labels_text") or "").strip(),
        str(metadata.get("table_context") or "").strip(),
        str(metadata.get("table_summary_text") or "").strip(),
        " ".join(str(item).strip() for item in (metadata.get("column_headers_chain") or []) if str(item).strip()),
    ]
    return any(_operand_text_match(surface, operand) for surface in metric_surfaces if surface)


def _candidate_segment_binding_bonus(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    constraints: Dict[str, Any],
    statement_type: str,
    local_heading: str,
    section_path: str,
) -> float:
    segment_label = _operand_segment_label(operand)
    if not segment_label:
        return 0.0

    score = 0.0
    segment_scope = _normalise_spaces(str((constraints or {}).get("segment_scope") or "none"))
    matches_segment = _candidate_matches_segment_binding(candidate, operand)
    context_text = " ".join(part for part in (local_heading, section_path) if part)
    if matches_segment:
        score += 5.0
        segment_context_terms = tuple(
            str(item)
            for item in (HELPER_RUNTIME_POLICY.get("segment_context_bonus_terms") or ())
            if str(item)
        )
        if any(token in context_text for token in segment_context_terms):
            score += 1.5
        if statement_type in {"notes", "mda"}:
            score += 0.75
    else:
        score -= 4.5
        if segment_scope == "segment" and statement_type in {"summary_financials", "income_statement", "balance_sheet"}:
            score -= 1.5
    return score


def _candidate_source_priority_bonus(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    statement_type: str,
    value_role: str,
    aggregation_stage: str,
    local_heading: str,
) -> float:
    score = 0.0

    if _is_balance_sheet_aggregate_operand(operand):
        if statement_type in {"summary_financials", "balance_sheet"}:
            score += 3.0
            if value_role == "aggregate":
                score += 1.25
            elif value_role == "detail":
                score -= 0.5
            if aggregation_stage in {"direct", "final"}:
                score += 0.75
            scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
            scope_markers = dict(scoring_policy.get("balance_sheet_scope_markers") or {})
            if any(marker in local_heading for marker in scope_markers.get("consolidated") or ()):
                score += 0.5
            elif any(marker in local_heading for marker in scope_markers.get("separate") or ()):
                score -= 0.5
        elif statement_type == "notes":
            score -= 1.5
            if value_role == "detail":
                score -= 1.25

    if _is_capex_total_operand(operand):
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        capex_section_terms = tuple(str(item) for item in (scoring_policy.get("capex_priority_section_terms") or ()) if str(item))
        if any(token in local_heading for token in capex_section_terms):
            score += 2.75
            if value_role == "aggregate":
                score += 1.0
            if aggregation_stage in {"final", "direct", "subtotal"}:
                score += 0.75
        if statement_type == "cash_flow":
            score -= 2.5
            if value_role != "aggregate":
                score -= 0.5

    if _operand_prefers_contextual_aggregate_match(operand):
        context_text = _candidate_local_aggregate_context(candidate)
        if (
            value_role == "aggregate"
            and aggregation_stage in {"final", "subtotal", "direct"}
            and _text_has_positive_surface(context_text, operand)
        ):
            score += 2.0
        elif value_role == "detail" and _text_has_positive_surface(context_text, operand):
            score -= 1.0

    if _operand_prefers_note_aggregate_lookup(operand):
        candidate_kind = _normalise_spaces(str(candidate.get("candidate_kind") or ""))
        metadata = dict(candidate.get("metadata") or {})
        row_context_text = str(metadata.get("row_context_text") or "")
        if statement_type == "notes":
            if candidate_kind == "structured_value":
                if value_role == "aggregate" and aggregation_stage == "final":
                    score += 2.75
                elif value_role == "aggregate" and aggregation_stage == "subtotal":
                    score += 1.5
                elif value_role == "aggregate" and aggregation_stage == "direct":
                    score += 1.0
            elif candidate_kind == "table_row":
                score -= 1.0
                if row_context_text and len(row_context_text) > 2500:
                    score -= 0.75
                if value_role != "aggregate":
                    score -= 0.5

    return score


def _candidate_period_table_coherence_bonus(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
) -> float:
    metadata = dict(candidate.get("metadata") or {})
    years = _candidate_explicit_years(candidate)
    if not years:
        return 0.0

    score = 0.0
    target_years = _operand_target_years(operand, query_years)
    if target_years:
        if any(year in years for year in target_years):
            score += 1.0
        else:
            score -= 1.0

    role = str(operand.get("role") or "").strip()
    if role in {"current_period", "prior_period"} and len(years) >= 2:
        score += 0.75
        if str(metadata.get("table_source_id") or "").strip():
            score += 0.35

    desired_unit_family = str(operand.get("unit_family") or "").strip().upper()
    if desired_unit_family == "PERCENT" and len(years) >= 2:
        score += 0.5

    return score


def _binding_policy_allows_candidate_shape(
    *,
    value_role: str,
    aggregation_stage: str,
    operand_binding_policy: Dict[str, Any],
) -> bool:
    normalized_value_role = _normalise_spaces(value_role)
    normalized_stage = _normalise_spaces(aggregation_stage)
    avoid_value_roles = {
        _normalise_spaces(str(item))
        for item in (operand_binding_policy.get("avoid_value_roles") or [])
        if str(item).strip()
    }
    avoid_aggregation_stages = {
        _normalise_spaces(str(item))
        for item in (operand_binding_policy.get("avoid_aggregation_stages") or [])
        if str(item).strip()
    }
    if normalized_value_role and normalized_value_role in avoid_value_roles:
        return False
    if normalized_stage and normalized_stage in avoid_aggregation_stages:
        return False

    preferred_value_roles = {
        _normalise_spaces(str(item))
        for item in (operand_binding_policy.get("prefer_value_roles") or [])
        if str(item).strip()
    }
    preferred_aggregation_stages = {
        _normalise_spaces(str(item))
        for item in (operand_binding_policy.get("prefer_aggregation_stages") or [])
        if str(item).strip()
    }
    if preferred_value_roles and normalized_value_role not in preferred_value_roles:
        return False
    if preferred_aggregation_stages and normalized_stage not in preferred_aggregation_stages:
        return False
    return True


def _table_row_has_matching_structured_sibling(metadata: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    for key in ("table_row_records_json", "table_value_records_json"):
        payload = str(metadata.get(key) or "").strip()
        if not payload:
            continue
        try:
            records = json.loads(payload)
        except json.JSONDecodeError:
            continue
        for record in records:
            surfaces = [
                str(record.get("row_label") or "").strip(),
                str(record.get("semantic_label") or "").strip(),
                " ".join(str(item).strip() for item in (record.get("row_headers") or []) if str(item).strip()),
                " ".join(str(item).strip() for item in (record.get("semantic_aliases") or []) if str(item).strip()),
            ]
            if any(_operand_text_match(surface, operand) for surface in surfaces if surface):
                return True
    return False


def _candidate_is_direct_grounding_candidate(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    constraints: Dict[str, Any],
    query_years: List[int],
    operation_family: str = "",
    report_scope: Optional[Dict[str, Any]] = None,
) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    candidate_kind = str(candidate.get("candidate_kind") or "").strip()
    if candidate_kind not in {"structured_value", "structured_row", "structured_column_value", "table_row"}:
        return False
    if _candidate_is_descriptor_row(candidate):
        return False
    if not _candidate_has_numeric_value_signal(candidate):
        return False

    direct_match_strength = _candidate_direct_match_strength(candidate, operand)
    if direct_match_strength < 1.0:
        return False

    operand_binding_policy = dict(operand.get("binding_policy") or {})
    value_role = _candidate_value_role(candidate)
    aggregation_stage = _candidate_aggregation_stage(candidate)
    statement_type = str(metadata.get("statement_type") or "unknown").strip()
    if not _binding_policy_allows_candidate_shape(
        value_role=value_role,
        aggregation_stage=aggregation_stage,
        operand_binding_policy=operand_binding_policy,
    ):
        return False

    if _lookup_prefers_canonical_statement_rows(operand) and candidate_kind == "table_row":
        if statement_type not in {"income_statement", "summary_financials", "notes"}:
            return False

    desired_consolidation = str((constraints or {}).get("consolidation_scope") or "unknown").strip()
    if desired_consolidation == "unknown":
        desired_consolidation = str(operand_binding_policy.get("prefer_consolidation_scope") or "unknown").strip()
    candidate_consolidation = _candidate_consolidation_scope(metadata)
    if (
        desired_consolidation != "unknown"
        and candidate_consolidation != "unknown"
        and candidate_consolidation != desired_consolidation
    ):
        return False

    desired_period_focus = _operand_period_focus(
        operand,
        str((constraints or {}).get("period_focus") or "unknown").strip(),
    )
    if desired_period_focus == "unknown":
        desired_period_focus = str(operand_binding_policy.get("prefer_period_focus") or "unknown").strip()
    semantic_label = _normalise_spaces(str(metadata.get("semantic_label") or metadata.get("row_label") or ""))
    if desired_period_focus in {"current", "prior"} and _is_delta_like_row_label(semantic_label):
        return False
    if not _candidate_matches_segment_binding(candidate, operand, strict=True):
        return False
    if not _candidate_matches_target_report_scope(
        candidate,
        operand=operand,
        query_years=query_years,
        report_scope=dict(report_scope or {}),
    ):
        return False
    candidate_period_focus = str(metadata.get("period_focus") or "unknown").strip()
    row_text = _normalise_spaces(str(metadata.get("row_text") or ""))
    trust_candidate_period_focus = (
        candidate_period_focus in {"current", "prior"}
        or not (candidate_kind == "table_row" and row_text)
    )
    target_year_match = _candidate_matches_operand_target_year(candidate, operand, query_years)
    if trust_candidate_period_focus:
        if desired_period_focus == "current" and candidate_period_focus == "prior" and not target_year_match:
            return False
        if desired_period_focus == "prior" and candidate_period_focus == "current" and not target_year_match:
            return False

    if operation_family in {"lookup", "single_value"} and candidate_kind == "table_row":
        if _table_row_has_matching_structured_sibling(metadata, operand):
            return False
        if row_text and _is_delta_like_row_label(row_text):
            return False

    return True


def _candidate_satisfies_direct_acceptance_contract(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    constraints: Dict[str, Any],
    query_years: List[int],
    operation_family: str = "",
    selected_cell: Optional[Dict[str, Any]] = None,
    report_scope: Optional[Dict[str, Any]] = None,
) -> bool:
    if not _candidate_is_direct_grounding_candidate(
        candidate,
        operand=operand,
        constraints=constraints,
        query_years=query_years,
        operation_family=operation_family,
        report_scope=report_scope,
    ):
        return False

    metadata = dict(candidate.get("metadata") or {})
    desired_period_focus = _operand_period_focus(
        operand,
        str((constraints or {}).get("period_focus") or "unknown").strip(),
    )
    if selected_cell:
        period_policy = dict(PERIOD_FOCUS_POLICY)
        period_presence_pattern = str(period_policy.get("period_presence_pattern") or period_policy.get("explicit_year_pattern") or r"$^")
        current_markers = tuple(str(item) for item in (period_policy.get("current_markers") or ()) if str(item))
        prior_markers = tuple(str(item) for item in (period_policy.get("prior_markers") or ()) if str(item))
        explicit_year_pattern = str(period_policy.get("explicit_year_pattern") or r"20\d{2}")
        period_text = _structured_cell_period_text(
            selected_cell,
            query_years,
            desired_period_focus,
        )
        candidate_period_focus = _normalise_spaces(str(metadata.get("period_focus") or ""))
        if desired_period_focus == "current" and candidate_period_focus == "prior":
            return False
        if desired_period_focus == "prior" and candidate_period_focus == "current":
            return False
        if not re.search(period_presence_pattern, period_text):
            report_year: Optional[int] = None
            for raw_year in (
                selected_cell.get("_report_year"),
                selected_cell.get("report_year"),
                selected_cell.get("year"),
            ):
                try:
                    if raw_year not in (None, ""):
                        report_year = int(raw_year)
                        break
                except (TypeError, ValueError):
                    continue
            if report_year is not None:
                target_years = _operand_target_years(operand, query_years)
                if target_years and report_year in target_years:
                    period_text = str(report_year)
                else:
                    period_text = str(report_year)
        normalized_period = _normalise_spaces(period_text)
        if desired_period_focus == "current" and normalized_period and any(
            token in normalized_period for token in prior_markers
        ):
            return False
        if desired_period_focus == "prior" and normalized_period and any(
            token in normalized_period for token in current_markers
        ):
            return False
        target_years = _operand_target_years(operand, query_years)
        explicit_years = [int(token) for token in re.findall(explicit_year_pattern, period_text or "")]
        if target_years and explicit_years and not any(year in explicit_years for year in target_years):
            return False

    binding_policy = dict(operand.get("binding_policy") or {})
    if bool(
        binding_policy.get("require_surface_contract_for_direct_match")
        or binding_policy.get("require_surface_contract_for_direct_lookup")
    ) and not _candidate_has_required_surface_contract(
        candidate,
        operand,
        selected_cell=selected_cell,
    ):
        return False

    if operation_family in {"lookup", "single_value"}:
        desired_unit_family = _normalise_spaces(str(operand.get("unit_family") or "")).upper()
        candidate_unit_family = _candidate_selected_unit_family(candidate, selected_cell=selected_cell)
        if (
            desired_unit_family in {"KRW", "USD", "COUNT", "PERCENT"}
            and candidate_unit_family
            and candidate_unit_family != desired_unit_family
        ):
            return False
        direct_match_strength = _candidate_direct_match_strength(candidate, operand)
        if direct_match_strength < 2.0:
            return False

    statement_type = str(metadata.get("statement_type") or "unknown").strip()
    value_role = _candidate_value_role(candidate)
    aggregation_stage = _candidate_aggregation_stage(candidate)
    local_heading = _normalise_spaces(
        str(metadata.get("local_heading") or metadata.get("table_context") or metadata.get("section_path") or "")
    )
    section_path = _normalise_spaces(str(metadata.get("section_path") or ""))
    if operation_family in {"lookup", "single_value"} and _lookup_prefers_canonical_statement_rows(operand):
        canonical_types, canonical_sections = _lookup_canonical_statement_preferences(operand)
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        note_markers = tuple(str(item) for item in (scoring_policy.get("note_context_markers") or ()) if str(item))
        note_context = any(marker in local_heading or marker in section_path for marker in note_markers)
        allows_note_canonical = any(
            marker in _normalise_spaces(section)
            for section in canonical_sections
            for marker in note_markers
        )
        canonical_statement_type_hit = (
            bool(canonical_types)
            and statement_type in canonical_types
            and statement_type not in {"notes", "unknown"}
        )
        canonical_section_hit = bool(canonical_sections) and any(
            _normalise_spaces(section_term) in local_heading or _normalise_spaces(section_term) in section_path
            for section_term in canonical_sections
            if _normalise_spaces(section_term)
        )
        if canonical_types and statement_type not in canonical_types:
            return False
        if note_context and not allows_note_canonical and not canonical_section_hit:
            return False
        if canonical_sections and (local_heading or section_path) and not canonical_section_hit and not canonical_statement_type_hit:
            return False
    if _is_balance_sheet_aggregate_operand(operand):
        if statement_type == "notes" and value_role == "detail":
            return False
    if _is_capex_total_operand(operand):
        preferred_sections = [
            _normalise_spaces(str(item))
            for item in (operand.get("preferred_sections") or [])
            if str(item).strip()
        ]
        aggregate_like = value_role == "aggregate" or aggregation_stage in {"final", "direct", "subtotal"}
        if candidate.get("candidate_kind") in {"structured_value", "structured_column_value"} and not aggregate_like:
            return False
        if preferred_sections:
            in_preferred_section = any(
                section_term in local_heading or section_term in section_path
                for section_term in preferred_sections
                if section_term
            )
            if not in_preferred_section and not aggregate_like:
                return False

    metadata_periods = [str(item).strip() for item in (metadata.get("period_labels") or []) if str(item).strip()]
    target_years = _operand_target_years(operand, query_years)
    if desired_period_focus == "prior" and target_years and metadata_periods:
        flattened = " ".join(metadata_periods)
        explicit_years = [int(token) for token in re.findall(r"20\d{2}", flattened)]
        if explicit_years and not any(year in explicit_years for year in target_years):
            return False

    return True


def _candidate_selected_unit_family(
    candidate: Dict[str, Any],
    *,
    selected_cell: Optional[Dict[str, Any]] = None,
) -> str:
    metadata = dict(candidate.get("metadata") or {})
    raw_value = _normalise_spaces(
        str(
            (selected_cell or {}).get("value_text")
            or metadata.get("value_text")
            or metadata.get("raw_value")
            or ""
        )
    )
    raw_unit = _normalise_spaces(
        str(
            (selected_cell or {}).get("unit_hint")
            or metadata.get("unit_hint")
            or metadata.get("raw_unit")
            or ""
        )
    )
    if raw_value or raw_unit:
        _, normalized_unit = _normalise_operand_value(raw_value or "1", raw_unit)
        if normalized_unit and normalized_unit != "UNKNOWN":
            return normalized_unit
    label_text = _normalise_spaces(
        " ".join(
            str(part or "").strip()
            for part in (
                metadata.get("semantic_label"),
                metadata.get("row_label"),
                metadata.get("aggregate_label"),
            )
            if str(part or "").strip()
        )
    )
    if _label_implies_percent_metric(label_text):
        return "PERCENT"
    return ""


def _candidate_matches_operand(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    if _candidate_conflicts_with_operand_concept(candidate, operand):
        return False

    candidate_kind = str(candidate.get("candidate_kind") or "").strip()
    structured_candidate = candidate_kind in {
        "structured_value",
        "structured_row",
        "structured_column_value",
        "table_row",
        "evidence_row",
    }
    metadata = dict(candidate.get("metadata") or {})
    row_label = str(metadata.get("row_label") or "").strip()
    if _operand_text_match(row_label, operand):
        return True
    semantic_label = str(metadata.get("semantic_label") or "").strip()
    if _operand_text_match(semantic_label, operand):
        return True
    semantic_aliases = " ".join(
        str(item).strip()
        for item in (metadata.get("semantic_aliases") or [])
        if str(item).strip()
    )
    if _operand_text_match(semantic_aliases, operand):
        return True
    row_headers = " ".join(str(item).strip() for item in (metadata.get("row_headers") or []) if str(item).strip())
    if _operand_text_match(row_headers, operand):
        return True
    aggregate_label = str(metadata.get("aggregate_label") or "").strip()
    if _operand_text_match(aggregate_label, operand):
        return True
    if candidate_kind != "table_row" and _operand_text_match(str(metadata.get("table_row_labels_text") or ""), operand):
        return True
    if _is_capex_total_operand(operand):
        section_context = " ".join(
            part
            for part in (
                str(metadata.get("local_heading") or "").strip(),
                str(metadata.get("table_context") or "").strip(),
                str(metadata.get("section_path") or "").strip(),
                str(metadata.get("row_context_text") or "").strip(),
                str(candidate.get("text") or "").strip(),
            )
            if part
        )
        preferred_sections = [
            _normalise_spaces(str(item))
            for item in (operand.get("preferred_sections") or [])
            if str(item).strip()
        ]
        if preferred_sections and any(section in _normalise_spaces(section_context) for section in preferred_sections):
            if (
                _text_has_positive_surface(section_context, operand)
                and (_candidate_value_role(candidate) == "aggregate" or _candidate_aggregation_stage(candidate) in {"final", "direct", "subtotal"})
            ):
                return True
    if _operand_prefers_contextual_aggregate_match(operand):
        section_context = _candidate_local_aggregate_context(candidate)
        aggregate_surface = _normalise_spaces(
            " ".join(
                part
                for part in (
                    str(metadata.get("aggregate_label") or "").strip(),
                    str(metadata.get("row_label") or "").strip(),
                    str(metadata.get("semantic_label") or "").strip(),
                )
                if part
            )
        )
        aggregate_like = (
            _candidate_value_role(candidate) == "aggregate"
            or _candidate_aggregation_stage(candidate) in {"final", "subtotal"}
            or _aggregate_like_row_stage(aggregate_surface) != "none"
        )
        if (
            _text_has_positive_surface(section_context, operand)
            and aggregate_like
        ):
            return True
    if structured_candidate:
        return False
    return _operand_text_match(str(candidate.get("text") or ""), operand)


def _is_delta_like_row_label(label: str) -> bool:
    text = _normalise_spaces(str(label or ""))
    if not text:
        return False
    scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
    delta_markers = tuple(str(item) for item in (scoring_policy.get("delta_row_markers") or ()) if str(item))
    return any(token in text for token in delta_markers)


def _candidate_direct_match_strength(candidate: Dict[str, Any], operand: Dict[str, Any]) -> float:
    """Score how directly a candidate label represents the requested operand."""
    if _candidate_conflicts_with_operand_concept(candidate, operand):
        return 0.0

    metadata = dict(candidate.get("metadata") or {})
    candidate_kind = _normalise_spaces(str(candidate.get("candidate_kind") or ""))
    surfaces: List[tuple[str, float]] = [
        (str(metadata.get("semantic_label") or "").strip(), 3.0),
        (str(metadata.get("row_label") or "").strip(), 2.5),
        (
            " ".join(
                str(item).strip()
                for item in (metadata.get("semantic_aliases") or [])
                if str(item).strip()
            ),
            2.0,
        ),
        (
            " ".join(
                str(item).strip()
                for item in (metadata.get("row_headers") or [])
                if str(item).strip()
            ),
            1.5,
        ),
        (str(metadata.get("aggregate_label") or "").strip(), 1.0),
    ]
    if candidate_kind != "table_row":
        surfaces.extend(
            [
                (str(metadata.get("table_row_labels_text") or "").strip(), 1.25),
                (str(metadata.get("row_text") or "").strip(), 1.0),
            ]
        )
    best = 0.0
    for surface, exact_bonus in surfaces:
        normalized_surface = _normalise_spaces(surface)
        if not normalized_surface:
            continue
        surface_variants = set(_surface_match_variants(normalized_surface))
        if any(_normalise_spaces(needle) == normalized_surface for needle in _operand_needles(operand)):
            best = max(best, exact_bonus)
            continue
        if any(
            needle_variant in surface_variants
            for needle in _operand_needles(operand)
            for needle_variant in _surface_match_variants(needle)
        ):
            best = max(best, exact_bonus)
            continue
        if _operand_text_match(normalized_surface, operand):
            best = max(best, exact_bonus * 0.5)
    if _is_capex_total_operand(operand):
        context_text = " ".join(
            part
            for part in (
                str(metadata.get("local_heading") or "").strip(),
                str(metadata.get("table_context") or "").strip(),
                str(metadata.get("section_path") or "").strip(),
                str(metadata.get("row_context_text") or "").strip(),
                str(candidate.get("text") or "").strip(),
            )
            if part
        )
        context_surfaces = [
            str(metadata.get("local_heading") or "").strip(),
            str(metadata.get("table_context") or "").strip(),
            str(metadata.get("section_path") or "").strip(),
        ]
        preferred_sections = [
            _normalise_spaces(str(item))
            for item in (operand.get("preferred_sections") or [])
            if str(item).strip()
        ]
        if preferred_sections and any(
            section in _normalise_spaces(surface)
            for section in preferred_sections
            for surface in context_surfaces
            if _normalise_spaces(surface)
        ):
            if (
                _text_has_positive_surface(context_text, operand)
                and (_candidate_value_role(candidate) == "aggregate" or _candidate_aggregation_stage(candidate) in {"final", "direct", "subtotal"})
            ):
                best = max(best, 2.25)
    if _operand_prefers_contextual_aggregate_match(operand):
        context_text = _candidate_local_aggregate_context(candidate)
        if (
            _text_has_positive_surface(context_text, operand)
            and (_candidate_value_role(candidate) == "aggregate" or _candidate_aggregation_stage(candidate) in {"final", "direct", "subtotal"})
        ):
            best = max(best, 2.0)
    aggregate_signal = _normalise_spaces(
        " ".join(
            part
            for part in (
                str(metadata.get("aggregate_label") or "").strip(),
                str(metadata.get("semantic_label") or "").strip(),
                str(metadata.get("row_label") or "").strip(),
            )
            if part
        )
    )
    if (
        aggregate_signal
        and _operand_text_match(aggregate_signal, operand)
        and _candidate_value_role(candidate) == "aggregate"
        and _candidate_aggregation_stage(candidate) in {"direct", "final", "subtotal"}
    ):
        best = max(best, 2.25)
    if (
        aggregate_signal
        and _operand_lookup_surface_match(aggregate_signal, operand)
        and _candidate_has_operand_context_surface(candidate, operand)
        and _candidate_value_role(candidate) == "aggregate"
        and _candidate_aggregation_stage(candidate) in {"direct", "final", "subtotal"}
    ):
        best = max(best, 2.25)
    if _candidate_supports_segment_metric_combo(candidate, operand):
        best = max(best, 2.25)
    return best


def _score_operand_candidate(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    preferred_statement_types: List[str],
    constraints: Dict[str, Any],
    query_years: List[int],
    report_scope: Optional[Dict[str, Any]] = None,
) -> float:
    """Rank candidate rows/chunks for a single operand.

    The scorer is deterministic on purpose: it gives the graph a stable first
    pass before any optional LLM reranking is considered.
    """
    metadata = dict(candidate.get("metadata") or {})
    if _candidate_conflicts_with_operand_concept(candidate, operand):
        return -10.0

    score = 0.0
    row_label = str(metadata.get("row_label") or "").strip()
    semantic_label = _normalise_spaces(str(metadata.get("semantic_label") or row_label))
    operand_binding_policy = dict(operand.get("binding_policy") or {})
    if row_label:
        row_label_variants = set(_surface_match_variants(row_label))
        if any(
            needle_variant in row_label_variants
            for needle in _operand_needles(operand)
            for needle_variant in _surface_match_variants(needle)
        ):
            score += 3.0
        elif _operand_text_match(row_label, operand):
            score += 1.5
    score += _candidate_direct_match_strength(candidate, operand)
    candidate_kind = str(candidate.get("candidate_kind") or "")
    if candidate_kind == "structured_value":
        score += 2.5
    elif candidate_kind == "structured_row":
        score += 2.0
    elif candidate_kind == "structured_column_value":
        score += 1.75
    elif candidate_kind == "table_row":
        score += 1.0
    elif candidate_kind == "evidence_row":
        score += 0.5
    elif candidate_kind == "chunk":
        score -= 0.25

    if candidate_kind in {"structured_value", "structured_row", "structured_column_value", "table_row"}:
        direct_match_strength = _candidate_direct_match_strength(candidate, operand)
        if direct_match_strength >= 2.5:
            score += 1.25
        elif direct_match_strength >= 1.5:
            score += 0.5

    value_role = _candidate_value_role(candidate)
    aggregation_stage = _candidate_aggregation_stage(candidate)
    if aggregation_stage == "final":
        score += 1.5
    elif aggregation_stage == "direct":
        score += 1.25
    elif aggregation_stage == "subtotal":
        score += 0.5
    elif value_role == "adjustment":
        score -= 1.5

    aggregate_signal = " ".join(
        part
        for part in (
            semantic_label,
            row_label,
            _normalise_spaces(str(metadata.get("aggregate_label") or "")),
            " ".join(str(item).strip() for item in (metadata.get("column_headers_chain") or []) if str(item).strip()),
        )
        if part
    )
    if value_role == "aggregate" and aggregation_stage in {"direct", "final"} and _operand_text_match(aggregate_signal, operand):
        score += 2.0
    elif value_role == "aggregate" and aggregation_stage == "subtotal" and _operand_text_match(aggregate_signal, operand):
        score += 0.75

    if _candidate_has_numeric_value_signal(candidate):
        score += 1.0

    if _candidate_is_descriptor_row(candidate):
        score -= 3.0

    statement_type = str(metadata.get("statement_type") or "unknown").strip()
    operand_preferred_statement_types = [
        str(item).strip()
        for item in (operand.get("preferred_statement_types") or [])
        if str(item).strip()
    ]
    if preferred_statement_types:
        if statement_type in preferred_statement_types:
            score += 2.5
        elif statement_type != "unknown":
            score -= 0.8
    if operand_preferred_statement_types:
        if statement_type in operand_preferred_statement_types:
            score += 1.5
        elif statement_type != "unknown":
            score -= 0.35

    local_heading = _normalise_spaces(
        str(metadata.get("local_heading") or metadata.get("table_context") or metadata.get("section_path") or "")
    )
    section_path = _normalise_spaces(str(metadata.get("section_path") or ""))
    if _lookup_prefers_canonical_statement_rows(operand):
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        canonical_types, canonical_sections = _lookup_canonical_statement_preferences(operand)
        canonical_section_hit = bool(canonical_sections) and any(
            _normalise_spaces(section_term) in local_heading or _normalise_spaces(section_term) in section_path
            for section_term in canonical_sections
            if _normalise_spaces(section_term)
        )
        note_markers = tuple(str(item) for item in (scoring_policy.get("note_context_markers") or ()) if str(item))
        note_context = any(marker in local_heading or marker in section_path for marker in note_markers)
        allows_note_canonical = any(
            marker in _normalise_spaces(section)
            for marker in note_markers
            for section in canonical_sections
        )
        if statement_type == "income_statement":
            score += 1.0
        elif statement_type == "summary_financials":
            score += 0.5
        elif statement_type == "notes":
            score -= 0.5
        if canonical_section_hit:
            score += 1.0
        elif note_context and not allows_note_canonical:
            score -= 2.5

        related_party_context = " ".join(
            part
            for part in (
                str(metadata.get("table_context") or "").strip(),
                str(metadata.get("table_row_labels_text") or "").strip(),
                str(metadata.get("section_path") or "").strip(),
                str(metadata.get("local_heading") or "").strip(),
                " ".join(str(item).strip() for item in (metadata.get("semantic_aliases") or []) if str(item).strip()),
                " ".join(str(item).strip() for item in (metadata.get("column_headers_chain") or []) if str(item).strip()),
            )
            if part
        )
        related_party_terms = tuple(str(item) for item in (scoring_policy.get("related_party_penalty_terms") or ()) if str(item))
        if any(token in related_party_context for token in related_party_terms):
            score -= 3.0
        stripped_row_label = _strip_financial_label_annotations(row_label)
        stripped_needles = {_strip_financial_label_annotations(needle) for needle in _operand_needles(operand)}
        generic_suffix_terms = tuple(str(item) for item in (scoring_policy.get("generic_suffix_penalty_terms") or ()) if str(item))
        if stripped_row_label and any(token in stripped_row_label for token in generic_suffix_terms) and stripped_row_label not in stripped_needles:
            score -= 1.5

    desired_consolidation = str((constraints or {}).get("consolidation_scope") or "unknown").strip()
    candidate_consolidation = _candidate_consolidation_scope(metadata)
    desired_period_focus = _operand_period_focus(operand, str((constraints or {}).get("period_focus") or "unknown").strip())
    if desired_consolidation == "unknown":
        desired_consolidation = str(operand_binding_policy.get("prefer_consolidation_scope") or "unknown").strip()
    if desired_period_focus == "unknown":
        desired_period_focus = str(operand_binding_policy.get("prefer_period_focus") or "unknown").strip()
    if desired_period_focus in {"current", "prior"} and _is_delta_like_row_label(semantic_label or row_label):
        score -= 4.0
    candidate_period_focus = str(metadata.get("period_focus") or "unknown").strip()
    score += _candidate_segment_binding_bonus(
        candidate,
        operand=operand,
        constraints=constraints,
        statement_type=statement_type,
        local_heading=local_heading,
        section_path=section_path,
    )
    if desired_consolidation != "unknown":
        if candidate_consolidation == desired_consolidation:
            score += 2.0
        elif candidate_consolidation != "unknown":
            score -= 2.0
        elif desired_consolidation == "consolidated":
            context_markers = dict(CONSOLIDATION_SCOPE_POLICY.get("context_markers") or {})
            consolidated_markers = tuple(str(item) for item in (context_markers.get("consolidated") or ()) if str(item))
            separate_markers = tuple(str(item) for item in (context_markers.get("separate") or ()) if str(item))
            if any(marker in local_heading for marker in consolidated_markers):
                score += 1.5
            elif any(marker in local_heading for marker in separate_markers):
                score -= 1.5
        elif desired_consolidation == "separate":
            context_markers = dict(CONSOLIDATION_SCOPE_POLICY.get("context_markers") or {})
            consolidated_markers = tuple(str(item) for item in (context_markers.get("consolidated") or ()) if str(item))
            separate_markers = tuple(str(item) for item in (context_markers.get("separate") or ()) if str(item))
            if any(marker in local_heading for marker in separate_markers):
                score += 1.5
            elif any(marker in local_heading for marker in consolidated_markers):
                score -= 1.5

    if desired_period_focus == "current":
        if candidate_period_focus == "current":
            score += 2.5
        elif candidate_period_focus == "prior":
            if _candidate_matches_operand_target_year(candidate, operand, query_years):
                score += 0.5
            else:
                score -= 2.5
    elif desired_period_focus == "prior":
        if candidate_period_focus == "prior":
            score += 2.5
        elif candidate_period_focus == "current":
            if _candidate_matches_operand_target_year(candidate, operand, query_years):
                score += 0.5
            else:
                score -= 2.5

    preferred_value_roles = [
        str(item).strip()
        for item in (operand_binding_policy.get("prefer_value_roles") or [])
        if str(item).strip()
    ]
    avoid_value_roles = {
        _normalise_spaces(str(item))
        for item in (operand_binding_policy.get("avoid_value_roles") or [])
        if str(item).strip()
    }
    preferred_aggregation_stages = [
        str(item).strip()
        for item in (operand_binding_policy.get("prefer_aggregation_stages") or [])
        if str(item).strip()
    ]
    avoid_aggregation_stages = {
        _normalise_spaces(str(item))
        for item in (operand_binding_policy.get("avoid_aggregation_stages") or [])
        if str(item).strip()
    }
    score += _preference_bonus(value_role, preferred_value_roles, base=0.6)
    score += _preference_bonus(aggregation_stage, preferred_aggregation_stages, base=0.5)
    if _normalise_spaces(value_role) in avoid_value_roles:
        score -= 2.0
    if _normalise_spaces(aggregation_stage) in avoid_aggregation_stages:
        score -= 1.75

    operand_preferred_sections = [
        str(item).strip()
        for item in (operand.get("preferred_sections") or [])
        if str(item).strip()
    ]
    if operand_preferred_sections:
        if any(
            _normalise_spaces(section_term) in local_heading or _normalise_spaces(section_term) in section_path
            for section_term in operand_preferred_sections
        ):
            score += 0.75

    score += _candidate_source_priority_bonus(
        candidate,
        operand=operand,
        statement_type=statement_type,
        value_role=value_role,
        aggregation_stage=aggregation_stage,
        local_heading=local_heading,
    )

    score += _metadata_period_match_strength(list(metadata.get("period_labels") or []), query_years) * 1.5
    score += _candidate_period_table_coherence_bonus(
        candidate,
        operand=operand,
        query_years=query_years,
    )
    score += _candidate_report_scope_binding_bonus(
        candidate,
        operand=operand,
        query_years=query_years,
        report_scope=dict(report_scope or {}),
    )

    if str(metadata.get("table_source_id") or "").strip():
        score += 0.25

    return score


def _build_reconciliation_retry_queries(
    *,
    active_subtask: Dict[str, Any],
    missing_operands: List[str],
    years: List[int],
) -> List[str]:
    def _strip_leading_period_prefix(text: str) -> str:
        return _normalise_spaces(re.sub(rf"^{KOREAN_PERIOD_PREFIX_RE_FRAGMENT}\s+", "", _normalise_spaces(text or "")))

    def _strip_prefix_overlap(surface: str, prefix_values: List[str]) -> str:
        normalized = _normalise_spaces(surface)
        for prefix in prefix_values:
            normalized_prefix = _normalise_spaces(prefix)
            if normalized_prefix and normalized.startswith(f"{normalized_prefix} "):
                normalized = normalized[len(normalized_prefix) :].strip()
        return normalized

    def _metric_context_for_surface(surface: str, metric: str) -> str:
        normalized_surface = _normalise_spaces(surface)
        normalized_metric = _normalise_spaces(metric)
        if not normalized_surface or not normalized_metric:
            return normalized_metric
        surface_base = _strip_leading_period_prefix(normalized_surface)
        metric_base = _strip_leading_period_prefix(normalized_metric)
        if surface_base and metric_base and (surface_base == metric_base or metric_base in surface_base):
            return ""
        return normalized_metric

    metric_label = str(active_subtask.get("metric_label") or "").strip()
    constraints = dict(active_subtask.get("constraints") or {})
    required_operands = list(active_subtask.get("required_operands") or [])
    operand_map = {str(item.get("label") or "").strip(): item for item in required_operands if str(item.get("label") or "").strip()}

    prefixes: List[str] = []
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    year_suffix_template = str(period_policy.get("year_suffix_template") or "{year}")
    if years:
        prefixes.append(year_suffix_template.format(year=years[0]))
    consolidation_scope = str(constraints.get("consolidation_scope") or "unknown").strip()
    scope_prefix_labels = dict(CONSOLIDATION_SCOPE_POLICY.get("query_prefix_labels") or {})
    if consolidation_scope == "consolidated":
        prefixes.append(str(scope_prefix_labels.get("consolidated") or ""))
    elif consolidation_scope == "separate":
        prefixes.append(str(scope_prefix_labels.get("separate") or ""))

    queries: List[str] = []
    for operand_label in missing_operands:
        spec = dict(operand_map.get(operand_label) or {})
        aliases = [str(item).strip() for item in (spec.get("aliases") or []) if str(item).strip()]
        query_surfaces: List[str] = [
            operand_label,
            *aliases,
            *[
                str(item).strip()
                for item in _lookup_query_surface_preferences(spec)
                if str(item).strip()
            ],
        ]
        preferred_sections = [
            str(item).strip()
            for item in (
                *list(spec.get("preferred_sections") or []),
                *list(active_subtask.get("preferred_sections") or []),
            )
            if str(item).strip()
        ]
        if _lookup_prefers_canonical_statement_rows(spec):
            canonical_types, canonical_sections = _lookup_canonical_statement_preferences(spec)
            del canonical_types  # section-only use here
            preferred_sections = list(dict.fromkeys([*canonical_sections, *preferred_sections]))
        binding_policy = dict(spec.get("binding_policy") or {})
        preferred_value_roles = {
            _normalise_spaces(str(item))
            for item in (binding_policy.get("prefer_value_roles") or [])
            if str(item).strip()
        }
        if "aggregate" in preferred_value_roles:
            aggregate_expansions: List[str] = []
            for surface in list(query_surfaces):
                normalized_surface = _strip_financial_label_annotations(surface)
                if not normalized_surface:
                    continue
                aggregate_expansions.extend(
                    [
                        f"{normalized_surface} 합계",
                        f"합계 {normalized_surface}",
                        f"{normalized_surface} 총계",
                    ]
                )
            query_surfaces.extend(aggregate_expansions)
        deduped_surfaces = list(dict.fromkeys(_normalise_spaces(surface) for surface in query_surfaces if _normalise_spaces(surface)))
        for surface in deduped_surfaces[:4]:
            normalized_surface = _strip_prefix_overlap(surface, prefixes)
            metric_context = _metric_context_for_surface(normalized_surface, metric_label)
            base_bits = prefixes + [normalized_surface]
            if metric_context:
                base_bits.append(metric_context)
            base_query = _normalise_spaces(" ".join(base_bits))
            if base_query:
                queries.append(base_query)
            for section in preferred_sections[:2]:
                queries.append(_normalise_spaces(f"{base_query} {section}"))
    return list(dict.fromkeys(item for item in queries if item))


def _deterministic_reconcile_task(
    *,
    active_subtask: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    years: List[int],
    reconciliation_retry_count: int,
    report_scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Match required operands to the best available candidates.

    Output from this function is not yet a final operand set. It is a ranked
    and explainable candidate selection that later calculation stages can
    convert into normalized operand rows.
    """
    if not active_subtask:
        return {
            "status": "ready",
            "task_id": "",
            "matched_operands": [],
            "missing_operands": [],
            "retry_queries": [],
            "notes": ["no_active_subtask"],
        }

    preferred_statement_types = [str(item).strip() for item in (active_subtask.get("preferred_statement_types") or []) if str(item).strip()]
    constraints = dict(active_subtask.get("constraints") or {})
    operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
    required_operands = [dict(item) for item in (active_subtask.get("required_operands") or []) if bool(item.get("required", True))]

    matched_operands: List[Dict[str, Any]] = []
    missing_operands: List[str] = []
    operand_top_candidates: Dict[str, List[Dict[str, Any]]] = {}

    for operand in required_operands:
        label = str(operand.get("label") or "").strip()
        matches = [candidate for candidate in candidates if _candidate_matches_operand(candidate, operand)]
        if _operand_segment_label(operand):
            segment_local_matches = [
                candidate
                for candidate in matches
                if _candidate_has_segment_local_binding(candidate, operand)
            ]
            if segment_local_matches:
                matches = segment_local_matches
        ranked = sorted(
            matches,
            key=lambda candidate: _score_operand_candidate(
                candidate,
                operand=operand,
                preferred_statement_types=preferred_statement_types,
                constraints=constraints,
                query_years=years,
                report_scope=report_scope,
            ),
            reverse=True,
        )
        operand_top_candidates[label] = ranked
        requires_direct_grounding = operation_family in {"lookup", "single_value"}
        if ranked:
            direct_candidates: List[Dict[str, Any]] = []
            if requires_direct_grounding:
                period_focus = _operand_period_focus(
                    operand,
                    str((constraints or {}).get("period_focus") or "unknown").strip(),
                )
                direct_entries: List[Dict[str, Any]] = []
                for candidate in ranked:
                    selected_cell = _candidate_selected_cell_for_operand(
                        candidate,
                        operand=operand,
                        query_years=years,
                        period_focus=period_focus,
                    )
                    if not _candidate_satisfies_direct_acceptance_contract(
                        candidate,
                        operand=operand,
                        constraints=constraints,
                        query_years=years,
                        operation_family=operation_family,
                        selected_cell=selected_cell,
                        report_scope=report_scope,
                    ):
                        continue
                    direct_entries.append(
                        {
                            "candidate": candidate,
                            "logical_signature": _candidate_direct_logical_signature(
                                candidate,
                                selected_cell=selected_cell,
                            ),
                            "family_signature": _candidate_direct_family_signature(
                                candidate,
                                selected_cell=selected_cell,
                            ),
                            "selected_value_text": _normalise_spaces(
                                str((selected_cell or {}).get("value_text") or "")
                            ),
                            "score": _score_operand_candidate(
                                candidate,
                                operand=operand,
                                preferred_statement_types=preferred_statement_types,
                                constraints=constraints,
                                query_years=years,
                                report_scope=report_scope,
                            ),
                            "canonical_winner": _candidate_is_canonical_statement_winner(
                                candidate,
                                operand=operand,
                                query_years=years,
                            ),
                        }
                    )
                collapsed_entries: List[Dict[str, Any]] = []
                if direct_entries:
                    family_signatures = {
                        tuple(entry.get("family_signature") or ())
                        for entry in direct_entries
                        if tuple(entry.get("family_signature") or ())
                    }
                    distinct_values = {
                        str(entry.get("selected_value_text") or "").strip()
                        for entry in direct_entries
                        if str(entry.get("selected_value_text") or "").strip()
                    }
                    if len(family_signatures) == 1 and len(distinct_values) <= 1:
                        collapsed_entries = sorted(
                            direct_entries,
                            key=lambda entry: (
                                bool(entry.get("canonical_winner")),
                                float(entry.get("score") or 0.0),
                            ),
                            reverse=True,
                        )[:1]
                    else:
                        best_by_signature: Dict[tuple[str, str, str, str], Dict[str, Any]] = {}
                        for entry in direct_entries:
                            signature = tuple(entry.get("logical_signature") or ())
                            existing = best_by_signature.get(signature)
                            if existing is None or (
                                bool(entry.get("canonical_winner")),
                                float(entry.get("score") or 0.0),
                            ) > (
                                bool(existing.get("canonical_winner")),
                                float(existing.get("score") or 0.0),
                                ):
                                    best_by_signature[signature] = entry
                        collapsed_entries = list(best_by_signature.values())
                        sibling_surfaces = [
                            str(item).strip()
                            for item in (active_subtask.get("sibling_lookup_surfaces") or [])
                            if str(item).strip()
                        ]
                        if len(collapsed_entries) > 1 and sibling_surfaces:
                            sibling_ranked_entries = sorted(
                                collapsed_entries,
                                key=lambda entry: (
                                    _candidate_sibling_surface_hit_count(
                                        dict(entry.get("candidate") or {}),
                                        sibling_surfaces,
                                    ),
                                    float(entry.get("score") or 0.0),
                                ),
                                reverse=True,
                            )
                            top_sibling_hits = _candidate_sibling_surface_hit_count(
                                dict(sibling_ranked_entries[0].get("candidate") or {}),
                                sibling_surfaces,
                            )
                            if top_sibling_hits > 0:
                                collapsed_entries = [
                                    entry
                                    for entry in sibling_ranked_entries
                                    if _candidate_sibling_surface_hit_count(
                                        dict(entry.get("candidate") or {}),
                                        sibling_surfaces,
                                    )
                                    == top_sibling_hits
                                ]
                        canonical_entries = [
                            entry for entry in collapsed_entries if bool(entry.get("canonical_winner"))
                        ]
                        if len(canonical_entries) == 1:
                            collapsed_entries = canonical_entries
                        elif len(collapsed_entries) > 1:
                            ranked_by_priority = sorted(
                                collapsed_entries,
                                key=lambda entry: (
                                    _direct_candidate_semantic_priority(
                                        dict(entry.get("candidate") or {}),
                                        operand=operand,
                                        preferred_statement_types=preferred_statement_types,
                                        query_years=years,
                                    ),
                                    float(entry.get("score") or 0.0),
                                ),
                                reverse=True,
                            )
                            top_priority = _direct_candidate_semantic_priority(
                                dict(ranked_by_priority[0].get("candidate") or {}),
                                operand=operand,
                                preferred_statement_types=preferred_statement_types,
                                query_years=years,
                            )
                            next_priority = _direct_candidate_semantic_priority(
                                dict(ranked_by_priority[1].get("candidate") or {}),
                                operand=operand,
                                preferred_statement_types=preferred_statement_types,
                                query_years=years,
                            )
                            if top_priority > next_priority:
                                collapsed_entries = [ranked_by_priority[0]]
                            else:
                                ranked_collapsed = sorted(
                                    collapsed_entries,
                                    key=lambda entry: (
                                        bool(entry.get("canonical_winner")),
                                        float(entry.get("score") or 0.0),
                                    ),
                                    reverse=True,
                                )
                                top_score = float(ranked_collapsed[0].get("score") or 0.0)
                                next_score = float(ranked_collapsed[1].get("score") or 0.0)
                                if top_score >= next_score + 0.75:
                                    collapsed_entries = [ranked_collapsed[0]]
                                else:
                                    collapsed_entries = ranked_collapsed
                direct_candidates = [dict(entry.get("candidate") or {}) for entry in collapsed_entries]
            else:
                direct_candidates = [
                    candidate
                    for candidate in ranked
                    if _candidate_is_direct_grounding_candidate(
                        candidate,
                        operand=operand,
                        constraints=constraints,
                        query_years=years,
                        operation_family=operation_family,
                        report_scope=report_scope,
                    )
                ]
            direct_candidate = direct_candidates[0] if len(direct_candidates) == 1 else None
            if direct_candidate:
                direct_candidate_id = str(direct_candidate.get("candidate_id") or "").strip()
                top = [direct_candidate]
                top.extend(
                    candidate
                    for candidate in ranked
                    if str(candidate.get("candidate_id") or "").strip() != direct_candidate_id
                )
                top = top[:3]
                matched_operands.append(
                    {
                        "label": label,
                        "role": str(operand.get("role") or "").strip(),
                        "concept": str(operand.get("concept") or "").strip(),
                        "matched": True,
                        "candidate_ids": [str(item.get("candidate_id") or "") for item in top if str(item.get("candidate_id") or "").strip()],
                            "reason": "matched_direct_candidate" if requires_direct_grounding else "matched_candidates",
                        }
                    )
            else:
                top = direct_candidates[:3] if direct_candidates else ranked[:3]
                if requires_direct_grounding:
                    missing_operands.append(label)
                    matched_operands.append(
                        {
                            "label": label,
                            "role": str(operand.get("role") or "").strip(),
                            "concept": str(operand.get("concept") or "").strip(),
                            "matched": False,
                            "candidate_ids": [str(item.get("candidate_id") or "") for item in top if str(item.get("candidate_id") or "").strip()],
                            "reason": "ambiguous_direct_grounding_candidates" if direct_candidates else "no_direct_grounding_candidate",
                        }
                    )
                else:
                    matched_operands.append(
                        {
                            "label": label,
                            "role": str(operand.get("role") or "").strip(),
                            "concept": str(operand.get("concept") or "").strip(),
                            "matched": True,
                            "candidate_ids": [str(item.get("candidate_id") or "") for item in top if str(item.get("candidate_id") or "").strip()],
                            "reason": "matched_candidates",
                        }
                    )
        else:
            missing_operands.append(label)
            matched_operands.append(
                {
                    "label": label,
                    "role": str(operand.get("role") or "").strip(),
                    "concept": str(operand.get("concept") or "").strip(),
                    "matched": False,
                    "candidate_ids": [],
                    "reason": "no_matching_candidate",
                }
            )

    notes: List[str] = []
    common_table_ids: Optional[set[str]] = None
    for label, ranked in operand_top_candidates.items():
        table_ids = {
            str(item.get("metadata", {}).get("table_source_id") or "").strip()
            for item in ranked[:5]
            if str(item.get("metadata", {}).get("table_source_id") or "").strip()
        }
        if not table_ids:
            continue
        common_table_ids = table_ids if common_table_ids is None else (common_table_ids & table_ids)
    if common_table_ids:
        notes.append("same_table_candidate_available")

    if not missing_operands:
        return {
            "status": "ready",
            "task_id": str(active_subtask.get("task_id") or ""),
            "matched_operands": matched_operands,
            "missing_operands": [],
            "retry_queries": [],
            "notes": notes,
        }

    if reconciliation_retry_count < 1:
        retry_queries = _build_reconciliation_retry_queries(
            active_subtask=active_subtask,
            missing_operands=missing_operands,
            years=years,
        )
        return {
            "status": "retry_retrieval",
            "task_id": str(active_subtask.get("task_id") or ""),
            "matched_operands": matched_operands,
            "missing_operands": missing_operands,
            "retry_queries": retry_queries,
            "notes": notes + ["retry_once_for_missing_operands"],
        }

    return {
        "status": "insufficient_operands",
        "task_id": str(active_subtask.get("task_id") or ""),
        "matched_operands": matched_operands,
        "missing_operands": missing_operands,
        "retry_queries": [],
        "notes": notes + ["retry_exhausted"],
    }


def _preferred_calc_sections(query: str, topic: str, intent: str) -> List[str]:
    if intent not in {"comparison", "trend"}:
        return []
    return get_financial_ontology().preferred_sections(query, topic, intent)


def _is_percent_point_difference_query(text: str) -> bool:
    normalized = _normalise_spaces(text)
    policy = dict(PERCENT_POINT_DIFFERENCE_POLICY)
    direct_markers = tuple(str(item) for item in (policy.get("direct_markers") or ()) if str(item))
    if any(marker in normalized for marker in direct_markers):
        return True
    ratio_metric_markers = tuple(str(item) for item in (policy.get("ratio_metric_markers") or ()) if str(item))
    ratio_metric = any(keyword in normalized for keyword in ratio_metric_markers)
    if not ratio_metric:
        return False
    comparison_markers = tuple(str(item) for item in (policy.get("comparison_markers") or ()) if str(item))
    return any(marker in normalized for marker in comparison_markers)


def _should_coerce_percent_point_unit(
    query: str,
    operands: List[Dict[str, Any]],
    plan_data: Dict[str, Any],
) -> bool:
    if not _is_percent_point_difference_query(query):
        return False
    if str(plan_data.get("mode") or "") != "single_value":
        return False
    ordered_ids = [str(item or "") for item in (plan_data.get("ordered_operand_ids") or []) if str(item or "").strip()]
    if len(ordered_ids) < 2:
        return False
    operand_map = {str(row.get("operand_id") or ""): row for row in operands}
    selected = [operand_map.get(operand_id) for operand_id in ordered_ids]
    if any(row is None for row in selected):
        return False
    if not all(str((row or {}).get("normalized_unit") or "").upper() == "PERCENT" for row in selected):
        return False
    operation = str(plan_data.get("operation") or "").strip().lower()
    formula = _normalise_spaces(str(plan_data.get("formula") or ""))
    return operation == "subtract" or "-" in formula


def _extract_value_near_match(text: str, start: int, end: int) -> tuple[Optional[str], str]:
    tail = text[end : min(len(text), end + 120)]
    if not tail:
        return None, ""
    tail = _normalise_spaces(tail)
    value_policy = dict(VALUE_NEAR_MATCH_POLICY)
    match = re.search(str(value_policy.get("value_pattern") or r"$^"), tail)
    if not match:
        return None, ""
    raw_value = _normalise_spaces(match.group(1))
    percent_markers = tuple(str(item) for item in (value_policy.get("percent_markers") or ()) if str(item))
    million_krw_unit = str(value_policy.get("million_krw_unit") or "")
    composite_markers = tuple(str(item) for item in (value_policy.get("composite_krw_markers") or ()) if str(item))
    composite_unit = str(value_policy.get("composite_krw_unit") or "")
    if any(marker in raw_value for marker in percent_markers):
        return raw_value, percent_markers[0] if percent_markers else ""
    if million_krw_unit and million_krw_unit in raw_value:
        return raw_value.replace(million_krw_unit, "").strip(), million_krw_unit
    if any(marker in raw_value for marker in composite_markers):
        return raw_value, composite_unit
    return raw_value, ""


def _supplement_section_terms_for_query(query: str, topic: str, intent: str) -> List[str]:
    sections: List[str] = []
    if intent not in {"comparison", "trend"}:
        return list(dict.fromkeys(sections))
    sections.extend(get_financial_ontology().supplement_sections(query, topic, intent))
    return list(dict.fromkeys(sections))


# ---------------------------------------------------------------------------
# Retrieval-hint helpers
# ---------------------------------------------------------------------------

def _active_preferred_sections(state: Dict[str, Any], query: str, topic: str, intent: str) -> List[str]:
    """Resolve section hints for the active task or top-level query."""
    sections = [
        str(item).strip()
        for item in (dict(state.get("active_subtask") or {}).get("preferred_sections") or [])
        if str(item).strip()
    ]
    if not sections:
        _statement_types, query_sections = _infer_statement_and_section_hints(query)
        sections.extend(query_sections)
    sections.extend(_preferred_calc_sections(query, topic, intent))
    return list(dict.fromkeys(sections))


def _active_preferred_statement_types(state: Dict[str, Any], query: str, topic: str) -> List[str]:
    types = [
        str(item).strip()
        for item in (dict(state.get("active_subtask") or {}).get("preferred_statement_types") or [])
        if str(item).strip()
    ]
    types.extend(_desired_statement_types(query, topic))
    return list(dict.fromkeys(types))


def _retrieval_hint_from_topic(query: str, topic: str, intent: str) -> str:
    hints: List[str] = []
    if intent not in {"comparison", "trend"}:
        return " ".join(dict.fromkeys(hints))
    hints.extend(get_financial_ontology().query_hints(query, topic, intent))
    return " ".join(dict.fromkeys(hints))


