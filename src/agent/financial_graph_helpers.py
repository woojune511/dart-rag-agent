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
import json
import math
import re
from typing import Any, Dict, List, Optional

from src.config import get_financial_ontology
from src.agent.financial_graph_models import validate_answer_slots_payload
from src.schema import ArtifactKind, ArtifactRecord, TaskKind, TaskRecord, TaskStatus

__all__ = [
    '_tokenize_terms',
    '_normalise_spaces',
    '_split_sentences',
    '_strip_anchor_text',
    '_section_hint_alias',
    '_append_artifact',
    '_upsert_task',
    '_extract_artifact_payload_value',
    '_find_task_record_in_list',
    '_latest_artifact_value_for_task_records',
    '_project_task_trace_from_runtime',
    '_project_task_trace_from_state',
    '_build_aggregate_calculation_projection',
    '_resolve_runtime_calculation_trace',
    '_runtime_trace_state_update',
    '_parse_number_text',
    '_safe_eval_formula',
    '_extract_composite_krw',
    '_normalise_operand_value',
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
    '_requires_direct_numeric_grounding',
    '_extract_year_tokens',
    '_build_generic_metric_aliases',
    '_infer_statement_and_section_hints',
    '_build_generic_required_operands',
    '_infer_generic_metric_label',
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

# ---------------------------------------------------------------------------
# Text and ledger utilities
# ---------------------------------------------------------------------------

def _tokenize_terms(text: str) -> set[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", text or "")
    return {token.lower() for token in tokens if len(token) >= 2}


def _normalise_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


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
        active_trace = _resolve_runtime_calculation_trace(state)
        if not calculation_operands:
            calculation_operands = [
                dict(item)
                for item in (
                    active_trace.get("calculation_operands")
                    or state.get("calculation_operands")
                    or []
                )
            ]
        if not calculation_plan:
            calculation_plan = dict(
                active_trace.get("calculation_plan")
                or state.get("calculation_plan")
                or {}
            )
        if not calculation_result:
            calculation_result = dict(
                active_trace.get("calculation_result")
                or state.get("calculation_result")
                or {}
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
    subtask_plans: List[Dict[str, Any]] = []
    subtask_result_views: List[Dict[str, Any]] = []

    for row in list(subtask_results or []):
        task_id = str(row.get("task_id") or "").strip()
        metric_family = str(row.get("metric_family") or "").strip()
        metric_label = str(row.get("metric_label") or "").strip()

        for operand in list(row.get("calculation_operands") or []):
            operand_row = dict(operand)
            operand_row.setdefault("task_id", task_id)
            operand_row.setdefault("metric_family", metric_family)
            operand_row.setdefault("metric_label", metric_label)
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

        subtask_result_views.append(
            {
                "task_id": task_id,
                "metric_family": metric_family,
                "metric_label": metric_label,
                "answer": str(row.get("answer") or "").strip(),
                "status": str(row.get("status") or ""),
                "calculation_result": dict(row.get("calculation_result") or {}),
            }
        )

    all_ok = all(str(item.get("status") or "") == "ok" for item in subtask_result_views) if subtask_result_views else False
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
            "subtask_results": subtask_result_views,
            "answer_slots": validate_answer_slots_payload(
                {
                    "operation_family": "aggregate_subtasks",
                    "subtask_results": [
                        {
                            "task_id": str(item.get("task_id") or ""),
                            "metric_family": str(item.get("metric_family") or ""),
                            "metric_label": str(item.get("metric_label") or ""),
                            "answer": str(item.get("answer") or ""),
                            "answer_slots": dict((item.get("calculation_result") or {}).get("answer_slots") or {}),
                            "rendered_value": str((item.get("calculation_result") or {}).get("rendered_value") or ""),
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
            },
        },
    }


def _normalise_resolved_calculation_trace(result: Dict[str, Any]) -> Dict[str, Any]:
    resolved = dict(result.get("resolved_calculation_trace") or {})
    structured_result = dict(result.get("structured_result") or {})

    operands = list(resolved.get("calculation_operands") or [])
    plan = dict(resolved.get("calculation_plan") or {})
    calc_result = dict(resolved.get("calculation_result") or {})
    if structured_result and not calc_result:
        calc_result = structured_result

    if operands or plan or calc_result:
        return {
            "calculation_operands": operands,
            "calculation_plan": plan,
            "calculation_result": calc_result,
        }
    return {}


def _resolve_runtime_calculation_trace(result: Dict[str, Any]) -> Dict[str, Any]:
    normalised = _normalise_resolved_calculation_trace(result)
    top_level = {
        "calculation_operands": list(result.get("calculation_operands") or []),
        "calculation_plan": dict(result.get("calculation_plan") or {}),
        "calculation_result": dict(result.get("calculation_result") or {}),
    }
    structured_result = dict(result.get("structured_result") or {})
    if structured_result and not top_level["calculation_result"]:
        top_level["calculation_result"] = structured_result
    subtask_results = [dict(item) for item in (result.get("subtask_results") or [])]
    if normalised:
        plan = dict(normalised.get("calculation_plan") or {})
        calc_result = dict(normalised.get("calculation_result") or {})
        answer_slots = dict(calc_result.get("answer_slots") or {})
        if (
            str(plan.get("mode") or "") == "aggregate_subtasks"
            or bool(calc_result.get("subtask_results"))
            or str(answer_slots.get("operation_family") or "").strip().lower() == "aggregate_subtasks"
        ):
            return normalised

    active_task_id = str((result.get("active_subtask") or {}).get("task_id") or "").strip()
    if not active_task_id:
        calc_task_ids = [
            str(task.get("task_id") or "").strip()
            for task in (result.get("tasks") or [])
            if str(task.get("task_id") or "").strip()
            and str(task.get("kind") or "") == "calculation"
        ]
        if len(calc_task_ids) == 1:
            active_task_id = calc_task_ids[0]

    if active_task_id:
        projected = _project_task_trace_from_runtime(result, active_task_id)
        if (
            projected["calculation_operands"]
            or projected["calculation_plan"]
            or projected["calculation_result"]
        ):
            return projected

    if subtask_results:
        final_answer = str(result.get("answer") or result.get("compressed_answer") or "").strip()
        return _build_aggregate_calculation_projection(subtask_results, final_answer)

    if normalised:
        return normalised

    return top_level


def _resolve_runtime_structured_result(result: Dict[str, Any]) -> Dict[str, Any]:
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
) -> Dict[str, Any]:
    current_trace = _resolve_runtime_calculation_trace(state)
    resolved_trace = {
        "calculation_operands": [
            dict(item)
            for item in (
                calculation_operands
                if calculation_operands is not None
                else list(current_trace.get("calculation_operands") or [])
            )
        ],
        "calculation_plan": dict(
            calculation_plan
            if calculation_plan is not None
            else dict(current_trace.get("calculation_plan") or {})
        ),
        "calculation_result": dict(
            calculation_result
            if calculation_result is not None
            else dict(current_trace.get("calculation_result") or {})
        ),
    }
    if calculation_result is not None:
        structured_result = dict(calculation_result)
    else:
        structured_result = _resolve_runtime_structured_result(
            {
                "structured_result": state.get("structured_result", {}),
                "resolved_calculation_trace": resolved_trace,
            }
        )
    return {
        "resolved_calculation_trace": resolved_trace,
        "structured_result": structured_result,
        # Internal compatibility mirror while graph-state callers migrate.
        "calculation_operands": list(resolved_trace["calculation_operands"]),
        "calculation_plan": dict(resolved_trace["calculation_plan"]),
        "calculation_result": dict(resolved_trace["calculation_result"]),
    }


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

    value = _parse_number_text(raw_value)
    if value is None and unit in {"%", "퍼센트"}:
        value = _parse_number_text(str(raw_value or "").replace("%", "").replace("퍼센트", ""))
    if value is None:
        return None, "UNKNOWN"

    krw_scale = {
        "원": 1.0,
        "천원": 1_000.0,
        "백만원": 1_000_000.0,
        "억원": 100_000_000.0,
        "조원": 1_0000_0000_0000.0,
    }
    usd_scale = {
        "usd": 1.0,
        "$": 1.0,
        "달러": 1.0,
        "백만달러": 1_000_000.0,
    }
    count_units = {"개", "명", "곳", "사"}
    percent_units = {"%", "퍼센트"}

    if unit in krw_scale:
        return value * krw_scale[unit], "KRW"
    if unit in usd_scale:
        return value * usd_scale[unit], "USD"
    if unit in count_units:
        return value, "COUNT"
    if unit in percent_units:
        return value, "PERCENT"
    return value, "UNKNOWN"


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
    # 1억 이상이면 억 단위에서 반올림, 미만이면 원 단위 그대로
    if abs(value) >= 100_000_000:
        amount = int(round(abs(value) / 100_000_000)) * 100_000_000
    else:
        amount = int(round(abs(value)))
    negative = value < 0
    jo = amount // 1_0000_0000_0000
    amount %= 1_0000_0000_0000
    eok = amount // 100_000_000
    amount %= 100_000_000
    man = amount // 10_000

    parts: List[str] = []
    if jo:
        parts.append(f"{jo}조")
    if eok:
        parts.append(f"{eok:,}억원")
    elif jo:
        parts.append("0억원")
    elif man:
        parts.append(f"{man:,}만원")
    else:
        parts.append(f"{int(round(abs(value))):,}원")

    rendered = " ".join(parts)
    return f"-{rendered}" if negative else rendered


def _display_operand_label(label: str) -> str:
    text = _normalise_spaces(label)
    text = re.sub(r"^\d{4}년\s*", "", text)
    text = re.sub(r"^삼성전자\s*", "", text)
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
    known_terms = [
        "영업이익",
        "매출",
        "연구개발비",
        "연구개발",
        "당기순이익",
        "순이익",
        "설비투자",
        "투자",
        "비용",
        "수익",
    ]
    return {term for term in known_terms if term in text}


def _is_ratio_percent_query(text: str) -> bool:
    normalized = _normalise_spaces(text)
    return any(keyword in normalized for keyword in ("비율", "비중", "%", "%p", "이익률", "차지"))


def _desired_statement_types(query: str, topic: str) -> List[str]:
    text = _normalise_spaces(f"{query} {topic}")
    desired: List[str] = []
    if "재무상태표" in text:
        desired.extend(["balance_sheet", "summary_financials"])
    if "손익계산서" in text or "포괄손익계산서" in text:
        desired.extend(["income_statement", "summary_financials", "segment_note"])
    if "현금흐름표" in text:
        desired.extend(["cash_flow", "summary_financials"])
    if "주석" in text:
        desired.extend(["notes"])
    if any(keyword in text for keyword in ("부채비율", "유동비율", "자산총계", "부채총계", "자본총계", "유동자산", "유동부채")):
        desired.extend(["balance_sheet", "summary_financials"])
    if any(keyword in text for keyword in ("영업이익", "당기순이익", "순이익", "매출액", "매출원가", "판매비와관리비", "이익률", "ROE", "ROA")):
        desired.extend(["income_statement", "summary_financials", "segment_note"])
    if any(keyword in text for keyword in ("영업활동현금흐름", "투자활동현금흐름", "재무활동현금흐름", "FCF", "현금흐름")):
        desired.extend(["cash_flow", "summary_financials"])
    return list(dict.fromkeys(desired))


def _desired_consolidation_scope(query: str, report_scope: Dict[str, Any]) -> str:
    text = _normalise_spaces(query)
    if "연결" in text:
        return "consolidated"
    if "별도" in text:
        return "separate"
    scope_value = str((report_scope or {}).get("consolidation") or "").strip()
    if scope_value == "연결":
        return "consolidated"
    if scope_value == "별도":
        return "separate"
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
    scope_rcept_no = str((report_scope or {}).get("rcept_no") or "").strip()
    if scope_rcept_no:
        return False
    return True


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
_GENERIC_NUMERIC_OPERAND_PATTERNS: List[re.Pattern[str]] = [
    re.compile(pattern)
    for pattern in [
        r"시설투자(?:\((?:CAPEX|CapEx)\))?",
        r"\bCAPEX\b",
        r"\bCapEx\b",
        r"자본적\s*지출",
        r"법인세비용차감전순(?:이익|손익)",
        r"외화환산(?:이익|손실)",
        r"순이자마진",
        r"\bNIM\b",
        r"무형자산상각비",
        r"세액공제",
        r"\bAMPC\b",
        r"매출원가",
        r"판매비와관리비",
        r"매출액",
        r"유형자산",
        r"무형자산",
        r"단기차입금",
        r"장기차입금",
        r"사채",
        r"(?:차량|금융)\s*부문\s*영업이익",
        r"전체\s*(?:연결\s*)?영업이익",
        r"연결\s*영업이익",
        r"영업손실",
        r"영업이익",
        r"유동자산",
        r"유동부채",
        r"부채총계",
        r"자본총계",
    ]
]


def _clean_metric_label(label: str) -> str:
    text = _normalise_spaces(str(label or ""))
    text = re.sub(r"^[0-9]{4}년\s*", "", text)
    text = re.sub(r"(?:금액|수치|총액|규모|비중|비율|증감액|증감폭|순효과)\s*$", "", text).strip()
    return text


def _extract_quoted_metric_labels(query: str) -> List[str]:
    labels: List[str] = []
    for match in _QUOTED_METRIC_RE.finditer(str(query or "")):
        cleaned = _clean_metric_label(match.group("label"))
        if cleaned:
            labels.append(cleaned)
    return list(dict.fromkeys(labels))


def _extract_generic_operand_labels(query: str) -> List[str]:
    text = str(query or "")
    labels: List[str] = []

    if "유·무형자산" in text or "유/무형자산" in text:
        labels.extend(["유형자산", "무형자산"])

    labels.extend(_extract_quoted_metric_labels(text))

    for pattern in _GENERIC_NUMERIC_OPERAND_PATTERNS:
        for match in pattern.finditer(text):
            cleaned = _clean_metric_label(match.group(0))
            if cleaned:
                labels.append(cleaned)

    normalized = list(dict.fromkeys(label for label in labels if label))
    if any("시설투자" in item for item in normalized):
        normalized = [item for item in normalized if item not in {"CAPEX", "CapEx"}]
    if "영업이익" in normalized and any("부문 영업이익" in item for item in normalized):
        normalized = [item for item in normalized if item != "영업이익"]
    derived_labels = {"총 영업비용", "영업비용률", "순효과"}
    normalized = [item for item in normalized if item not in derived_labels]
    return normalized


def _label_implies_percent_metric(label: str) -> bool:
    normalized = _normalise_spaces(str(label or ""))
    if not normalized:
        return False
    return any(
        token in normalized
        for token in ("비율", "비중", "마진", "이익률", "수익률", "%", "%p")
    )


def _is_single_metric_period_comparison(query: str, operand_labels: List[str]) -> bool:
    text = _normalise_spaces(query)
    comparison_markers = ("전년 대비", "전기 대비", "증감액", "증감폭", "%p", "추이")
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
    return years


def _build_generic_metric_aliases(label: str) -> List[str]:
    base = str(label or "").strip()
    if not base:
        return []
    aliases = [base]
    if "순이익" in base:
        aliases.append(base.replace("순이익", "순손익"))
    if "순손익" in base:
        aliases.append(base.replace("순손익", "순이익"))
    if "손익" in base:
        aliases.append(base.replace("손익", "이익"))
    if "이익" in base and "손익" not in base:
        aliases.append(base.replace("이익", "손익"))
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
    statement_types = _desired_statement_types(query, query)
    preferred_sections: List[str] = []
    if "손익계산서" in text or "포괄손익계산서" in text:
        preferred_sections.extend(["연결 손익계산서", "손익계산서", "포괄손익계산서"])
    if "재무상태표" in text:
        preferred_sections.extend(["연결 재무상태표", "재무상태표"])
    if "현금흐름표" in text:
        preferred_sections.extend(["현금흐름표", "현금흐름표 (연결)"])
    if "주석" in text:
        preferred_sections.extend(["연결재무제표 주석", "재무제표 주석"])
        if "notes" not in statement_types:
            statement_types.append("notes")
    if any(keyword in text for keyword in ("부문", "segment", "세그먼트")):
        preferred_sections.extend(["부문정보", "영업부문", "영업실적"])
        if "segment_note" not in statement_types:
            statement_types.append("segment_note")
    if any(keyword in text for keyword in ("법인세비용차감전순이익", "법인세비용차감전순손익")):
        preferred_sections.extend(["법인세비용", "연결 손익계산서", "포괄손익계산서"])
        if "notes" not in statement_types:
            statement_types.append("notes")
        if "summary_financials" not in statement_types:
            statement_types.append("summary_financials")
    if any(keyword in text for keyword in ("외화환산이익", "외화환산손실", "환율 변동", "외화환산")):
        preferred_sections.extend(["현금흐름표 (연결)", "현금흐름표", "금융손익 (연결)", "외화환산"])
        if "cash_flow" not in statement_types:
            statement_types.append("cash_flow")
        if "notes" not in statement_types:
            statement_types.append("notes")
    if any(keyword in text for keyword in ("단기차입금", "장기차입금", "유동성장기차입금", "차입금", "사채")):
        preferred_sections.extend(["차입금 및 사채", "단기차입금", "장기차입금", "사채", "연결재무제표 주석"])
        if "notes" not in statement_types:
            statement_types.append("notes")
    if any(keyword in text for keyword in ("시설투자", "capex", "자본적 지출")):
        preferred_sections.extend(["원재료 및 생산설비", "시설투자", "사업의 내용"])
    return list(dict.fromkeys(statement_types)), list(dict.fromkeys(preferred_sections))


def _build_generic_required_operands(
    query: str,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    ontology = get_financial_ontology()
    operand_labels = _extract_generic_operand_labels(query)
    if _is_single_metric_period_comparison(query, operand_labels):
        base_label = operand_labels[0] if operand_labels else _infer_generic_metric_label(query, "")
        aliases = _build_generic_metric_aliases(base_label)
        unit_family = "PERCENT" if _label_implies_percent_metric(base_label) else ""
        concept_spec = _infer_generic_concept_spec(base_label, ontology)
        year_tokens = _extract_year_tokens(query, report_scope)
        if year_tokens:
            current_year = year_tokens[0]
            prior_year = year_tokens[1] if len(year_tokens) > 1 else current_year - 1
            return [
                _augment_generic_operand_with_concept(
                    {
                        "label": f"{current_year}년 {base_label}",
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
                        "label": f"{prior_year}년 {base_label}",
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
                    "label": f"당기 {base_label}",
                    "aliases": aliases,
                    "role": "current_period",
                    "required": True,
                    "period_hint": "당기",
                    "unit_family": unit_family,
                },
                concept_spec=concept_spec,
            ),
            _augment_generic_operand_with_concept(
                {
                    "label": f"전기 {base_label}",
                    "aliases": aliases,
                    "role": "prior_period",
                    "required": True,
                    "period_hint": "전기",
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
                    "unit_family": "PERCENT" if _label_implies_percent_metric(label) else "",
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
    return _clean_metric_label(topic) or "수치 계산"


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
        return _normalise_spaces(re.sub(r"^(20\d{2}년|당기|전기|전년)\s+", "", _normalise_spaces(text or "")))

    queries = [query]
    year = str(report_scope.get("year") or "").strip()
    year_prefix = f"{year}년 " if year else ""
    fallback_period_focus = str((constraints or {}).get("period_focus") or "unknown").strip()

    def _year_for_operand(operand: Dict[str, Any]) -> str:
        if not year.isdigit():
            return year
        role = str(operand.get("role") or "").strip()
        period_hint = str(operand.get("period_hint") or "").strip()
        if role == "prior_period" or period_hint in {"전기", "전년", "직전 연도", "이전 연도"}:
            return str(int(year) - 1)
        if role == "current_period":
            return year
        if fallback_period_focus == "prior":
            return str(int(year) - 1)
        return year

    def _prefix_for_operand(operand: Dict[str, Any]) -> str:
        operand_year = _year_for_operand(operand)
        pieces: List[str] = []
        if operand_year:
            pieces.append(f"{operand_year}년")
        period_hint = str(operand.get("period_hint") or "").strip()
        role = str(operand.get("role") or "").strip()
        if not period_hint:
            if role == "current_period":
                period_hint = "당기"
            elif role == "prior_period":
                period_hint = "전기"
        normalized_period_hint = _normalise_spaces(period_hint)
        if operand_year and normalized_period_hint in {operand_year, f"{operand_year}년"}:
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
        if (
            {left_role, right_role} == {"current_period", "prior_period"}
            and left_concept
            and left_concept == right_concept
        ):
            left_year = _year_for_operand(left)
            right_year = _year_for_operand(right)
            shared_label = _strip_leading_period_prefix(
                str(left.get("aliases") or [left.get("label") or ""])[0]
            ) or _strip_leading_period_prefix(str(left.get("label") or ""))
            if shared_label:
                compact_bits = [bit for bit in (f"{left_year}년" if left_year else "", f"{right_year}년" if right_year else "", shared_label) if bit]
                queries.append(_collapse_duplicate_query_tokens(" ".join(compact_bits)))
                for section in preferred_sections[:2]:
                    queries.append(_collapse_duplicate_query_tokens(f"{' '.join(compact_bits)} {section}"))
                for alias in list(left.get("aliases") or [])[:2]:
                    alias_text = _strip_leading_period_prefix(str(alias).strip())
                    if alias_text and alias_text != shared_label:
                        alias_bits = [bit for bit in (f"{left_year}년" if left_year else "", f"{right_year}년" if right_year else "", alias_text) if bit]
                        queries.append(_collapse_duplicate_query_tokens(" ".join(alias_bits)))
                        for section in preferred_sections[:2]:
                            queries.append(_collapse_duplicate_query_tokens(f"{' '.join(alias_bits)} {section}"))

    if metric_label:
        queries.append(_collapse_duplicate_query_tokens(f"{year_prefix}{metric_label}"))
        for section in preferred_sections[:4]:
            queries.append(_collapse_duplicate_query_tokens(f"{year_prefix}{metric_label} {section}"))
    for operand in operand_specs:
        label = str(operand.get("label") or "").strip()
        if not label:
            continue
        operand_prefix = _prefix_for_operand(operand) or year_prefix.strip()
        normalized_label = _strip_leading_period_prefix(label)
        queries.append(_collapse_duplicate_query_tokens(f"{operand_prefix} {normalized_label or label}"))
        for alias in list(operand.get("aliases") or [])[:3]:
            if str(alias).strip():
                normalized_alias = _strip_leading_period_prefix(str(alias).strip())
                queries.append(_collapse_duplicate_query_tokens(f"{operand_prefix} {normalized_alias or alias}"))
                for section in preferred_sections[:2]:
                    queries.append(_collapse_duplicate_query_tokens(f"{operand_prefix} {normalized_alias or alias} {section}"))
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
    if any(token in text for token in ("증감률", "증가율", "감소율", "성장률", "변화율")):
        return "growth_rate"
    if any(token in text for token in ("차이", "얼마나 더", "보다 얼마나", "더 큰가", "더 높은가", "더 많은가")):
        return "difference"
    if _is_percent_point_difference_query(query):
        return "difference"
    if _is_single_metric_period_comparison(query, generic_operand_labels):
        return "difference"
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
                "label": f"{current_year}년 {label}",
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
                "label": f"{prior_year}년 {label}",
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
            "label": f"당기 {label}",
            "concept": concept,
            "aliases": aliases,
            "keywords": keywords,
            "role": "current_period",
            "required": True,
            "period_hint": "당기",
            "preferred_sections": preferred_sections,
            "preferred_statement_types": preferred_statement_types,
            "binding_policy": binding_policy,
            "unit_family": str(spec.get("unit_family") or "").strip(),
            "surface_contract": surface_contract,
        },
        {
            "label": f"전기 {label}",
            "concept": concept,
            "aliases": aliases,
            "keywords": keywords,
            "role": "prior_period",
            "required": True,
            "period_hint": "전기",
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
        "사업보고서",
        "반기보고서",
        "분기보고서",
        "연결",
        "별도",
        "매출",
        "부문",
        "세그먼트",
        "segment",
    }

    def _valid_label(label: str) -> str:
        normalized = _normalise_spaces(label)
        if not normalized:
            return ""
        if normalized in blocked_tokens:
            return ""
        if "부문" in normalized or "세그먼트" in normalized:
            return ""
        if any(token in normalized for token in ("사업보고서", "반기보고서", "분기보고서")):
            return ""
        if re.fullmatch(r"20\d{2}", normalized):
            return ""
        if len(normalized) > 40:
            return ""
        return normalized

    labels: List[str] = []

    if any(marker in text for marker in ("부문", "세그먼트", "segment")):
        segment_anchor = ""
        for marker in ("부문의", "부문", "세그먼트의", "세그먼트", "segment"):
            if marker in text:
                segment_anchor = marker
                break
        if segment_anchor:
            prefix = text.split(segment_anchor, 1)[0].strip()
            for boundary in ("에서", "중", "내", ":"):
                if boundary in prefix:
                    prefix = prefix.rsplit(boundary, 1)[-1].strip()
            prefix = re.sub(r"\b20\d{2}\b", " ", prefix)
            raw_parts = re.split(r"\s*(?:와|과|및|,|/|·|\+)\s*", prefix)
            for part in raw_parts:
                normalized = _valid_label(part)
                if normalized:
                    labels.append(normalized)

    token_patterns = (
        r"([A-Za-z0-9가-힣&/\-]{1,20})\s*부문",
        r"([A-Za-z0-9가-힣&/\-]{1,20})\s*세그먼트",
        r"([A-Za-z0-9가-힣&/\-]{1,20})\s*매출",
    )
    for pattern in token_patterns:
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
            if operation_family == "sum":
                # Sum tasks can legitimately use the same concept more than once when the
                # planner is adding segment- or scope-specific values (for example, SDC
                # revenue + Harman revenue). Preserve distinct addend roles while still
                # collapsing exact duplicates.
                dedupe_key = (concept_key, str(role or "").strip())
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
    labels = [str(spec.get("name") or "").strip() for spec in ordered_specs if str(spec.get("name") or "").strip()]
    if operation_family == "ratio" and labels:
        return f"{' + '.join(labels)} 비율"
    if operation_family == "sum" and labels:
        return f"{' + '.join(labels)} 합계"
    if operation_family == "difference" and labels:
        if len(labels) >= 2:
            return f"{labels[0]}과 {labels[1]} 차이"
        return f"{labels[0]} 차이"
    if operation_family == "growth_rate" and labels:
        return f"{labels[0]} 증가율"
    if labels:
        return labels[0]
    return _clean_metric_label(query) or "개념 기반 수치"


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
    return {
        "consolidation_scope": str(consolidation_scope or "unknown"),
        "period_focus": str(period_focus or "unknown"),
        "entity_scope": str(defaults.get("entity_scope") or "company"),
        "segment_scope": "segment" if "부문" in _normalise_spaces(query) else "none",
    }


def _build_concept_numeric_task(
    *,
    query: str,
    topic: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    concept_specs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    operation_family = _infer_operation_family_from_query(query, ontology)
    operand_specs = _build_concept_required_operands(query, report_scope, concept_specs, operation_family)
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
    metric_label = _build_concept_metric_label(query, concept_specs, operation_family)
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
    return {
        "task_id": "task_1",
        "metric_family": f"concept_{operation_family}",
        "metric_label": metric_label,
        "query": task_query,
        "operation_family": operation_family,
        "required_operands": operand_specs,
        "preferred_statement_types": preferred_statement_types,
        "preferred_sections": preferred_sections,
        "retrieval_queries": retrieval_queries,
        "constraints": constraints,
    }


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

    base_label = "매출액" if "매출" in _normalise_spaces(query) else _infer_generic_metric_label(query, "")
    concept_spec = _infer_generic_concept_spec(base_label, ontology)
    if not concept_spec:
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
        "segment_scope": "segment" if "부문" in _normalise_spaces(query) else "none",
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


def _infer_period_focus(query: str, default_value: str = "unknown") -> str:
    text = _normalise_spaces(query)
    if any(keyword in text for keyword in ("전기", "전년", "이전 연도", "직전 연도")):
        return "prior"
    if any(keyword in text for keyword in ("당기", "금년", "현재 연도", "이번 연도")):
        return "current"
    explicit_years = list(dict.fromkeys(re.findall(r"20\d{2}", text)))
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
    year_text = f"{year}년 " if str(year or "").strip() else ""
    consolidation_scope = str((constraints or {}).get("consolidation_scope") or "unknown").strip()
    consolidation_text = ""
    if consolidation_scope == "consolidated":
        consolidation_text = "연결기준 "
    elif consolidation_scope == "separate":
        consolidation_text = "별도기준 "

    operand_labels = [str(spec.get("label") or "").strip() for spec in operand_specs if str(spec.get("label") or "").strip()]
    operand_hint = f"({ '/'.join(operand_labels) })" if len(operand_labels) >= 2 else ""
    canonical_query = _normalise_spaces(f"{year_text}{consolidation_text}{metric_label}{operand_hint}을 계산해 줘.")
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
    matched_metric_keys = {
        str(item.get("key") or "").strip()
        for item in matches
        if str(item.get("key") or "").strip()
    }
    metric_keys: List[str] = []
    planner_notes: List[str] = []
    concept_specs = ontology.concept_specs(query, topic, intent)
    operation_family = _infer_operation_family_from_query(query, ontology)
    entity_scoped_specs = _build_entity_scoped_concept_specs(
        query=query,
        report_scope=report_scope,
        ontology=ontology,
        operation_family=operation_family,
    )
    if entity_scoped_specs and (
        not concept_specs
        or (
            operation_family in {"sum", "difference"}
            and len(concept_specs) == 1
            and len(entity_scoped_specs) >= 2
        )
    ):
        concept_specs = entity_scoped_specs
        planner_notes.append("entity_scoped_concept_fallback")
    if not target_metric_family and concept_specs:
        concept_task = _build_concept_numeric_task(
            query=query,
            topic=topic,
            report_scope=report_scope,
            ontology=ontology,
            concept_specs=concept_specs,
        )
        if concept_task:
            return {
                "status": "concept_fallback",
                "fallback_to_general_search": False,
                "planned_metric_families": [str(concept_task.get("metric_family") or "").strip()],
                "tasks": [concept_task],
                "planner_notes": planner_notes + ["concept_first_preferred"],
            }
    if target_metric_family:
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
    metric_keys.extend(
        str(item.get("key") or "").strip()
        for item in matches
        if str(item.get("key") or "").strip() and _query_mentions_metric(query, item)
    )
    metric_keys = list(dict.fromkeys(metric_keys))

    tasks: List[Dict[str, Any]] = []
    if not metric_keys:
        concept_task = _build_concept_numeric_task(
            query=query,
            topic=topic,
            report_scope=report_scope,
            ontology=ontology,
            concept_specs=concept_specs,
        )
        if concept_task:
            return {
                "status": "concept_fallback",
                "fallback_to_general_search": False,
                "planned_metric_families": [str(concept_task.get("metric_family") or "").strip()],
                "tasks": [concept_task],
                "planner_notes": planner_notes + ["concept_numeric_task"],
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
                "planner_notes": planner_notes + ["heuristic_numeric_task"],
            }
        return {
            "status": "fallback_general_search",
            "fallback_to_general_search": True,
            "planned_metric_families": [],
            "tasks": [],
            "planner_notes": planner_notes + ["ontology_match_missing"],
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
    headers = [str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()]
    if query_years:
        for year in query_years:
            year_text = str(year)
            if any(year_text in header for header in headers):
                return year_text
    header_text = " ".join(headers)
    if period_focus == "current" and any(token in header_text for token in ("당기", "현재")):
        return "당기"
    if period_focus == "prior" and any(token in header_text for token in ("전기", "이전")):
        return "전기"
    fiscal_rank = _structured_cell_fiscal_rank(cell)
    if fiscal_rank is not None and query_years:
        current_year = max(query_years)
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
    return list(query_years or [])


def _operand_period_focus(operand: Dict[str, Any], default_period_focus: str) -> str:
    hint = str(operand.get("period_hint") or "").strip()
    role = str(operand.get("role") or "").strip()
    if hint in {"당기", "현재"} or role == "current_period":
        return "current"
    if hint in {"전기", "이전"} or role == "prior_period":
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

    non_generic_headers = [header for header in headers if header not in _GENERIC_COLUMN_HEADERS]
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

    aggregate_tokens = ("합계", "총계", "소계", "계")
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
    if period_focus == "current":
        if any(token in header_text for token in ("당기", "현재")):
            score += 4.0
        if any(token in header_text for token in ("전기", "이전")):
            score -= 1.0
    elif period_focus == "prior":
        if any(token in header_text for token in ("전기", "이전")):
            score += 4.0
        if any(token in header_text for token in ("당기", "현재")):
            score -= 1.0
    if operand:
        score += _structured_cell_operand_affinity(cell, operand)
    if not header_text:
        score -= 0.25
    return score


def _operand_needles(operand: Dict[str, Any]) -> List[str]:
    label = str(operand.get("label") or "").strip()
    aliases = [str(item).strip() for item in (operand.get("aliases") or []) if str(item).strip()]
    return [needle for needle in [label, *aliases] if needle]


_LEGACY_CONCEPT_SURFACE_CONTRACTS: Dict[str, Dict[str, List[str]]] = {
    "income_before_income_taxes": {
        "positive": [
            "법인세비용차감전순이익",
            "법인세비용차감전순손익",
            "법인세비용 차감 전 순이익",
            "법인세비용 차감 전 순손익",
            "세전이익",
            "세전순이익",
        ],
        "negative": [
            "계속영업순이익",
            "계속영업순손익",
            "당기순이익",
            "당기순손익",
        ],
    }
}


def _operand_surface_contract(operand: Dict[str, Any]) -> Dict[str, List[str]]:
    explicit_contract = dict(operand.get("surface_contract") or {})
    if explicit_contract:
        return {
            "positive": [str(item).strip() for item in (explicit_contract.get("positive") or []) if str(item).strip()],
            "negative": [str(item).strip() for item in (explicit_contract.get("negative") or []) if str(item).strip()],
        }

    concept_key = _normalise_spaces(str(operand.get("concept") or ""))
    if concept_key and concept_key in _LEGACY_CONCEPT_SURFACE_CONTRACTS:
        return dict(_LEGACY_CONCEPT_SURFACE_CONTRACTS[concept_key])

    needles = " ".join(_operand_needles(operand))
    for contract in _LEGACY_CONCEPT_SURFACE_CONTRACTS.values():
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


def _candidate_conflicts_with_operand_concept(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    contract = _operand_surface_contract(operand)
    if not contract:
        return False

    metadata = dict(candidate.get("metadata") or {})
    authoritative_surfaces = [
        str(metadata.get("semantic_label") or "").strip(),
        str(metadata.get("row_label") or "").strip(),
        str(metadata.get("aggregate_label") or "").strip(),
        " ".join(str(item).strip() for item in (metadata.get("semantic_aliases") or []) if str(item).strip()),
        " ".join(str(item).strip() for item in (metadata.get("row_headers") or []) if str(item).strip()),
        str(metadata.get("table_row_labels_text") or "").strip(),
    ]
    authoritative_surfaces = [surface for surface in authoritative_surfaces if surface]
    if any(_text_has_negative_surface(surface, operand) for surface in authoritative_surfaces):
        return True

    if any(_text_has_positive_surface(surface, operand) for surface in authoritative_surfaces):
        return False

    return _text_has_negative_surface(str(candidate.get("text") or ""), operand)


def _operand_row_conflicts_with_requirement(row: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    contract = _operand_surface_contract(operand)
    if not contract:
        return False

    authoritative_surfaces = [
        str(row.get("matched_operand_label") or "").strip(),
        str(row.get("label") or "").strip(),
    ]
    authoritative_surfaces = [surface for surface in authoritative_surfaces if surface]
    if any(_text_has_negative_surface(surface, operand) for surface in authoritative_surfaces):
        return True
    return False


def _operand_text_match(text: str, operand: Dict[str, Any]) -> bool:
    haystack = _normalise_spaces(text or "")
    if not haystack:
        return False
    haystack_compact = re.sub(r"\s+", "", haystack)
    for needle in _operand_needles(operand):
        normalized_needle = _normalise_spaces(needle)
        if not normalized_needle:
            continue
        needle_compact = re.sub(r"\s+", "", normalized_needle)
        if (
            haystack == normalized_needle
            or normalized_needle in haystack
            or (needle_compact and needle_compact in haystack_compact)
        ):
            return True
    return False


def _extract_numeric_value_after_operand_text(text: str, operand: Dict[str, Any]) -> str:
    normalized = _normalise_spaces(text or "")
    if not normalized:
        return ""
    value_pattern = re.compile(r"[\d,]+(?:\s*조\s*[\d,]+\s*억(?:원)?)?|[\d,]+")
    for needle in _operand_needles(operand):
        compact = re.sub(r"\s+", "", _normalise_spaces(needle))
        if not compact:
            continue
        spaced_pattern = r"\s*".join(re.escape(char) for char in compact)
        match = re.search(spaced_pattern, normalized)
        if not match:
            continue
        suffix = normalized[match.end() :]
        value_match = value_pattern.search(suffix)
        if value_match:
            return _normalise_spaces(value_match.group(0))
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
    if compact == "소계":
        return "subtotal"
    if compact in {"합계", "총계", "계"}:
        return "final"
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
        cells.append(
            {
                "column_headers": [str(header).strip()] if str(header).strip() else [],
                "value_text": raw_value,
                "unit_hint": str(metadata.get("unit_hint") or "").strip(),
            }
        )
    return cells


_GENERIC_COLUMN_HEADERS = {
    "구분",
    "항목",
    "내용",
    "세부항목",
    "비고",
    "차입금명칭",
}


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
        candidates.append(candidate)
    return candidates


def _column_candidate_label(column_headers: List[str]) -> str:
    cleaned = [_normalise_spaces(header) for header in column_headers if _normalise_spaces(header)]
    if not cleaned:
        return ""
    filtered = [header for header in cleaned if header not in _GENERIC_COLUMN_HEADERS]
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
            candidate["metadata"]["structured_cells"] = cells
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


_NON_VALUE_ROW_LABELS = {
    "범위",
    "하위범위",
    "상위범위",
    "범위 합계",
}

_BALANCE_SHEET_AGGREGATE_LABELS = {
    "자산총계",
    "부채총계",
    "자본총계",
    "유동자산",
    "비유동자산",
    "유형자산",
    "무형자산",
    "유동부채",
    "비유동부채",
}


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
    for raw in metadata.get("period_labels") or []:
        years.update(int(token) for token in re.findall(r"20\d{2}", str(raw or "")))
    for cell in metadata.get("structured_cells") or []:
        cell_data = dict(cell or {})
        for raw in (
            str(cell_data.get("period_text") or ""),
            " ".join(str(item).strip() for item in (cell_data.get("column_headers") or []) if str(item).strip()),
        ):
            years.update(int(token) for token in re.findall(r"20\d{2}", raw))
    return sorted(years)


def _candidate_is_descriptor_row(candidate: Dict[str, Any]) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    row_label = _normalise_spaces(str(metadata.get("row_label") or ""))
    if row_label in _NON_VALUE_ROW_LABELS:
        return True

    structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
    if structured_cells and not any(re.search(r"\d", str(cell.get("value_text") or "")) for cell in structured_cells):
        return True

    row_text = _normalise_spaces(str(metadata.get("row_text") or ""))
    if row_text and "|" in row_text:
        parts = [part.strip() for part in row_text.split("|")]
        if parts and _normalise_spaces(parts[0]) in _NON_VALUE_ROW_LABELS:
            numeric_parts = [part for part in parts[1:] if re.search(r"\d", part)]
            if not numeric_parts:
                return True

    return False


def _is_balance_sheet_aggregate_operand(operand: Dict[str, Any]) -> bool:
    needles = {re.sub(r"\s+", "", _normalise_spaces(needle)) for needle in _operand_needles(operand)}
    needles.discard("")
    return any(needle in _BALANCE_SHEET_AGGREGATE_LABELS for needle in needles)


def _is_capex_total_operand(operand: Dict[str, Any]) -> bool:
    concept = str(operand.get("concept") or "").strip()
    if concept == "capital_expenditure_total":
        return True
    needles = {re.sub(r"\s+", "", _normalise_spaces(needle)) for needle in _operand_needles(operand)}
    needles.discard("")
    return any(
        needle in {"시설투자", "시설투자(capex)", "capex", "자본적지출", "시설투자총액"}
        for needle in needles
    )


def _operand_segment_label(operand: Dict[str, Any]) -> str:
    binding_policy = dict(operand.get("binding_policy") or {})
    return _normalise_spaces(str(binding_policy.get("segment_label") or ""))


def _candidate_segment_surfaces(candidate: Dict[str, Any]) -> List[str]:
    metadata = dict(candidate.get("metadata") or {})
    surfaces = [
        str(metadata.get("semantic_label") or "").strip(),
        str(metadata.get("row_label") or "").strip(),
        str(metadata.get("aggregate_label") or "").strip(),
        " ".join(str(item).strip() for item in (metadata.get("semantic_aliases") or []) if str(item).strip()),
        " ".join(str(item).strip() for item in (metadata.get("row_headers") or []) if str(item).strip()),
        str(metadata.get("row_text") or "").strip(),
        str(metadata.get("table_row_labels_text") or "").strip(),
        str(metadata.get("table_context") or "").strip(),
        str(metadata.get("table_summary_text") or "").strip(),
        str(metadata.get("local_heading") or "").strip(),
        str(metadata.get("section_path") or "").strip(),
        str(candidate.get("text") or "").strip(),
        str(candidate.get("source_anchor") or "").strip(),
    ]
    return [_normalise_spaces(surface) for surface in surfaces if _normalise_spaces(surface)]


def _candidate_matches_segment_binding(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    segment_label = _operand_segment_label(operand)
    if not segment_label:
        return True

    normalized_segment = _normalise_spaces(segment_label)
    compact_segment = re.sub(r"\s+", "", normalized_segment)
    for surface in _candidate_segment_surfaces(candidate):
        compact_surface = re.sub(r"\s+", "", surface)
        if normalized_segment in surface or (compact_segment and compact_segment in compact_surface):
            return True
    return False


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
        if any(token in context_text for token in ("매출 및 수주상황", "부문", "세그먼트", "segment")):
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
            if "연결" in local_heading:
                score += 0.5
            elif "별도" in local_heading:
                score -= 0.5
        elif statement_type == "notes":
            score -= 1.5
            if value_role == "detail":
                score -= 1.25

    if _is_capex_total_operand(operand):
        if any(token in local_heading for token in ("원재료 및 생산설비", "시설투자", "사업의 내용")):
            score += 2.75
            if value_role == "aggregate":
                score += 1.0
            if aggregation_stage in {"final", "direct", "subtotal"}:
                score += 0.75
        if statement_type == "cash_flow":
            score -= 2.5
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


def _candidate_is_direct_grounding_candidate(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    constraints: Dict[str, Any],
    query_years: List[int],
    operation_family: str = "",
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
    if not _binding_policy_allows_candidate_shape(
        value_role=value_role,
        aggregation_stage=aggregation_stage,
        operand_binding_policy=operand_binding_policy,
    ):
        return False

    desired_consolidation = str((constraints or {}).get("consolidation_scope") or "unknown").strip()
    if desired_consolidation == "unknown":
        desired_consolidation = str(operand_binding_policy.get("prefer_consolidation_scope") or "unknown").strip()
    candidate_consolidation = str(metadata.get("consolidation_scope") or "unknown").strip()
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
    if not _candidate_matches_segment_binding(candidate, operand):
        return False
    candidate_period_focus = str(metadata.get("period_focus") or "unknown").strip()
    row_text = _normalise_spaces(str(metadata.get("row_text") or ""))
    trust_candidate_period_focus = not (candidate_kind == "table_row" and row_text)
    if trust_candidate_period_focus:
        if desired_period_focus == "current" and candidate_period_focus == "prior":
            return False
        if desired_period_focus == "prior" and candidate_period_focus == "current":
            return False

    if operation_family in {"lookup", "single_value"} and candidate_kind == "table_row":
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
) -> bool:
    if not _candidate_is_direct_grounding_candidate(
        candidate,
        operand=operand,
        constraints=constraints,
        query_years=query_years,
        operation_family=operation_family,
    ):
        return False

    metadata = dict(candidate.get("metadata") or {})
    desired_period_focus = _operand_period_focus(
        operand,
        str((constraints or {}).get("period_focus") or "unknown").strip(),
    )
    if selected_cell:
        period_text = _structured_cell_period_text(
            selected_cell,
            query_years,
            desired_period_focus,
        )
        normalized_period = _normalise_spaces(period_text)
        if desired_period_focus == "current" and normalized_period and any(
            token in normalized_period for token in ("전기", "이전")
        ):
            return False
        if desired_period_focus == "prior" and normalized_period and any(
            token in normalized_period for token in ("당기", "현재")
        ):
            return False
        target_years = _operand_target_years(operand, query_years)
        explicit_years = [int(token) for token in re.findall(r"20\d{2}", period_text or "")]
        if target_years and explicit_years and not any(year in explicit_years for year in target_years):
            return False

    if operation_family in {"lookup", "single_value"}:
        direct_match_strength = _candidate_direct_match_strength(candidate, operand)
        if direct_match_strength < 1.5:
            return False

    statement_type = str(metadata.get("statement_type") or "unknown").strip()
    value_role = _candidate_value_role(candidate)
    if _is_balance_sheet_aggregate_operand(operand):
        if statement_type == "notes" and value_role == "detail":
            return False

    metadata_periods = [str(item).strip() for item in (metadata.get("period_labels") or []) if str(item).strip()]
    target_years = _operand_target_years(operand, query_years)
    if desired_period_focus == "prior" and target_years and metadata_periods:
        flattened = " ".join(metadata_periods)
        explicit_years = [int(token) for token in re.findall(r"20\d{2}", flattened)]
        if explicit_years and not any(year in explicit_years for year in target_years):
            return False

    return True


def _candidate_matches_operand(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    if _candidate_conflicts_with_operand_concept(candidate, operand):
        return False

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
    if _operand_text_match(str(metadata.get("table_row_labels_text") or ""), operand):
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
    return _operand_text_match(str(candidate.get("text") or ""), operand)


def _is_delta_like_row_label(label: str) -> bool:
    text = _normalise_spaces(str(label or ""))
    if not text:
        return False
    return any(token in text for token in ("증가(감소)", "증가", "감소", "증감", "변동"))


def _candidate_direct_match_strength(candidate: Dict[str, Any], operand: Dict[str, Any]) -> float:
    """Score how directly a candidate label represents the requested operand."""
    if _candidate_conflicts_with_operand_concept(candidate, operand):
        return 0.0

    metadata = dict(candidate.get("metadata") or {})
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
        (str(metadata.get("table_row_labels_text") or "").strip(), 1.25),
        (str(metadata.get("row_text") or "").strip(), 1.0),
    ]
    best = 0.0
    for surface, exact_bonus in surfaces:
        normalized_surface = _normalise_spaces(surface)
        if not normalized_surface:
            continue
        if any(_normalise_spaces(needle) == normalized_surface for needle in _operand_needles(operand)):
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
                best = max(best, 1.75)
    return best


def _score_operand_candidate(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    preferred_statement_types: List[str],
    constraints: Dict[str, Any],
    query_years: List[int],
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
        if any(_normalise_spaces(row_label) == _normalise_spaces(needle) for needle in _operand_needles(operand)):
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

    desired_consolidation = str((constraints or {}).get("consolidation_scope") or "unknown").strip()
    candidate_consolidation = str(metadata.get("consolidation_scope") or "unknown").strip()
    desired_period_focus = _operand_period_focus(operand, str((constraints or {}).get("period_focus") or "unknown").strip())
    if desired_consolidation == "unknown":
        desired_consolidation = str(operand_binding_policy.get("prefer_consolidation_scope") or "unknown").strip()
    if desired_period_focus == "unknown":
        desired_period_focus = str(operand_binding_policy.get("prefer_period_focus") or "unknown").strip()
    if desired_period_focus in {"current", "prior"} and _is_delta_like_row_label(semantic_label or row_label):
        score -= 4.0
    candidate_period_focus = str(metadata.get("period_focus") or "unknown").strip()
    local_heading = _normalise_spaces(
        str(metadata.get("local_heading") or metadata.get("table_context") or metadata.get("section_path") or "")
    )
    section_path = _normalise_spaces(str(metadata.get("section_path") or ""))
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
            if "연결" in local_heading:
                score += 1.5
            elif "별도" in local_heading:
                score -= 1.5
        elif desired_consolidation == "separate":
            if "별도" in local_heading:
                score += 1.5
            elif "연결" in local_heading:
                score -= 1.5

    if desired_period_focus == "current":
        if candidate_period_focus == "current":
            score += 2.5
        elif candidate_period_focus == "prior":
            score -= 2.5
    elif desired_period_focus == "prior":
        if candidate_period_focus == "prior":
            score += 2.5
        elif candidate_period_focus == "current":
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

    if str(metadata.get("table_source_id") or "").strip():
        score += 0.25

    return score


def _build_reconciliation_retry_queries(
    *,
    active_subtask: Dict[str, Any],
    missing_operands: List[str],
    years: List[int],
) -> List[str]:
    metric_label = str(active_subtask.get("metric_label") or "").strip()
    constraints = dict(active_subtask.get("constraints") or {})
    preferred_sections = [str(item).strip() for item in (active_subtask.get("preferred_sections") or []) if str(item).strip()]
    required_operands = list(active_subtask.get("required_operands") or [])
    operand_map = {str(item.get("label") or "").strip(): item for item in required_operands if str(item.get("label") or "").strip()}

    prefixes: List[str] = []
    if years:
        prefixes.append(f"{years[0]}년")
    consolidation_scope = str(constraints.get("consolidation_scope") or "unknown").strip()
    if consolidation_scope == "consolidated":
        prefixes.append("연결기준")
    elif consolidation_scope == "separate":
        prefixes.append("별도기준")

    queries: List[str] = []
    for operand_label in missing_operands:
        spec = dict(operand_map.get(operand_label) or {})
        aliases = [str(item).strip() for item in (spec.get("aliases") or []) if str(item).strip()]
        base_bits = prefixes + [operand_label, metric_label]
        if preferred_sections:
            base_bits.append(preferred_sections[0])
        queries.append(_normalise_spaces(" ".join(base_bits)))
        if aliases:
            alias_bits = prefixes + [aliases[0], metric_label]
            if preferred_sections:
                alias_bits.append(preferred_sections[0])
            queries.append(_normalise_spaces(" ".join(alias_bits)))
    return list(dict.fromkeys(item for item in queries if item))


def _deterministic_reconcile_task(
    *,
    active_subtask: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    years: List[int],
    reconciliation_retry_count: int,
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
        ranked = sorted(
            matches,
            key=lambda candidate: _score_operand_candidate(
                candidate,
                operand=operand,
                preferred_statement_types=preferred_statement_types,
                constraints=constraints,
                query_years=years,
            ),
            reverse=True,
        )
        operand_top_candidates[label] = ranked
        if ranked:
            direct_candidate = next(
                (
                    candidate
                    for candidate in ranked
                    if _candidate_is_direct_grounding_candidate(
                        candidate,
                        operand=operand,
                        constraints=constraints,
                        query_years=years,
                        operation_family=operation_family,
                    )
                ),
                None,
            )
            if direct_candidate:
                direct_candidate_id = str(direct_candidate.get("candidate_id") or "").strip()
                top = [direct_candidate]
                top.extend(
                    candidate
                    for candidate in ranked
                    if str(candidate.get("candidate_id") or "").strip() != direct_candidate_id
                )
                top = top[:3]
            else:
                top = ranked[:3]
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
    text = _normalise_spaces(f"{query} {topic}")
    preferred: List[str] = []
    ontology_sections = get_financial_ontology().preferred_sections(query, topic, intent)
    preferred.extend(ontology_sections)
    if "연구개발" in text:
        preferred.extend(["연구개발 활동", "요약재무정보"])
    if "영업이익" in text or "당기순이익" in text or "순이익" in text:
        preferred.extend(["요약재무정보", "손익계산서"])
    if "매출" in text or "수익" in text:
        preferred.extend(["매출 및 수주상황", "손익계산서", "요약재무정보"])
    if any(keyword in text for keyword in ("부채비율", "유동비율", "자산총계", "부채총계", "자본총계", "유동자산", "유동부채")):
        preferred.extend(["재무상태표", "요약재무정보", "위험관리 및 파생거래"])
    if _is_ratio_percent_query(text):
        preferred.extend(["요약재무정보", "손익계산서", "재무상태표"])
    return list(dict.fromkeys(preferred))


def _is_percent_point_difference_query(text: str) -> bool:
    normalized = _normalise_spaces(text)
    if "%p" in normalized:
        return True
    ratio_metric = any(keyword in normalized for keyword in ("비율", "비중", "이익률"))
    if not ratio_metric:
        return False
    comparison_markers = (
        "차이",
        "격차",
        "비교",
        "증감",
        "변화",
        "변동",
        "몇 %p",
        "몇%p",
    )
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
    match = re.search(
        r"([\d,]+\s*조\s*[\d,]+\s*억(?:\s*원)?|[\d,]+\s*억(?:\s*원)?|[\d,]+\s*백만원|[\d,.]+%)",
        tail,
    )
    if not match:
        return None, ""
    raw_value = _normalise_spaces(match.group(1))
    if "%" in raw_value:
        return raw_value, "%"
    if "백만원" in raw_value:
        return raw_value.replace("백만원", "").strip(), "백만원"
    if "조" in raw_value or "억" in raw_value:
        return raw_value, "원"
    return raw_value, ""


def _supplement_section_terms_for_query(query: str, topic: str, intent: str) -> List[str]:
    if intent not in {"comparison", "trend"}:
        return []
    sections: List[str] = []
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
    if intent not in {"comparison", "trend"}:
        return ""
    text = _normalise_spaces(topic)
    hints: List[str] = []
    hints.extend(get_financial_ontology().query_hints(query, topic, intent))
    if "영업이익" in text or "당기순이익" in text or "순이익" in text:
        hints.extend(["손익계산서", "요약재무정보"])
    if "매출" in text or "수익" in text:
        hints.extend(["매출 및 수주상황", "손익계산서"])
    if any(keyword in text for keyword in ("부채비율", "유동비율", "자산총계", "부채총계", "자본총계", "유동자산", "유동부채")):
        hints.extend(["재무상태표", "요약재무정보", "부채총계", "자본총계", "유동자산", "유동부채"])
    if "연구개발" in text:
        hints.append("연구개발")
        # R&D 비중/비율 질문은 분모(총 매출)가 요약재무정보에 있으므로 함께 힌트 추가
        if any(kw in text for kw in ("비중", "비율", "이익률", "차지")):
            hints.append("요약재무정보")
    if "설비투자" in text or "투자" in text:
        hints.extend(["요약재무정보", "재무제표"])
    return " ".join(dict.fromkeys(hints))


