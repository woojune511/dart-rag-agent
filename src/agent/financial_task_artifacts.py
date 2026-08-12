"""Task/artifact ledger projection helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Sequence

from src.agent.financial_artifact_contracts import (
    REQUIRED_ARTIFACT_KINDS_BY_TASK_KIND,
    critic_report_acceptance_state,
    payload_has_provenance,
    payload_missing_contract,
    reconciliation_result_status,
)
from src.agent.financial_runtime_normalization import _clean_source_row_ids, _normalise_spaces
from src.agent.financial_row_surfaces import _operand_text_match
from src.agent.financial_surface_contracts import _operand_needles
from src.schema.runtime_enums import ArtifactKind, TaskKind, TaskStatus

if TYPE_CHECKING:
    from src.agent.financial_graph_state import FinancialAgentState

__all__ = [
    "AggregateArtifactProjectionPayloadSyncInput",
    "AggregateArtifactProjectionPayloadSyncResult",
    "aggregate_answer_artifact_update",
    "calculation_plan_artifact_update",
    "calculation_result_artifact_update",
    "evidence_items_with_runtime",
    "enrich_reconciliation_artifact_refs",
    "synchronize_calculation_result_artifact",
    "next_reflection_task_id",
    "operand_set_artifact_update",
    "reconciliation_result_artifact_update",
    "ratio_result_rows_from_task_artifacts",
    "reflection_report_artifact_update",
    "semantic_plan_artifact_update",
    "synchronize_aggregate_artifact_projection_payload",
    "supersede_task_with_aggregate_result",
    "project_task_artifact_trace",
    "reconciliation_artifact_candidate_ids",
    "reconciliation_artifact_candidate_ids_for_operand",
    "reconciliation_evidence_refs",
]


@dataclass(frozen=True)
class AggregateArtifactProjectionPayloadSyncInput:
    """Prepared aggregate artifact payload replacement inputs."""

    artifacts: Sequence[Mapping[str, Any]]
    artifact_id: str
    final_answer: str
    aggregate_projection: Mapping[str, Any]


@dataclass(frozen=True)
class AggregateArtifactProjectionPayloadSyncResult:
    """Fresh artifact records after the first matching payload replacement."""

    artifacts: List[Dict[str, Any]]


def evidence_items_with_runtime(
    evidence_items: List[Dict[str, Any]],
    state: FinancialAgentState,
) -> List[Dict[str, Any]]:
    combined = list(evidence_items)
    existing_ids = {
        str(item.get("evidence_id") or "").strip()
        for item in combined
        if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
    }
    for item in state.get("runtime_evidence") or []:
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("evidence_id") or "").strip()
        if evidence_id and evidence_id in existing_ids:
            continue
        if evidence_id:
            existing_ids.add(evidence_id)
        combined.append(dict(item))
    return combined


def ratio_result_rows_from_task_artifacts(
    state: FinancialAgentState,
    task: Dict[str, Any],
) -> List[Dict[str, Any]]:
    task_id = _normalise_spaces(str(task.get("task_id") or ""))
    if not task_id:
        return []
    rows: List[Dict[str, Any]] = []
    for artifact in list(state.get("artifacts") or []):
        artifact_data = dict(artifact or {})
        if _normalise_spaces(str(artifact_data.get("task_id") or "")) != task_id:
            continue
        if _normalise_spaces(str(artifact_data.get("kind") or "")) != ArtifactKind.CALCULATION_RESULT.value:
            continue
        payload = dict(artifact_data.get("payload") or {})
        calculation_result = dict(payload.get("calculation_result") or {})
        if not calculation_result:
            continue
        answer = _normalise_spaces(
            str(
                calculation_result.get("formatted_result")
                or calculation_result.get("rendered_value")
                or artifact_data.get("summary")
                or ""
            )
        )
        rows.append(
            {
                "task_id": task_id,
                "metric_family": task.get("metric_family") or "concept_ratio",
                "metric_label": task.get("metric_label") or task.get("target_metric") or "",
                "operation_family": "ratio",
                "status": calculation_result.get("status") or artifact_data.get("status") or "",
                "answer": answer,
                "calculation_result": calculation_result,
                "calculation_operands": payload.get("calculation_operands") or [],
                "source_row_ids": calculation_result.get("source_row_ids") or artifact_data.get("evidence_refs") or [],
                "source_evidence_ids": calculation_result.get("source_evidence_ids") or artifact_data.get("evidence_refs") or [],
                "artifact_backed_complete_result": True,
            }
        )
    return rows


def synchronize_aggregate_artifact_projection_payload(
    sync_input: AggregateArtifactProjectionPayloadSyncInput,
) -> AggregateArtifactProjectionPayloadSyncResult:
    """Replace one prepared aggregate artifact payload without ledger access."""

    artifacts = sync_input.artifacts
    artifact_id = sync_input.artifact_id
    final_answer = sync_input.final_answer
    aggregate_projection = sync_input.aggregate_projection
    updated_artifacts = [dict(item) for item in (artifacts or [])]
    for index, artifact in enumerate(updated_artifacts):
        if str((artifact or {}).get("artifact_id") or "") != artifact_id:
            continue
        payload = dict((artifact or {}).get("payload") or {})
        payload.update(
            {
                "final_answer": final_answer,
                "calculation_operands": list(aggregate_projection.get("calculation_operands") or []),
                "calculation_plan": dict(aggregate_projection.get("calculation_plan") or {}),
                "calculation_result": dict(aggregate_projection.get("calculation_result") or {}),
            }
        )
        updated_artifacts[index] = {
            **dict(artifact),
            "summary": final_answer[:200],
            "payload": payload,
        }
        break
    return AggregateArtifactProjectionPayloadSyncResult(artifacts=updated_artifacts)


def _calculation_operand_source_refs(operand_rows: List[Dict[str, Any]]) -> List[str]:
    refs: List[str] = []
    for row in operand_rows or []:
        if not isinstance(row, dict):
            continue
        refs.extend(
            _clean_source_row_ids(
                [
                    row.get("evidence_id"),
                    row.get("evidence_ids"),
                    row.get("source_evidence_id"),
                    row.get("source_evidence_ids"),
                    row.get("source_row_id"),
                    row.get("source_row_ids"),
                    row.get("row_id"),
                    row.get("row_ids"),
                    row.get("candidate_id"),
                    row.get("candidate_ids"),
                ]
            )
        )
    return list(dict.fromkeys(refs))


def enrich_reconciliation_artifact_refs(
    artifacts: List[Dict[str, Any]],
    *,
    task_id: str,
    operand_rows: List[Dict[str, Any]],
    extra_refs: Optional[List[Any]] = None,
    task_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    refs = list(
        dict.fromkeys(
            [
                *_calculation_operand_source_refs(operand_rows),
                *_clean_source_row_ids(extra_refs or []),
            ]
        )
    )
    if not refs:
        return artifacts
    target_task_id = str(task_id or "").strip()
    target_task_ids = {
        str(value).strip()
        for value in [target_task_id, *(task_ids or [])]
        if str(value).strip()
    }
    updated: List[Dict[str, Any]] = []
    for artifact in artifacts or []:
        item = dict(artifact)
        if str(item.get("kind") or "").strip() != ArtifactKind.RECONCILIATION_RESULT.value:
            updated.append(item)
            continue
        if target_task_ids and str(item.get("task_id") or "").strip() not in target_task_ids:
            updated.append(item)
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        result = payload.get("reconciliation_result") if isinstance(payload, dict) else {}
        status = str(result.get("status") if isinstance(result, dict) else "").strip().lower()
        if status not in {"ok", "ready"}:
            updated.append(item)
            continue
        merged_refs = list(dict.fromkeys([*(item.get("evidence_refs") or []), *refs]))
        item["evidence_refs"] = merged_refs
        updated.append(item)
    return updated


def _artifact_text_matches_operand_surface(text: str, operand: Dict[str, Any]) -> bool:
    normalized_text = _normalise_spaces(str(text or ""))
    if not normalized_text:
        return False
    if _operand_text_match(normalized_text, operand):
        return True
    compact_text = re.sub(r"\s+", "", normalized_text)
    for needle in _operand_needles(operand):
        normalized_needle = _normalise_spaces(str(needle or ""))
        if not normalized_needle:
            continue
        compact_needle = re.sub(r"\s+", "", normalized_needle)
        if compact_needle and (compact_needle in compact_text or compact_text in compact_needle):
            return True
    return False


def reconciliation_artifact_candidate_ids_for_operand(
    state: FinancialAgentState,
    *,
    operand: Dict[str, Any],
) -> List[str]:
    candidate_ids: List[str] = []
    seen: set[str] = set()

    def append_candidate_id(raw_value: Any) -> None:
        candidate_id = str(raw_value or "").strip()
        if candidate_id and candidate_id not in seen:
            seen.add(candidate_id)
            candidate_ids.append(candidate_id)

    for artifact in list(state.get("artifacts") or []):
        artifact_data = dict(artifact or {})
        kind = str(artifact_data.get("kind") or "").strip()
        if "reconciliation_result" not in kind:
            continue

        payload = dict(artifact_data.get("payload") or {})
        reconciliation_result = dict(payload.get("reconciliation_result") or {})
        matched_operands = [
            dict(item)
            for item in (reconciliation_result.get("matched_operands") or [])
            if isinstance(item, dict)
        ]
        matched_operand_seen = False
        for match_entry in matched_operands:
            match_surfaces = [
                str(match_entry.get("label") or ""),
                str(match_entry.get("concept") or ""),
                str(match_entry.get("role") or ""),
            ]
            if not any(
                _artifact_text_matches_operand_surface(surface, operand)
                for surface in match_surfaces
                if str(surface).strip()
            ):
                continue
            matched_operand_seen = True
            for candidate_id in list(match_entry.get("candidate_ids") or []):
                append_candidate_id(candidate_id)

        if matched_operand_seen:
            continue
        for evidence_ref in list(artifact_data.get("evidence_refs") or []):
            append_candidate_id(evidence_ref)

    return candidate_ids


def reconciliation_artifact_candidate_ids(state: FinancialAgentState) -> List[str]:
    candidate_ids: List[str] = []
    seen: set[str] = set()

    def append_candidate_id(raw_value: Any) -> None:
        candidate_id = str(raw_value or "").strip()
        if candidate_id and candidate_id not in seen:
            seen.add(candidate_id)
            candidate_ids.append(candidate_id)

    reconciliation_result = dict(state.get("reconciliation_result") or {})
    for key in ("evidence_refs", "source_evidence_ids"):
        for evidence_ref in list(reconciliation_result.get(key) or []):
            append_candidate_id(evidence_ref)

    for artifact in list(state.get("artifacts") or []):
        artifact_data = dict(artifact or {})
        kind = str(artifact_data.get("kind") or "").strip()
        if "reconciliation_result" not in kind:
            continue
        for evidence_ref in list(artifact_data.get("evidence_refs") or []):
            append_candidate_id(evidence_ref)
        payload = dict(artifact_data.get("payload") or {})
        artifact_result = dict(payload.get("reconciliation_result") or {})
        for key in ("evidence_refs", "source_evidence_ids"):
            for evidence_ref in list(artifact_result.get(key) or []):
                append_candidate_id(evidence_ref)

    return candidate_ids


def reconciliation_evidence_refs(result: Dict[str, Any]) -> List[str]:
    values: List[Any] = []
    for item in result.get("matched_operands") or []:
        if not isinstance(item, dict):
            continue
        values.extend(
            [
                item.get("candidate_ids"),
                item.get("candidate_id"),
                item.get("source_row_ids"),
                item.get("source_row_id"),
                item.get("source_evidence_ids"),
                item.get("source_evidence_id"),
                item.get("evidence_ids"),
                item.get("evidence_id"),
                item.get("row_ids"),
                item.get("row_id"),
            ]
        )
    refs: List[str] = []

    def _append(value: Any) -> None:
        if isinstance(value, (list, tuple, set)):
            for nested in value:
                _append(nested)
            return
        cleaned = str(value).strip()
        if cleaned and cleaned.lower() not in {"none", "null", "nan"} and cleaned not in refs:
            refs.append(cleaned)

    _append(values)
    return refs


def next_reflection_task_id(
    *,
    tasks: Sequence[Mapping[str, Any]],
    artifacts: Sequence[Mapping[str, Any]],
    target_task_id: str,
    current_count: int,
) -> str:
    target = _normalise_spaces(str(target_task_id or "")) or "global"
    prefix = f"reflection:{target}:"
    used_indexes: set[int] = set()
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)(?::report)?$")
    for task in tasks or []:
        if not isinstance(task, Mapping):
            continue
        match = pattern.match(str(task.get("task_id") or "").strip())
        if match:
            used_indexes.add(int(match.group(1)))
    for artifact in artifacts or []:
        if not isinstance(artifact, Mapping):
            continue
        for value in (artifact.get("task_id"), artifact.get("artifact_id")):
            match = pattern.match(str(value or "").strip())
            if match:
                used_indexes.add(int(match.group(1)))
    next_index = max(int(current_count or 0) + 1, 1)
    while next_index in used_indexes:
        next_index += 1
    return f"{prefix}{next_index:03d}"


@lru_cache(maxsize=1)
def _artifact_record_model() -> Any:
    from src.schema import ArtifactRecord

    return ArtifactRecord


@lru_cache(maxsize=1)
def _task_record_model() -> Any:
    from src.schema import TaskRecord

    return TaskRecord


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
    ArtifactRecord = _artifact_record_model()
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
        TaskRecord = _task_record_model()
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

    TaskRecord = _task_record_model()
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


def _calculation_task_artifact_update(
    *,
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    task_id: str,
    task_label: str,
    query: str,
    metric_family: str,
    artifact_prefix: str,
    artifact_kind: ArtifactKind,
    artifact_status: str,
    task_status: TaskStatus,
    summary: str,
    payload: Dict[str, Any],
    evidence_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    task_id = str(task_id or "calc")
    artifact_id = f"{artifact_prefix}:{task_id}:{len(artifacts or []) + 1:03d}"
    updated_artifacts = _append_artifact(
        list(artifacts or []),
        artifact_id=artifact_id,
        task_id=task_id,
        kind=artifact_kind,
        status=artifact_status,
        summary=summary,
        payload=payload,
        evidence_refs=evidence_refs,
    )
    updated_tasks = _upsert_task(
        list(tasks or []),
        task_id=task_id,
        kind=TaskKind.CALCULATION,
        label=str(task_label or task_id),
        status=task_status,
        query=query,
        metric_family=metric_family,
        artifact_id=artifact_id,
    )
    return {"tasks": updated_tasks, "artifacts": updated_artifacts, "artifact_id": artifact_id}


def operand_set_artifact_update(
    *,
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    task_id: str,
    task_label: str,
    query: str,
    metric_family: str,
    operand_rows: List[Dict[str, Any]],
    status: str,
    summary: str,
    payload: Dict[str, Any],
    evidence_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Append an operand-set artifact and attach it to the calculation task."""

    task_id = str(task_id or "calc")
    refs = (
        list(evidence_refs)
        if evidence_refs is not None
        else [
            str(row.get("evidence_id") or "")
            for row in operand_rows
            if isinstance(row, Mapping) and str(row.get("evidence_id") or "").strip()
        ]
    )
    updated = _calculation_task_artifact_update(
        tasks=tasks,
        artifacts=artifacts,
        task_id=task_id,
        task_label=task_label,
        query=query,
        metric_family=metric_family,
        artifact_prefix="operands",
        artifact_kind=ArtifactKind.OPERAND_SET,
        artifact_status=status,
        task_status=TaskStatus.IN_PROGRESS,
        summary=summary,
        payload=payload,
        evidence_refs=refs,
    )
    return {"tasks": updated["tasks"], "artifacts": updated["artifacts"]}


def calculation_plan_artifact_update(
    *,
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    task_id: str,
    task_label: str,
    query: str,
    metric_family: str,
    calculation_plan: Mapping[str, Any],
) -> Dict[str, Any]:
    """Append a calculation-plan artifact and attach it to the calculation task."""

    task_id = str(task_id or "calc")
    plan = dict(calculation_plan or {})
    updated = _calculation_task_artifact_update(
        tasks=tasks,
        artifacts=artifacts,
        task_id=task_id,
        task_label=task_label,
        query=query,
        metric_family=metric_family,
        artifact_prefix="plan",
        artifact_kind=ArtifactKind.CALCULATION_PLAN,
        artifact_status=str(plan.get("status") or "ok"),
        task_status=TaskStatus.IN_PROGRESS,
        summary=f"mode={plan.get('mode')} op={plan.get('operation')}",
        payload={"calculation_plan": plan},
    )
    return {"tasks": updated["tasks"], "artifacts": updated["artifacts"]}


def calculation_result_artifact_update(
    *,
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    task_id: str,
    task_label: str,
    query: str,
    metric_family: str,
    calculation_result: Mapping[str, Any],
    evidence_refs: Optional[List[str]],
) -> Dict[str, Any]:
    """Append a calculation-result artifact and attach it to the calculation task."""

    task_id = str(task_id or "calc")
    result = dict(calculation_result or {})
    task_status = TaskStatus.COMPLETED if str(result.get("status") or "") == "ok" else TaskStatus.FAILED
    return _calculation_task_artifact_update(
        tasks=tasks,
        artifacts=artifacts,
        task_id=task_id,
        task_label=task_label,
        query=query,
        metric_family=metric_family,
        artifact_prefix="result",
        artifact_kind=ArtifactKind.CALCULATION_RESULT,
        artifact_status=str(result.get("status") or "ok"),
        task_status=task_status,
        summary=str(result.get("rendered_value") or result.get("formatted_result") or ""),
        payload={"calculation_result": result},
        evidence_refs=evidence_refs,
    )


def synchronize_calculation_result_artifact(
    *,
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    task_id: str,
    calculation_result: Mapping[str, Any],
    evidence_refs: Sequence[str],
) -> Dict[str, Any]:
    """Replace the latest attached result artifact without changing ledger cardinality."""

    task_id = str(task_id or "").strip()
    task_record = next(
        (
            dict(task)
            for task in reversed(list(tasks or []))
            if str((task or {}).get("task_id") or "").strip() == task_id
        ),
        {},
    )
    attached_artifact_ids = [
        str(value).strip()
        for value in (task_record.get("artifact_ids") or [])
        if str(value).strip()
    ]
    result_kind = str(ArtifactKind.CALCULATION_RESULT.value)
    target_index = -1
    target_artifact_id = ""
    for artifact_id in reversed(attached_artifact_ids):
        for index in range(len(artifacts or []) - 1, -1, -1):
            artifact = (artifacts or [])[index]
            if str((artifact or {}).get("artifact_id") or "").strip() != artifact_id:
                continue
            if str((artifact or {}).get("kind") or "").strip() != result_kind:
                continue
            target_index = index
            target_artifact_id = artifact_id
            break
        if target_index >= 0:
            break
    if target_index < 0:
        return {
            "artifacts": artifacts,
            "artifact_id": "",
            "synchronized": False,
        }

    result = dict(calculation_result or {})
    updated_artifacts = [dict(item) for item in (artifacts or [])]
    target_artifact = dict(updated_artifacts[target_index])
    target_payload = dict(target_artifact.get("payload") or {})
    target_artifact.update(
        {
            "status": str(result.get("status") or target_artifact.get("status") or "ok"),
            "summary": str(
                result.get("rendered_value")
                or result.get("formatted_result")
                or target_artifact.get("summary")
                or ""
            ),
            "payload": {
                **target_payload,
                "calculation_result": result,
            },
            "evidence_refs": list(
                dict.fromkeys(
                    str(value).strip()
                    for value in (evidence_refs or [])
                    if str(value).strip()
                )
            ),
        }
    )
    updated_artifacts[target_index] = target_artifact
    return {
        "artifacts": updated_artifacts,
        "artifact_id": target_artifact_id,
        "synchronized": True,
    }


def semantic_plan_artifact_update(
    *,
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    artifact_task_id: str,
    semantic_plan: Mapping[str, Any],
    retrieval_queries: List[str],
    summary: str,
    payload_extra: Optional[Dict[str, Any]] = None,
    calculation_tasks: Optional[List[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Append a semantic-plan artifact and attach pending calculation tasks."""

    artifact_id = f"semantic_plan:{len(artifacts or []) + 1:03d}"
    payload = {
        "semantic_plan": dict(semantic_plan or {}),
        "retrieval_queries": list(retrieval_queries or []),
    }
    payload.update(dict(payload_extra or {}))
    updated_artifacts = _append_artifact(
        list(artifacts or []),
        artifact_id=artifact_id,
        task_id=str(artifact_task_id or "semantic_plan"),
        kind=ArtifactKind.SEMANTIC_PLAN,
        status=str((semantic_plan or {}).get("status") or "ok"),
        summary=summary,
        payload=payload,
    )
    updated_tasks = list(tasks or [])
    for task in calculation_tasks or []:
        task_row = dict(task or {})
        task_id = str(task_row.get("task_id") or "")
        if not task_id:
            continue
        updated_tasks = _upsert_task(
            updated_tasks,
            task_id=task_id,
            kind=TaskKind.CALCULATION,
            label=str(task_row.get("metric_label") or task_row.get("metric_family") or "calculation"),
            status=TaskStatus.PENDING,
            query=str(task_row.get("query") or ""),
            metric_family=str(task_row.get("metric_family") or ""),
            constraints=dict(task_row.get("constraints") or {}),
            artifact_id=artifact_id,
        )
    return {"tasks": updated_tasks, "artifacts": updated_artifacts, "artifact_id": artifact_id}


def reconciliation_result_artifact_update(
    *,
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    active_subtask: Mapping[str, Any],
    reconciliation_result: Mapping[str, Any],
    summary: str,
    evidence_refs: Optional[List[str]],
) -> Dict[str, Any]:
    """Append a reconciliation-result artifact and attach the reconciliation task."""

    task = dict(active_subtask or {})
    result = dict(reconciliation_result or {})
    status = str(result.get("status") or "ready")
    task_id = str(task.get("task_id") or "reconcile")
    artifact_id = f"reconcile:{task_id}:{len(artifacts or []) + 1:03d}"
    updated_artifacts = _append_artifact(
        list(artifacts or []),
        artifact_id=artifact_id,
        task_id=task_id,
        kind=ArtifactKind.RECONCILIATION_RESULT,
        status=status,
        summary=summary,
        payload={"reconciliation_result": result},
        evidence_refs=evidence_refs,
    )
    updated_tasks = _upsert_task(
        list(tasks or []),
        task_id=task_id,
        kind=TaskKind.RECONCILIATION,
        label=f"reconcile {task.get('metric_label') or task.get('metric_family') or task_id}",
        status=TaskStatus.COMPLETED if status == "ready" else TaskStatus.PARTIAL,
        query=str(task.get("query") or ""),
        metric_family=str(task.get("metric_family") or ""),
        constraints=dict(task.get("constraints") or {}),
        artifact_id=artifact_id,
    )
    return {"tasks": updated_tasks, "artifacts": updated_artifacts, "artifact_id": artifact_id}


def supersede_task_with_aggregate_result(
    *,
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    task: Mapping[str, Any],
    aggregate_artifact_id: str,
    replacement_summary: str = "",
    replacement_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Mark a task as superseded by the aggregate answer, optionally adding a replacement artifact."""

    task_row = dict(task or {})
    task_id = str(task_row.get("task_id") or "").strip()
    updated_artifacts = list(artifacts or [])
    supersession_artifact_id: Optional[str] = None
    summary = str(replacement_summary or "")
    payload = dict(replacement_payload or {})
    if task_id and summary and payload:
        base_artifact_id = f"supersession:{task_id}"
        supersession_artifact_id = f"{base_artifact_id}:{len(updated_artifacts) + 1:03d}"
        existing_artifact_ids = {
            str(item.get("artifact_id") or "").strip()
            for item in updated_artifacts
            if isinstance(item, Mapping)
        }
        suffix = len(updated_artifacts) + 1
        while supersession_artifact_id in existing_artifact_ids:
            suffix += 1
            supersession_artifact_id = f"{base_artifact_id}:{suffix:03d}"
        updated_artifacts = _append_artifact(
            updated_artifacts,
            artifact_id=supersession_artifact_id,
            task_id=task_id,
            kind=ArtifactKind.CALCULATION_RESULT,
            status="superseded_by_aggregate_result",
            summary=summary[:200],
            payload=payload,
        )

    try:
        task_kind = TaskKind(str(task_row.get("kind") or TaskKind.CALCULATION.value))
    except ValueError:
        task_kind = TaskKind.CALCULATION
    constraints = dict(task_row.get("constraints") or {})
    constraints.update(
        {
            "resolution_status": "superseded_by_aggregate_result",
            "superseded_by_task_id": "aggregate",
            "superseded_by_artifact_id": aggregate_artifact_id,
        }
    )
    notes = list(dict.fromkeys([*(task_row.get("notes") or []), "superseded_by_aggregate_result"]))
    updated_tasks = _upsert_task(
        list(tasks or []),
        task_id=task_id,
        kind=task_kind,
        label=str(task_row.get("label") or task_id),
        status=TaskStatus.SUPERSEDED,
        query=str(task_row.get("query") or ""),
        metric_family=str(task_row.get("metric_family") or ""),
        constraints=constraints,
        artifact_id=supersession_artifact_id,
        notes=notes,
    )
    return {
        "tasks": updated_tasks,
        "artifacts": updated_artifacts,
        "artifact_id": supersession_artifact_id or "",
    }


def aggregate_answer_artifact_update(
    *,
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    final_answer: str,
    payload: Dict[str, Any],
    evidence_refs: Optional[List[str]],
    planner_feedback: str,
    query: str,
) -> Dict[str, Any]:
    """Append the aggregate-answer artifact and attach the synthesis task."""

    artifact_id = f"aggregate:{len(artifacts or []) + 1:03d}"
    updated_artifacts = _append_artifact(
        list(artifacts or []),
        artifact_id=artifact_id,
        task_id="aggregate",
        kind=ArtifactKind.AGGREGATED_ANSWER,
        status="ok",
        summary=str(final_answer or "")[:200],
        payload=payload,
        evidence_refs=evidence_refs,
    )
    task_status = TaskStatus.PARTIAL if str(planner_feedback or "").strip() else TaskStatus.COMPLETED
    updated_tasks = _upsert_task(
        list(tasks or []),
        task_id="aggregate",
        kind=TaskKind.SYNTHESIS,
        label="Aggregate subtask results",
        status=task_status,
        query=query,
        metric_family="aggregate",
        artifact_id=artifact_id,
    )
    return {"tasks": updated_tasks, "artifacts": updated_artifacts, "artifact_id": artifact_id}


def reflection_report_artifact_update(
    *,
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    reflection_task_id: str,
    target_task_id: str,
    query: str,
    metric_family: str,
    reflection_report: Mapping[str, Any],
    reflection_action: Mapping[str, Any],
    reflection_request: Mapping[str, Any],
    reflection_plan: Mapping[str, Any],
    retry_strategy: str,
) -> Dict[str, Any]:
    """Append the reflection-report artifact and attach the reflection task."""

    reflection_task_id = str(reflection_task_id or "reflection")
    report = dict(reflection_report or {})
    action = dict(reflection_action or {})
    artifact_id = f"{reflection_task_id}:report"
    updated_artifacts = _append_artifact(
        list(artifacts or []),
        artifact_id=artifact_id,
        task_id=reflection_task_id,
        kind=ArtifactKind.REFLECTION_REPORT,
        status=str(report.get("outcome") or "retry_prepared"),
        summary=f"reflection={report.get('action_taken') or retry_strategy}",
        payload={
            "reflection_report": report,
            "reflection_action": action,
            "reflection_request": dict(reflection_request or {}),
            "reflection_plan": dict(reflection_plan or {}),
        },
        evidence_refs=[],
    )
    updated_tasks = _upsert_task(
        list(tasks or []),
        task_id=reflection_task_id,
        kind=TaskKind.REFLECTION,
        label=f"reflect {target_task_id or 'global'}",
        status=TaskStatus.COMPLETED,
        query=query,
        metric_family=metric_family,
        constraints={
            "target_task_ids": list(report.get("target_task_ids") or []),
            "target_artifact_ids": list(report.get("target_artifact_ids") or []),
            "action_taken": str(report.get("action_taken") or ""),
        },
        artifact_id=artifact_id,
    )
    return {"tasks": updated_tasks, "artifacts": updated_artifacts, "artifact_id": artifact_id}


def _normalise_ledger_records(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, dict):
        raw_items = list(value.values())
    elif isinstance(value, list):
        raw_items = list(value)
    else:
        raw_items = []
    return [dict(item) for item in raw_items if isinstance(item, dict)]


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


def _ledger_id_counts(records: Sequence[Mapping[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for record in records:
        record_id = str(record.get(key) or "").strip()
        if record_id:
            counts[record_id] = counts.get(record_id, 0) + 1
    return counts


def _record_ids(records: Sequence[Mapping[str, Any]], key: str) -> set[str]:
    return {
        str(record.get(key) or "").strip()
        for record in records
        if str(record.get(key) or "").strip()
    }


def _project_task_trace_views(
    task_records: Sequence[Mapping[str, Any]],
    artifact_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[List[Dict[str, Any]], set[str]]:
    referenced_artifact_ids: set[str] = set()
    task_views: List[Dict[str, Any]] = []
    for task in task_records:
        artifact_ids = [
            str(value).strip()
            for value in (task.get("artifact_ids") or [])
            if str(value).strip()
        ]
        constraints = task.get("constraints") if isinstance(task.get("constraints"), dict) else {}
        notes = [
            str(value).strip()
            for value in (task.get("notes") or [])
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
                "resolution_status": str(constraints.get("resolution_status") or "").strip(),
                "superseded_by_task_id": str(constraints.get("superseded_by_task_id") or "").strip(),
                "superseded_by_artifact_id": str(constraints.get("superseded_by_artifact_id") or "").strip(),
                "notes": notes,
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
    return task_views, referenced_artifact_ids


def _project_artifact_trace_views(artifact_records: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
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
    return artifact_views


def _append_duplicate_id_issues(
    integrity_issues: List[Dict[str, Any]],
    *,
    task_id_counts: Mapping[str, int],
    artifact_id_counts: Mapping[str, int],
) -> None:
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


def _task_requires_evidence_ref(task_kind: str, attached_artifacts: Sequence[Mapping[str, Any]]) -> bool:
    requires_evidence_ref = task_kind == TaskKind.CALCULATION.value
    if task_kind == TaskKind.RECONCILIATION.value:
        requires_evidence_ref = reconciliation_result_status(attached_artifacts) in {"ok", "ready"}
    elif task_kind == TaskKind.REFLECTION.value:
        requires_evidence_ref = False
    elif task_kind == TaskKind.RETRIEVAL.value:
        requires_evidence_ref = True
    elif task_kind == TaskKind.SYNTHESIS.value:
        requires_evidence_ref = True
    elif task_kind == TaskKind.CRITIC.value:
        requires_evidence_ref = True
    return requires_evidence_ref


def _append_required_artifact_issues(
    integrity_issues: List[Dict[str, Any]],
    *,
    task: Mapping[str, Any],
    attached_artifacts: Sequence[Mapping[str, Any]],
    task_ids: set[str],
    artifact_ids: set[str],
) -> None:
    required_kinds = sorted(
        REQUIRED_ARTIFACT_KINDS_BY_TASK_KIND.get(str(task.get("kind") or "").strip(), set())
    )
    if not required_kinds:
        return
    task_kind = str(task.get("kind") or "").strip()
    latest_required_artifact_by_kind: Dict[str, Mapping[str, Any]] = {}
    for artifact in attached_artifacts:
        artifact_kind = str(artifact.get("kind") or "").strip()
        if artifact_kind in required_kinds:
            latest_required_artifact_by_kind[artifact_kind] = artifact
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
    for artifact in latest_required_artifact_by_kind.values():
        artifact_kind = str(artifact.get("kind") or "").strip()
        payload = artifact.get("payload") if isinstance(artifact.get("payload"), Mapping) else {}
        missing_payload_key = payload_missing_contract(artifact_kind, payload)
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
            acceptance_state = critic_report_acceptance_state(dict(report))
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


def _append_task_integrity_issues(
    integrity_issues: List[Dict[str, Any]],
    *,
    task_views: Sequence[Mapping[str, Any]],
    artifact_by_id: Mapping[str, Mapping[str, Any]],
    task_ids: set[str],
    artifact_ids: set[str],
    final_source_task_ids: set[str],
) -> None:
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
        if status != "completed":
            continue
        task_kind = str(task.get("kind") or "").strip()
        attached_artifacts = [
            artifact_by_id[artifact_id]
            for artifact_id in (task.get("artifact_ids") or [])
            if artifact_id in artifact_by_id
        ]
        _append_required_artifact_issues(
            integrity_issues,
            task=task,
            attached_artifacts=attached_artifacts,
            task_ids=task_ids,
            artifact_ids=artifact_ids,
        )
        has_evidence_ref = any(
            str(value).strip()
            for artifact in attached_artifacts
            for value in (artifact.get("evidence_refs") or [])
        )
        has_payload_provenance = any(
            payload_has_provenance(artifact.get("payload") or {})
            for artifact in attached_artifacts
        )
        if _task_requires_evidence_ref(task_kind, attached_artifacts) and not has_evidence_ref and not has_payload_provenance:
            integrity_issues.append(
                {
                    "type": "missing_required_evidence_ref",
                    "severity": "error",
                    "task_id": task.get("task_id") or "",
                    "task_kind": task_kind,
                }
            )


def project_task_artifact_trace(
    tasks: Any,
    artifacts: Any,
) -> Dict[str, Any]:
    """Return a compact caller-facing projection of the task/artifact ledger."""

    task_records = _normalise_ledger_records(tasks)
    artifact_records = _normalise_ledger_records(artifacts)
    task_id_counts = _ledger_id_counts(task_records, "task_id")
    artifact_id_counts = _ledger_id_counts(artifact_records, "artifact_id")
    artifact_by_id = {
        str(item.get("artifact_id") or "").strip(): item
        for item in artifact_records
        if str(item.get("artifact_id") or "").strip()
    }
    task_views, referenced_artifact_ids = _project_task_trace_views(task_records, artifact_by_id)
    artifact_views = _project_artifact_trace_views(artifact_records)

    artifact_ids = _record_ids(artifact_records, "artifact_id")
    task_ids = _record_ids(task_records, "task_id")
    missing_artifact_ids = sorted(
        artifact_id for artifact_id in referenced_artifact_ids if artifact_id not in artifact_ids
    )
    orphan_artifact_ids = sorted(
        artifact_id
        for artifact_id, artifact in artifact_by_id.items()
        if str(artifact.get("task_id") or "").strip() not in task_ids
    )
    integrity_issues: List[Dict[str, Any]] = []

    _append_duplicate_id_issues(
        integrity_issues,
        task_id_counts=task_id_counts,
        artifact_id_counts=artifact_id_counts,
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
    _append_task_integrity_issues(
        integrity_issues,
        task_views=task_views,
        artifact_by_id=artifact_by_id,
        task_ids=task_ids,
        artifact_ids=artifact_ids,
        final_source_task_ids=final_source_task_ids,
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
