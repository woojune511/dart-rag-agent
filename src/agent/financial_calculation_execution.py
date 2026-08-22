"""Deterministic calculation execution and payload helpers."""

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

from src.agent.financial_answer_slots import build_answer_slots, build_calculated_value_slot
from src.agent.financial_formula_eval import _safe_eval_formula
from src.agent.financial_operand_resolution import (
    missing_required_operands,
    operand_row_matches_requirement,
    ratio_operand_rows_collapse_to_same_slot,
)
from src.agent.financial_operation_policies import should_coerce_percent_point_unit
from src.agent.financial_runtime_normalization import (
    _clean_source_row_ids,
    _normalise_operand_value,
    _normalise_spaces,
)
from src.agent.financial_runtime_trace import _runtime_trace_state_update
from src.agent.financial_scope_policies import extract_period_sort_key
from src.agent.financial_task_artifacts import calculation_result_artifact_update as _calculation_result_artifact_update
from src.config import get_financial_ontology


CalculationExecutionStatus = Literal[
    "ok",
    "insufficient_operands",
    "zero_division",
    "unit_mismatch",
    "parse_error",
]

StaleCalculationValueAssessmentReason = Literal[
    "stale",
    "current",
    "expected_value_unavailable",
    "current_value_unavailable",
]

DeterministicOperationPlanDecisionStatus = Literal[
    "not_applicable",
    "guarded",
    "ready",
]


@dataclass(frozen=True)
class CalculationExecutionOutcome:
    """Explicit boundary between prepared operands and result projection."""

    status: CalculationExecutionStatus
    reason: str
    result_value: Optional[float]
    normalized_unit: str
    source_normalized_unit: str
    ordered_operands: Tuple[Dict[str, Any], ...]
    selected_evidence_ids: Tuple[str, ...]
    yoy_growth_rates: Tuple[Any, ...] = ()


@dataclass(frozen=True)
class StaleCalculationValueAssessment:
    """State-free comparison between a canonical value and a projected result."""

    is_stale: bool
    reason: StaleCalculationValueAssessmentReason
    expected_value: Optional[float] = None
    current_value: Optional[float] = None
    tolerance: Optional[float] = None


@dataclass(frozen=True)
class DeterministicOperationPlanDecision:
    """State-free validation outcome for a deterministic operation plan."""

    status: DeterministicOperationPlanDecisionStatus
    raw_plan: Dict[str, Any]
    selected_plan: Dict[str, Any]


def assess_stale_calculation_value(
    *,
    expected_value: Any,
    calculation_result: Mapping[str, Any],
) -> StaleCalculationValueAssessment:
    """Assess whether a projected scalar result disagrees with a canonical value."""

    try:
        canonical_value = float(expected_value)
    except Exception:
        return StaleCalculationValueAssessment(
            is_stale=False,
            reason="expected_value_unavailable",
        )

    derived_metrics = calculation_result.get("derived_metrics")
    formula_result_value = (
        derived_metrics.get("formula_result_value")
        if (
            isinstance(derived_metrics, dict)
            and derived_metrics.get("source_stated_result_used") is True
        )
        else None
    )
    try:
        current_value = float(formula_result_value)
    except Exception:
        try:
            current_value = float(calculation_result.get("result_value"))
        except Exception:
            return StaleCalculationValueAssessment(
                is_stale=False,
                reason="current_value_unavailable",
                expected_value=canonical_value,
            )

    tolerance = max(1e-6, abs(canonical_value) * 1e-9)
    is_stale = not (abs(canonical_value - current_value) <= tolerance)
    return StaleCalculationValueAssessment(
        is_stale=is_stale,
        reason="stale" if is_stale else "current",
        expected_value=canonical_value,
        current_value=current_value,
        tolerance=tolerance,
    )


def guard_operation_plan(
    *,
    plan: Dict[str, Any],
    operands: List[Dict[str, Any]],
    required_operands: List[Dict[str, Any]],
    operation_family: str,
) -> Optional[Dict[str, Any]]:
    """Reject executable plans that do not bind distinct required roles."""

    family = str(operation_family or plan.get("operation") or "").strip().lower()
    if family not in {"ratio", "difference", "growth_rate"}:
        return None

    operand_by_id = {
        str(row.get("operand_id") or "").strip(): row
        for row in operands
        if str(row.get("operand_id") or "").strip()
    }
    ordered_ids = [
        str(operand_id or "").strip()
        for operand_id in (plan.get("ordered_operand_ids") or [])
        if str(operand_id or "").strip() in operand_by_id
    ]
    if not ordered_ids:
        ordered_ids = [
            str(binding.get("operand_id") or "").strip()
            for binding in (plan.get("variable_bindings") or [])
            if str(binding.get("operand_id") or "").strip() in operand_by_id
        ]
    unique_ids = list(dict.fromkeys(ordered_ids))
    missing_info: List[str] = []

    if len(unique_ids) < 2:
        missing_info.append("distinct_operands")

    selected_rows = [operand_by_id[operand_id] for operand_id in unique_ids]
    if family == "ratio" and required_operands:
        missing_required = missing_required_operands(required_operands, selected_rows)
        missing_info.extend(
            _normalise_spaces(str(item.get("label") or item.get("role") or item.get("concept") or "operand"))
            for item in missing_required
        )

    if family == "ratio":
        numerator_ids: set[str] = set()
        denominator_ids: set[str] = set()
        ratio_requirements = [
            dict(item)
            for item in required_operands
            if str(item.get("role") or "").strip().startswith(("numerator", "denominator"))
        ]
        for row in selected_rows:
            operand_id = str(row.get("operand_id") or "").strip()
            row_role = str(row.get("matched_operand_role") or "").strip()
            if row_role.startswith("numerator"):
                numerator_ids.add(operand_id)
            elif row_role.startswith("denominator"):
                denominator_ids.add(operand_id)
            elif ratio_requirements:
                for requirement in ratio_requirements:
                    role = str(requirement.get("role") or "").strip()
                    if operand_row_matches_requirement(row, requirement):
                        if role.startswith("numerator"):
                            numerator_ids.add(operand_id)
                        elif role.startswith("denominator"):
                            denominator_ids.add(operand_id)

        if not numerator_ids:
            missing_info.append("numerator")
        if not denominator_ids:
            missing_info.append("denominator")
        if numerator_ids and denominator_ids and not (numerator_ids - denominator_ids or denominator_ids - numerator_ids):
            missing_info.append("distinct_ratio_roles")
        if ratio_operand_rows_collapse_to_same_slot(selected_rows):
            missing_info.append("distinct_ratio_roles")

    if not missing_info:
        return None

    missing_info = list(dict.fromkeys(item for item in missing_info if item))
    return {
        "status": "incomplete",
        "mode": "none",
        "operation": "none",
        "ordered_operand_ids": [],
        "variable_bindings": [],
        "formula": "",
        "pairwise_formula": "",
        "result_unit": "",
        "operation_text": "",
        "explanation": "operation plan does not satisfy required operand bindings",
        "missing_info": missing_info,
    }


def build_deterministic_operation_plan(
    *,
    operation_family: str,
    required_operands: Sequence[Mapping[str, Any]],
    operands: Sequence[Mapping[str, Any]],
    metric_label: str,
    difference_result_unit: str,
) -> Optional[Dict[str, Any]]:
    """Build a deterministic difference or growth plan without graph state."""

    family = str(operation_family or "").strip().lower()
    if family not in {"difference", "growth_rate"}:
        return None

    required_rows = [
        dict(item)
        for item in required_operands
        if bool(item.get("required", True))
    ]
    if not required_rows:
        return None

    operand_rows = [dict(row) for row in operands]
    matched_rows: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for operand in required_rows:
        matched_row = next(
            (row for row in operand_rows if operand_row_matches_requirement(row, operand)),
            None,
        )
        if matched_row is None:
            return None
        matched_rows.append((operand, matched_row))

    def _first_pair(role: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        for operand, row in matched_rows:
            if str(operand.get("role") or "").strip() == role:
                return operand, row
        return None

    ordered_pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    if family == "difference":
        left_pair = _first_pair("current_period") or _first_pair("minuend") or _first_pair("numerator")
        right_pair = _first_pair("prior_period") or _first_pair("subtrahend") or _first_pair("denominator")
        if left_pair and right_pair:
            ordered_pairs = [left_pair, right_pair]
        elif len(matched_rows) == 2:
            ordered_pairs = matched_rows
    else:
        current_pair = _first_pair("current_period")
        prior_pair = _first_pair("prior_period")
        if current_pair and prior_pair:
            ordered_pairs = [current_pair, prior_pair]

    if len(ordered_pairs) != 2:
        return None

    variable_bindings: List[Dict[str, str]] = []
    ordered_operand_ids: List[str] = []
    ordered_labels: List[str] = []
    for index, (operand, row) in enumerate(ordered_pairs):
        operand_id = str(row.get("operand_id") or "").strip()
        if not operand_id:
            return None
        variable_bindings.append(
            {"variable": chr(ord("A") + index), "operand_id": operand_id}
        )
        ordered_operand_ids.append(operand_id)
        ordered_labels.append(
            str(operand.get("label") or row.get("label") or "").strip()
        )

    metric_display = str(metric_label or "").strip()
    if family == "difference":
        right_role = str(ordered_pairs[1][0].get("role") or "").strip()
        right_value = ordered_pairs[1][1].get("normalized_value")
        formula = "A - B"
        operation_text = f"{ordered_labels[0]} - {ordered_labels[1]}"
        explanation = f"{metric_display or 'difference'} is computed as A - B."
        if right_role in {"subtrahend", "denominator"} and right_value is not None and float(right_value) < 0:
            formula = "A + B"
            operation_text = f"{ordered_labels[0]} + {ordered_labels[1]}"
            explanation = (
                f"{metric_display or 'difference'} uses sign-aware subtraction "
                "because B is already negative."
            )
        return {
            "status": "ok",
            "mode": "single_value",
            "operation": "subtract",
            "ordered_operand_ids": ordered_operand_ids,
            "variable_bindings": variable_bindings,
            "formula": formula,
            "pairwise_formula": "",
            "result_unit": str(difference_result_unit or "").strip(),
            "operation_text": operation_text,
            "explanation": explanation,
            "missing_info": [],
        }

    return {
        "status": "ok",
        "mode": "single_value",
        "operation": "growth_rate",
        "ordered_operand_ids": ordered_operand_ids,
        "variable_bindings": variable_bindings,
        "formula": "((A - B) / B) * 100",
        "pairwise_formula": "",
        "result_unit": "%",
        "operation_text": f"({ordered_labels[0]} - {ordered_labels[1]}) / {ordered_labels[1]} * 100",
        "explanation": f"{metric_display or 'growth rate'} is computed as ((A - B) / B) * 100.",
        "missing_info": [],
    }


def build_runtime_deterministic_operation_plan(
    state: Mapping[str, Any],
    operands: List[Dict[str, Any]],
    *,
    active_subtask: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    resolved_active_subtask = dict(
        active_subtask
        if active_subtask is not None
        else state.get("active_subtask") or {}
    )
    operation_family = str(resolved_active_subtask.get("operation_family") or "").strip().lower()
    required_operands = [
        dict(item)
        for item in (resolved_active_subtask.get("required_operands") or [])
        if bool(item.get("required", True))
    ]
    metric_label = str(
        resolved_active_subtask.get("metric_label")
        or resolved_active_subtask.get("task_id")
        or ""
    ).strip()
    plan = build_deterministic_operation_plan(
        operation_family=operation_family,
        required_operands=required_operands,
        operands=operands,
        metric_label=metric_label,
        difference_result_unit="",
    )
    if operation_family == "difference" and plan and should_coerce_percent_point_unit(
        str(resolved_active_subtask.get("query") or state["query"]),
        operands,
        plan,
    ):
        plan = {**plan, "result_unit": "%p"}
    return plan


def build_deterministic_ontology_plan(
    active_subtask: Dict[str, Any], operands: List[Dict[str, Any]], *, metric_key: str
) -> Optional[Dict[str, Any]]:
    ontology = get_financial_ontology()
    metric_info = ontology.metric_family(metric_key) or {}
    formula_family = str(metric_info.get("formula_family") or "").strip().lower()
    if not formula_family:
        formula_family = str(active_subtask.get("operation_family") or "").strip().lower()
    if formula_family not in {"ratio", "sum"}:
        return None

    required_operands = [
        dict(item)
        for item in (active_subtask.get("required_operands") or [])
        if bool(item.get("required", True))
    ]
    if not required_operands:
        return None

    matched_rows: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
    missing_labels: List[str] = []

    def _operand_row_preference_score(row: Dict[str, Any], operand: Dict[str, Any]) -> tuple[int, int, int, int, int]:
        required_role = _normalise_spaces(str(operand.get("role") or "")).lower()
        matched_role = _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")).lower()
        role_score = 0
        if required_role and matched_role:
            if matched_role == required_role:
                role_score = 3
            elif required_role.startswith(("numerator", "denominator")) and matched_role.startswith(
                "numerator" if required_role.startswith("numerator") else "denominator"
            ):
                role_score = 2
        required_scope = _normalise_spaces(str(operand.get("consolidation_scope") or "")).lower()
        row_scope = _normalise_spaces(str(row.get("consolidation_scope") or "")).lower()
        scope_score = 0
        if required_scope and row_scope == required_scope:
            scope_score = 2
        elif row_scope == "consolidated":
            scope_score = 1
        statement_type = _normalise_spaces(str(row.get("statement_type") or "")).lower()
        statement_score = 2 if statement_type == "income_statement" else 0
        stage = _normalise_spaces(str(row.get("aggregation_stage") or "")).lower()
        value_role = _normalise_spaces(str(row.get("value_role") or "")).lower()
        aggregate_score = int(value_role == "aggregate") + int(stage in {"direct", "final", "subtotal"})
        source_score = len(_clean_source_row_ids([row.get("source_row_id"), row.get("source_row_ids")]))
        return role_score, scope_score, statement_score, aggregate_score, source_score

    for operand in required_operands:
        candidate_rows = [row for row in operands if operand_row_matches_requirement(row, operand)]
        required_role = str(operand.get("role") or "").strip()
        role_matched_rows = [
            row
            for row in candidate_rows
            if required_role
            and str(row.get("matched_operand_role") or "").strip()
            and (
                str(row.get("matched_operand_role") or "").strip() == required_role
                or (
                    required_role.startswith(("numerator", "denominator"))
                    and str(row.get("matched_operand_role") or "").strip().startswith(
                        "numerator" if required_role.startswith("numerator") else "denominator"
                    )
                )
            )
        ]
        candidate_pool = role_matched_rows or candidate_rows
        matched_row = max(
            candidate_pool,
            key=lambda row: _operand_row_preference_score(row, operand),
            default=None,
        )
        if matched_row is None:
            missing_labels.append(str(operand.get("label") or "").strip() or "required_operand")
            continue
        matched_rows.append((operand, matched_row))

    if missing_labels:
        return None

    if formula_family == "ratio":
        numerator_pairs = [
            (operand, row)
            for operand, row in matched_rows
            if str(operand.get("role") or "").strip().startswith("numerator")
        ]
        denominator_pairs = [
            (operand, row)
            for operand, row in matched_rows
            if str(operand.get("role") or "").strip().startswith("denominator")
        ]
        if not numerator_pairs or not denominator_pairs:
            return None
        ordered_pairs = numerator_pairs + denominator_pairs
    else:
        numerator_pairs = []
        denominator_pairs = []
        ordered_pairs = matched_rows

    variable_bindings: List[Dict[str, str]] = []
    ordered_operand_ids: List[str] = []
    numerator_vars: List[str] = []
    denominator_vars: List[str] = []
    additive_vars: List[str] = []

    for index, (operand, row) in enumerate(ordered_pairs):
        variable = chr(ord("A") + index)
        operand_id = str(row.get("operand_id") or "").strip()
        if not operand_id:
            return None
        variable_bindings.append({"variable": variable, "operand_id": operand_id})
        ordered_operand_ids.append(operand_id)
        role = str(operand.get("role") or "").strip()
        if formula_family == "ratio":
            if role.startswith("numerator"):
                numerator_vars.append(variable)
            elif role.startswith("denominator"):
                denominator_vars.append(variable)
        elif formula_family == "sum":
            additive_vars.append(variable)

    metric_display = (
        str(metric_info.get("display_name") or "").strip()
        or str(active_subtask.get("metric_label") or "").strip()
        or metric_key
    )

    if formula_family == "ratio":
        if not numerator_vars or not denominator_vars:
            return None
        numerator_expr = " + ".join(numerator_vars)
        denominator_expr = " + ".join(denominator_vars)
        denominator_operation_text = " + ".join(
            str(operand.get("label") or "").strip()
            for operand, _row in denominator_pairs
        )
        denominator_aggregation = _normalise_spaces(
            str(
                active_subtask.get("denominator_aggregation")
                or metric_info.get("denominator_aggregation")
                or ""
            )
        ).lower()
        if denominator_aggregation == "average" and len(denominator_vars) > 1:
            denominator_expr = f"(({denominator_expr}) / {len(denominator_vars)})"
            denominator_operation_text = f"average({denominator_operation_text})"
        result_unit = str(active_subtask.get("result_unit") or metric_info.get("result_unit") or "").strip()
        if not result_unit:
            result_unit = "%"
        if result_unit.upper() == "PERCENT":
            result_unit = "%"
        elif result_unit.upper() == "PERCENT_POINT":
            result_unit = "%p"
        percent_result = result_unit in {"%", "퍼센트"} or result_unit.upper() == "PERCENT"
        if result_unit == "%p":
            percent_result = True
        formula = f"(({numerator_expr}) / ({denominator_expr}))"
        operation_suffix = ""
        if percent_result:
            formula = f"{formula} * 100"
            operation_suffix = " * 100"

        numerator_labels = [str(operand.get("label") or "").strip() for operand, _row in numerator_pairs]

        return {
            "status": "ok",
            "mode": "single_value",
            "operation": "ratio",
            "ordered_operand_ids": ordered_operand_ids,
            "variable_bindings": variable_bindings,
            "formula": formula,
            "pairwise_formula": "",
            "result_unit": result_unit,
            "operation_text": f"({' + '.join(numerator_labels)}) / ({denominator_operation_text}){operation_suffix}",
            "explanation": f"{metric_display}의 role에 따라 분자와 분모를 결정해 비율을 계산합니다.",
            "missing_info": [],
        }

    if not additive_vars:
        return None
    additive_labels = [str(operand.get("label") or "").strip() for operand, _row in ordered_pairs]
    result_unit = str(metric_info.get("result_unit") or "").strip()
    return {
        "status": "ok",
        "mode": "single_value",
        "operation": "add",
        "ordered_operand_ids": ordered_operand_ids,
        "variable_bindings": variable_bindings,
        "formula": " + ".join(additive_vars),
        "pairwise_formula": "",
        "result_unit": result_unit,
        "operation_text": " + ".join(additive_labels),
        "explanation": f"{metric_display}에 필요한 concept operand를 합산합니다.",
        "missing_info": [],
    }


def resolve_deterministic_operation_plan(
    *,
    plan: Mapping[str, Any],
    operands: Sequence[Mapping[str, Any]],
    required_operands: Sequence[Mapping[str, Any]],
    operation_family: str,
) -> DeterministicOperationPlanDecision:
    """Select a raw deterministic plan or its binding guard without graph projection."""

    raw_plan = dict(plan or {})
    if not raw_plan:
        return DeterministicOperationPlanDecision(
            status="not_applicable",
            raw_plan={},
            selected_plan={},
        )
    guarded_plan = guard_operation_plan(
        plan=raw_plan,
        operands=[dict(row) for row in operands],
        required_operands=[dict(item) for item in required_operands],
        operation_family=operation_family,
    )
    return DeterministicOperationPlanDecision(
        status="guarded" if guarded_plan else "ready",
        raw_plan=raw_plan,
        selected_plan=dict(guarded_plan or raw_plan),
    )


def execute_prepared_calculation_plan(
    *,
    mode: str,
    operation: str,
    formula: str,
    pairwise_formula: str,
    result_unit: str,
    operands_by_id: Mapping[str, Dict[str, Any]],
    ordered_operand_ids: Sequence[str],
    variable_bindings: Sequence[Dict[str, Any]],
) -> CalculationExecutionOutcome:
    """Execute a prepared calculation plan without reading or mutating graph state."""

    operands = {str(operand_id): dict(row) for operand_id, row in operands_by_id.items()}
    ordered_ids = [
        str(operand_id).strip()
        for operand_id in ordered_operand_ids
        if str(operand_id).strip()
    ]
    binding_rows = [dict(binding) for binding in variable_bindings]
    binding_ids = [
        str(binding.get("operand_id") or "").strip()
        for binding in binding_rows
        if str(binding.get("operand_id") or "").strip()
    ]
    execution_ids = ordered_ids or list(dict.fromkeys(binding_ids))
    ordered_operands = [
        dict(operands[operand_id])
        for operand_id in execution_ids
        if operand_id in operands
    ]
    selected_evidence_ids = tuple(
        dict.fromkeys(
            str(row.get("evidence_id"))
            for row in ordered_operands
            if row.get("evidence_id")
        )
    )

    def _outcome(
        *,
        status: CalculationExecutionStatus,
        reason: str = "",
        result_value: Optional[float] = None,
        normalized_unit: str = "",
        source_normalized_unit: str = "",
        result_operands: Optional[Sequence[Dict[str, Any]]] = None,
        result_evidence_ids: Optional[Sequence[str]] = None,
        yoy_growth_rates: Optional[Sequence[Any]] = None,
    ) -> CalculationExecutionOutcome:
        return CalculationExecutionOutcome(
            status=status,
            reason=reason,
            result_value=result_value,
            normalized_unit=normalized_unit,
            source_normalized_unit=source_normalized_unit,
            ordered_operands=tuple(
                dict(row)
                for row in (ordered_operands if result_operands is None else result_operands)
            ),
            selected_evidence_ids=tuple(
                selected_evidence_ids if result_evidence_ids is None else result_evidence_ids
            ),
            yoy_growth_rates=tuple(() if yoy_growth_rates is None else yoy_growth_rates),
        )

    missing_ordered_ids = [operand_id for operand_id in execution_ids if operand_id not in operands]
    if missing_ordered_ids:
        return _outcome(
            status="parse_error",
            reason=f"unknown ordered operand ids: {list(dict.fromkeys(missing_ordered_ids))}",
        )

    invalid_bindings = [
        binding
        for binding in binding_rows
        if not str(binding.get("variable") or "").strip()
        or not str(binding.get("operand_id") or "").strip()
        or str(binding.get("operand_id") or "").strip() not in operands
    ]
    if invalid_bindings:
        return _outcome(
            status="parse_error",
            reason=f"invalid variable binding: {invalid_bindings[0]}",
        )

    if not binding_ids:
        return _outcome(
            status="insufficient_operands",
            reason="calculation plan has no variable bindings",
        )

    if ordered_ids and set(ordered_ids) != set(binding_ids):
        return _outcome(
            status="parse_error",
            reason="ordered operands and variable bindings disagree",
        )

    units = {row.get("normalized_unit") for row in ordered_operands}
    if len(units) != 1:
        return _outcome(
            status="unit_mismatch",
            reason=f"unit families differ: {sorted(str(unit) for unit in units)}",
        )
    source_normalized_unit = str(next(iter(units)))
    values = [row.get("normalized_value") for row in ordered_operands]
    if any(value is None for value in values):
        return _outcome(
            status="parse_error",
            reason="one or more operands could not be normalized",
            source_normalized_unit=source_normalized_unit,
        )

    try:
        env: Dict[str, float] = {}
        for binding in binding_rows:
            variable = str(binding.get("variable") or "").strip()
            operand_id = str(binding.get("operand_id") or "").strip()
            operand = operands.get(operand_id)
            if not variable or operand is None or operand.get("normalized_value") is None:
                return _outcome(
                    status="parse_error",
                    reason=f"invalid variable binding: {binding}",
                    source_normalized_unit=source_normalized_unit,
                )
            env[variable] = float(operand.get("normalized_value"))

        outcome_operands = ordered_operands
        outcome_evidence_ids = selected_evidence_ids
        growth_rates: Sequence[Any] = ()
        if mode == "time_series":
            if len(binding_rows) < 2:
                return _outcome(
                    status="insufficient_operands",
                    reason="time_series needs at least 2 operands",
                    source_normalized_unit=source_normalized_unit,
                )
            outcome_operands = sorted(
                [operands[str(binding.get("operand_id"))] for binding in binding_rows],
                key=lambda row: extract_period_sort_key(str(row.get("period") or "")),
            )
            outcome_evidence_ids = tuple(
                dict.fromkeys(
                    str(row.get("evidence_id"))
                    for row in outcome_operands
                    if row.get("evidence_id")
                )
            )
            growth_rates = time_series_yoy_growth_rates(
                ordered_operands=outcome_operands,
                pairwise_formula=pairwise_formula,
            )
            if not formula:
                return _outcome(
                    status="parse_error",
                    reason="missing trend formula",
                    source_normalized_unit=source_normalized_unit,
                    result_operands=outcome_operands,
                    result_evidence_ids=outcome_evidence_ids,
                    yoy_growth_rates=growth_rates,
                )
        elif not formula:
            return _outcome(
                status="parse_error",
                reason="missing scalar formula",
                source_normalized_unit=source_normalized_unit,
            )

        result_value = float(_safe_eval_formula(formula, env))
    except ZeroDivisionError as exc:
        return _outcome(
            status="zero_division",
            reason=str(exc),
            source_normalized_unit=source_normalized_unit,
        )
    except Exception as exc:
        return _outcome(
            status="parse_error",
            reason=str(exc),
            source_normalized_unit=source_normalized_unit,
        )

    normalized_unit = source_normalized_unit
    if result_unit in {"%", "%p"}:
        normalized_unit = "PERCENT"
    elif operation == "ratio":
        normalized_unit = "COUNT"
    return _outcome(
        status="ok",
        result_value=result_value,
        normalized_unit=normalized_unit,
        source_normalized_unit=source_normalized_unit,
        result_operands=outcome_operands,
        result_evidence_ids=outcome_evidence_ids,
        yoy_growth_rates=growth_rates,
    )


def build_failed_calculation_result(
    *,
    active_subtask: Dict[str, Any],
    operation_family: str,
    runtime_operands: List[Dict[str, Any]],
    result_unit: str,
    source_normalized_unit: str,
    status: str,
    reason: str,
) -> Dict[str, Any]:
    failure_slots = build_answer_slots(
        active_subtask=active_subtask,
        operation_family=operation_family or "single_value",
        ordered_operands=list(runtime_operands),
        result_value=None,
        result_unit=result_unit,
        normalized_unit="UNKNOWN",
        source_normalized_unit=source_normalized_unit or "UNKNOWN",
        current_value=None,
        prior_value=None,
        delta_value=None,
        current_period="",
        prior_period="",
        source_row_ids=[],
        current_row=None,
        prior_row=None,
    )
    return {
        "status": status,
        "result_value": None,
        "result_unit": result_unit,
        "rendered_value": "",
        "formatted_result": "",
        "series": [],
        "answer_slots": failure_slots,
        "derived_metrics": {},
        "explanation": reason,
    }


def build_success_calculation_state_payload(
    *,
    state: Dict[str, Any],
    calc_result: Dict[str, Any],
    selected_evidence_ids: List[str],
    runtime_operands: List[Dict[str, Any]],
    calculation_plan: Dict[str, Any],
    query: str,
    metric_family: str,
) -> Dict[str, Any]:
    result_payload: Dict[str, Any] = {
        "answer": "",
        "compressed_answer": "",
        "selected_claim_ids": list(selected_evidence_ids),
        "draft_points": [],
        "kept_claim_ids": list(selected_evidence_ids),
        "dropped_claim_ids": [],
        "unsupported_sentences": [],
        "sentence_checks": [],
    }
    active_subtask = dict(state.get("active_subtask") or {})
    task_id = str(active_subtask.get("task_id") or "calc")
    ledger_update = _calculation_result_artifact_update(
        tasks=list(state.get("tasks") or []),
        artifacts=list(state.get("artifacts") or []),
        task_id=task_id,
        task_label=str(active_subtask.get("metric_label") or task_id),
        query=query,
        metric_family=metric_family,
        calculation_result=calc_result,
        evidence_refs=selected_evidence_ids,
    )
    result_payload["tasks"] = list(ledger_update["tasks"])
    result_payload["artifacts"] = list(ledger_update["artifacts"])
    result_payload.update(
        _runtime_trace_state_update(
            state,
            calculation_operands=list(runtime_operands),
            calculation_plan=dict(calculation_plan),
            calculation_result=dict(calc_result),
        )
    )
    return result_payload


def build_scalar_calculation_state(
    *,
    operation_family: str,
    ordered_operands: List[Dict[str, Any]],
    result_value: float,
    normalized_unit: str,
    result_unit: str,
    rendered_with_unit: str,
) -> Dict[str, Any]:
    current_value = None
    prior_value = None
    delta_value = None
    current_period = ""
    prior_period = ""
    current_row = None
    prior_row = None
    source_stated_result_used = False
    source_row_ids = _clean_source_row_ids(
        [
            [
                row.get("evidence_id"),
                row.get("source_row_id"),
                row.get("source_row_ids"),
            ]
            for row in ordered_operands
        ]
    )
    if operation_family in {"lookup", "single_value"} and ordered_operands:
        current_value = float(ordered_operands[0].get("normalized_value"))
        current_period = str(ordered_operands[0].get("period") or "")
    elif operation_family in {"difference", "growth_rate"}:
        current_row = next(
            (
                row
                for row in ordered_operands
                if str(row.get("matched_operand_role") or "").strip() == "current_period"
            ),
            None,
        )
        prior_row = next(
            (
                row
                for row in ordered_operands
                if str(row.get("matched_operand_role") or "").strip() == "prior_period"
            ),
            None,
        )
        if current_row is None and len(ordered_operands) >= 1:
            current_row = ordered_operands[0]
        if prior_row is None and len(ordered_operands) >= 2:
            prior_row = ordered_operands[1]
        if current_row and current_row.get("normalized_value") is not None:
            current_value = float(current_row.get("normalized_value"))
            current_period = str(current_row.get("period") or "")
        if prior_row and prior_row.get("normalized_value") is not None:
            prior_value = float(prior_row.get("normalized_value"))
            prior_period = str(prior_row.get("period") or "")
        if operation_family == "difference":
            delta_value = float(result_value)
        elif operation_family == "growth_rate" and current_row:
            stated_change_raw_value = _normalise_spaces(str(current_row.get("stated_change_raw_value") or ""))
            stated_change_raw_unit = _normalise_spaces(str(current_row.get("stated_change_raw_unit") or "%"))
            if stated_change_raw_value:
                stated_value, stated_unit = _normalise_operand_value(
                    stated_change_raw_value,
                    stated_change_raw_unit or "%",
                )
                if stated_value is not None and str(stated_unit or "").strip().upper() == "PERCENT":
                    result_value = stated_value
                    normalized_unit = "PERCENT"
                    result_unit = "%"
                    rendered_with_unit = f"{stated_change_raw_value}%"
                    source_stated_result_used = True
    return {
        "result_value": result_value,
        "normalized_unit": normalized_unit,
        "result_unit": result_unit,
        "rendered_with_unit": rendered_with_unit,
        "source_stated_result_used": source_stated_result_used,
        "current_value": current_value,
        "prior_value": prior_value,
        "delta_value": delta_value,
        "current_period": current_period,
        "prior_period": prior_period,
        "current_row": current_row,
        "prior_row": prior_row,
        "source_row_ids": source_row_ids,
    }


def build_scalar_calculation_result(
    *,
    result_value: float,
    result_unit: str,
    rendered_with_unit: str,
    result_series: List[Dict[str, Any]],
    scalar_state: Dict[str, Any],
    answer_slots: Dict[str, Any],
    operand_labels: List[str],
    formula: str,
    operation_family: str,
    operation: str,
    formula_result_value: float,
    explanation: str,
) -> Dict[str, Any]:
    return {
        "status": "ok",
        "result_value": result_value,
        "result_unit": result_unit,
        "rendered_value": rendered_with_unit,
        "formatted_result": "",
        "series": list(result_series),
        "current_value": scalar_state.get("current_value"),
        "prior_value": scalar_state.get("prior_value"),
        "delta_value": scalar_state.get("delta_value"),
        "current_period": scalar_state.get("current_period") or "",
        "prior_period": scalar_state.get("prior_period") or "",
        "source_row_ids": list(scalar_state.get("source_row_ids") or []),
        "answer_slots": dict(answer_slots),
        "derived_metrics": {
            "operand_labels": list(operand_labels),
            "formula": formula,
            "operation_family": operation_family or operation,
            "formula_result_value": formula_result_value,
            "source_stated_result_used": bool(scalar_state.get("source_stated_result_used")),
        },
        "explanation": explanation,
    }


def build_time_series_calculation_result(
    *,
    result_value: float,
    result_unit: str,
    rendered_value: str,
    result_series: List[Dict[str, Any]],
    operation_family: str,
    operation: str,
    metric_name: str,
    normalized_unit: str,
    yoy_growth_rates: List[Any],
    formula: str,
    pairwise_formula: str,
    explanation: str,
) -> Dict[str, Any]:
    return {
        "status": "ok",
        "result_value": result_value,
        "result_unit": result_unit,
        "rendered_value": rendered_value,
        "formatted_result": "",
        "series": list(result_series),
        "answer_slots": {
            "operation_family": operation_family or operation,
            "metric_label": metric_name,
            "primary_value": build_calculated_value_slot(
                label=metric_name,
                normalized_value=result_value,
                normalized_unit=normalized_unit,
                display_unit=result_unit,
                role="primary_value",
            ),
        },
        "derived_metrics": {
            "metric_name": metric_name,
            "yoy_growth_rates": list(yoy_growth_rates),
            "formula": formula,
            "pairwise_formula": pairwise_formula,
        },
        "explanation": explanation,
    }


def time_series_yoy_growth_rates(
    *,
    ordered_operands: List[Dict[str, Any]],
    pairwise_formula: str,
) -> List[Any]:
    yoy_growth_rates: List[Any] = [None]
    if not pairwise_formula:
        return yoy_growth_rates
    for previous_row, current_row in zip(ordered_operands, ordered_operands[1:]):
        prev_value = float(previous_row.get("normalized_value"))
        curr_value = float(current_row.get("normalized_value"))
        try:
            yoy_growth_rates.append(
                _safe_eval_formula(pairwise_formula, {"PREV": prev_value, "CURR": curr_value})
            )
        except ZeroDivisionError:
            yoy_growth_rates.append(None)
    return yoy_growth_rates
