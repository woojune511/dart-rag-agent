"""Operation-family policy helpers used across retrieval and calculation."""

from __future__ import annotations

from typing import Any, Dict, List

from src.agent.financial_runtime_normalization import _normalise_spaces
from src.config.retrieval_policy import (
    GENERIC_PERIOD_OPERAND_POLICY,
    HELPER_RUNTIME_POLICY,
    KOREAN_PERCENT_METRIC_HINT_TERMS,
    PERCENT_POINT_DIFFERENCE_POLICY,
    RATIO_PERCENT_QUERY_POLICY,
)


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


def _is_ratio_percent_query(text: str) -> bool:
    normalized = _normalise_spaces(text)
    return any(keyword in normalized for keyword in (RATIO_PERCENT_QUERY_POLICY.get("markers") or ()))


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


def _label_implies_percent_metric(label: str) -> bool:
    normalized = _normalise_spaces(str(label or ""))
    if not normalized:
        return False
    return any(
        token in normalized
        for token in (*KOREAN_PERCENT_METRIC_HINT_TERMS, "%", "%p")
    )


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
