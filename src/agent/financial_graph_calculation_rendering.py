"""Presentation helpers for calculation results.

The calculation mixin keeps the public method surface for compatibility; this
module holds the behavior-neutral rendering logic behind those methods.
"""

import re
from typing import Any, Callable, Dict, List, Optional

from src.agent.financial_graph_helpers import (
    _clean_source_row_ids,
    _desired_consolidation_scope,
    _display_operand_label,
    _format_korean_won_compact,
    _normalise_spaces,
)
from src.config.retrieval_policy import CALCULATION_RENDER_POLICY


def direction_hint_for_result(
    *,
    operation: str,
    result_value: float,
    render_policy: Optional[Dict[str, Any]] = None,
) -> str:
    policy = dict(render_policy or CALCULATION_RENDER_POLICY)
    direction_policy = dict((policy.get("direction_hints") or {}).get(str(operation or "")) or {})
    if not direction_policy:
        return ""
    if result_value > 0:
        return str(direction_policy.get("positive") or "")
    if result_value < 0:
        return str(direction_policy.get("negative") or "")
    return str(direction_policy.get("zero") or "")


def coerce_rendered_value_for_direction(
    calculation_result: Dict[str, Any],
    *,
    direction_hint: str,
    result_value: float,
) -> Dict[str, Any]:
    updated = dict(calculation_result or {})
    if direction_hint and result_value < 0:
        rendered_value = str(updated.get("rendered_value") or "")
        updated["rendered_value"] = rendered_value.lstrip("-")
    return updated


def format_calculation_value(value: float, result_unit: str, normalized_unit: str) -> str:
    if normalized_unit == "KRW":
        return _format_korean_won_compact(value)
    normalized_upper = str(normalized_unit or "").upper()
    percent_normalized_units = {
        str(item).upper()
        for item in (CALCULATION_RENDER_POLICY.get("count_or_percent_normalized_units") or ())
        if str(item).upper() != "COUNT"
    }
    if normalized_upper in percent_normalized_units:
        if str(result_unit or "").strip() == "%p":
            return f"{value:.2f}"
        if value and abs(value) < 0.01:
            return f"{value:.4f}".rstrip("0").rstrip(".")
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if normalized_unit in {"COUNT", "USD"}:
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    return f"{value}"


def format_ratio_percent_result(result_value: float) -> str:
    rendered_value = format_calculation_value(result_value, "%", "PERCENT")
    return rendered_value if "%" in rendered_value else f"{result_value:.2f}".rstrip("0").rstrip(".") + "%"


def format_calculation_value_in_display_unit(value: float, display_unit: str) -> str:
    unit = _normalise_spaces(str(display_unit or ""))
    scale_by_unit = dict(CALCULATION_RENDER_POLICY.get("krw_display_unit_scales") or {})
    scale = scale_by_unit.get(unit)
    if not scale:
        return ""
    scaled = float(value) / scale
    if abs(scaled - round(scaled)) <= 1e-6:
        rendered = f"{round(scaled):,}"
    else:
        rendered = f"{scaled:,.4f}".rstrip("0").rstrip(".")
    return f"{rendered}{unit}"


def adjusted_difference_source_display_unit(
    *,
    active_subtask: Dict[str, Any],
    ordered_operands: List[Dict[str, Any]],
) -> str:
    raw_units = [
        _normalise_spaces(str(row.get("raw_unit") or row.get("result_unit") or ""))
        for row in ordered_operands
        if str(row.get("raw_unit") or row.get("result_unit") or "").strip()
    ]
    if not raw_units or len(raw_units) != len(ordered_operands):
        return ""
    source_display_units = {
        str(item)
        for item in (CALCULATION_RENDER_POLICY.get("source_display_units") or ())
        if str(item)
    }
    converted_display_units = {
        str(item)
        for item in (CALCULATION_RENDER_POLICY.get("converted_display_units") or ())
        if str(item)
    }
    dependency_bound = any(
        bool(row.get("dependency_resolved"))
        or any(
            str(source_id).startswith("task_output:")
            for source_id in _clean_source_row_ids([
                row.get("source_row_id"),
                row.get("source_row_ids"),
            ])
        )
        for row in ordered_operands
    )
    if dependency_bound and len(set(raw_units)) == 1 and raw_units[0] in source_display_units:
        return raw_units[0]
    query_text = _normalise_spaces(
        " ".join(
            str(active_subtask.get(key) or "")
            for key in ("query", "metric_label", "operation_text", "task_id")
        )
    )
    query_terms = tuple(str(item) for item in (CALCULATION_RENDER_POLICY.get("adjusted_difference_query_terms") or ()))
    exclusion_pattern = str(CALCULATION_RENDER_POLICY.get("adjusted_difference_exclusion_pattern") or r"$^")
    if not (
        any(marker in query_text for marker in query_terms)
        or re.search(exclusion_pattern, query_text)
    ):
        return ""
    if len(set(raw_units)) == 1 and raw_units[0] in source_display_units:
        return raw_units[0]
    source_units = [unit for unit in raw_units if unit in source_display_units]
    if len(set(source_units)) == 1 and any(unit in converted_display_units for unit in raw_units):
        return source_units[0]
    return ""


def render_value_with_unit(value: float, display_unit: str, normalized_unit: str) -> str:
    rendered = format_calculation_value(value, display_unit, normalized_unit)
    if normalized_unit == "KRW":
        return rendered
    normalized_upper = str(normalized_unit or "").upper()
    percent_normalized_units = {
        str(item).upper()
        for item in (CALCULATION_RENDER_POLICY.get("count_or_percent_normalized_units") or ())
        if str(item).upper() != "COUNT"
    }
    if normalized_upper in percent_normalized_units:
        return f"{rendered}{display_unit or '%'}"
    if display_unit:
        return f"{rendered}{display_unit}"
    return rendered


def scalar_result_display(
    *,
    result_value: float,
    result_unit: str,
    normalized_unit: str,
    result_display_unit: str = "",
    operation_family: str = "",
    ordered_operands: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, str]:
    if result_display_unit:
        rendered_value = format_calculation_value_in_display_unit(result_value, result_display_unit)
    else:
        rendered_value = format_calculation_value(result_value, result_unit or "", normalized_unit)
    if normalized_unit == "KRW":
        rendered_with_unit = rendered_value
    elif result_unit:
        rendered_with_unit = f"{rendered_value}{result_unit}"
    else:
        rendered_with_unit = rendered_value
    if operation_family in {"lookup", "single_value"} and ordered_operands:
        grounded_display = render_grounded_operand_display(ordered_operands[0])
        if grounded_display:
            rendered_value = grounded_display
            rendered_with_unit = grounded_display
    return {
        "rendered_value": rendered_value,
        "rendered_with_unit": rendered_with_unit,
        "result_display_unit": result_display_unit,
    }


def scalar_result_series(
    *,
    ordered_operands: List[Dict[str, Any]],
    source_normalized_unit: str,
) -> List[Dict[str, Any]]:
    result_series: List[Dict[str, Any]] = []
    for row in ordered_operands:
        point_value = float(row.get("normalized_value"))
        point_rendered = render_grounded_operand_display(row)
        if not point_rendered:
            point_rendered = format_calculation_value(
                point_value,
                str(row.get("raw_unit") or row.get("result_unit") or ""),
                source_normalized_unit,
            )
        result_series.append(
            {
                "label": _display_operand_label(str(row.get("label") or row.get("evidence_id") or "")),
                "period": str(row.get("period") or ""),
                "raw_value": str(row.get("raw_value") or ""),
                "raw_unit": str(row.get("raw_unit") or ""),
                "normalized_value": point_value,
                "normalized_unit": source_normalized_unit,
                "rendered_value": point_rendered,
            }
        )
    return result_series


def time_series_result_series(
    *,
    ordered_operands: List[Dict[str, Any]],
    normalized_unit: str,
) -> List[Dict[str, Any]]:
    result_series: List[Dict[str, Any]] = []
    for row in ordered_operands:
        point_value = float(row.get("normalized_value"))
        point_rendered = format_calculation_value(
            point_value,
            str(row.get("raw_unit") or row.get("result_unit") or ""),
            normalized_unit,
        )
        result_series.append(
            {
                "label": _display_operand_label(str(row.get("label") or row.get("evidence_id") or "")),
                "period": str(row.get("period") or ""),
                "raw_value": str(row.get("raw_value") or ""),
                "raw_unit": str(row.get("raw_unit") or ""),
                "normalized_value": point_value,
                "normalized_unit": normalized_unit,
                "rendered_value": point_rendered,
            }
        )
    return result_series


def time_series_result_display(
    *,
    result_value: float,
    result_unit: str,
    normalized_unit: str,
) -> Dict[str, str]:
    display_normalized_unit = normalized_unit
    if result_unit in {"%", "%p"}:
        display_normalized_unit = "PERCENT"
    percent_normalized_units = {
        str(item).upper()
        for item in (CALCULATION_RENDER_POLICY.get("count_or_percent_normalized_units") or ())
        if str(item).upper() != "COUNT"
    }
    if (display_normalized_unit or "").upper() in percent_normalized_units:
        rendered_value = f"{result_value:.1f}%"
    else:
        rendered_value = f"{result_value:,.4f}".rstrip("0").rstrip(".")
    return {
        "normalized_unit": display_normalized_unit,
        "rendered_value": rendered_value,
    }


def render_grounded_operand_display(row: Dict[str, Any]) -> str:
    raw_value = _normalise_spaces(str(row.get("raw_value") or ""))
    raw_unit = _normalise_spaces(str(row.get("raw_unit") or row.get("result_unit") or ""))
    normalized_unit = _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
    count_or_percent_units = {
        str(item).upper()
        for item in (CALCULATION_RENDER_POLICY.get("count_or_percent_normalized_units") or ())
        if str(item)
    }
    krw_normalized_unit = str(CALCULATION_RENDER_POLICY.get("krw_normalized_unit") or "").upper()
    krw_display_units = {
        str(item)
        for item in (CALCULATION_RENDER_POLICY.get("krw_display_units") or ())
        if str(item)
    }
    embedded_unit_markers = tuple(
        str(item)
        for item in (CALCULATION_RENDER_POLICY.get("value_embedded_unit_markers") or ())
        if str(item)
    )
    coerced_display = _normalise_spaces(str(row.get("rendered_value") or ""))
    if row.get("value_coercion") and coerced_display:
        return coerced_display
    if normalized_unit in count_or_percent_units and raw_value:
        if raw_unit and raw_unit in raw_value:
            return raw_value
        return f"{raw_value}{raw_unit}" if raw_unit else raw_value
    if normalized_unit != krw_normalized_unit or not raw_value or not raw_unit:
        return ""
    if raw_unit not in krw_display_units:
        return ""
    if any(token in raw_value for token in embedded_unit_markers):
        return raw_value
    return f"{raw_value}{raw_unit}"


def absolute_display_value(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("-"):
        return text[1:].strip()
    if text.startswith("(") and text.endswith(")"):
        return text[1:-1].strip()
    parenthesized_numeric = re.match(r"^\((?P<number>\d[\d,]*(?:\.\d+)?)\)(?P<suffix>\s*\S.*)?$", text)
    if parenthesized_numeric:
        return _normalise_spaces(
            f"{parenthesized_numeric.group('number')}{parenthesized_numeric.group('suffix') or ''}"
        )
    return text


def collect_negative_subtrahend_slots(
    *,
    calculation_result: Optional[Dict[str, Any]] = None,
    subtask_results: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    def _push_from_answer_slots(answer_slots: Dict[str, Any]) -> None:
        components = dict(answer_slots.get("components_by_role") or {})
        operation_family = _normalise_spaces(str(answer_slots.get("operation_family") or ""))
        right_hand_roles = ["subtrahend"]
        if operation_family == "difference":
            right_hand_roles.append("denominator")
        for role in right_hand_roles:
            for slot in list(components.get(role) or []):
                rendered = str(slot.get("rendered_value") or "").strip()
                positive = absolute_display_value(rendered)
                if not rendered or rendered == positive:
                    continue
                rows.append(
                    {
                        "label": _display_operand_label(str(slot.get("label") or "")),
                        "negative": rendered,
                        "positive": positive,
                    }
                )

    if calculation_result:
        _push_from_answer_slots(dict((calculation_result or {}).get("answer_slots") or {}))
    for row in list(subtask_results or []):
        _push_from_answer_slots(dict(row.get("answer_slots") or {}))
        _push_from_answer_slots(dict((row.get("calculation_result") or {}).get("answer_slots") or {}))
    return rows


def coerce_sign_aware_subtraction_answer(
    answer: str,
    *,
    calculation_result: Optional[Dict[str, Any]] = None,
    subtask_results: Optional[List[Dict[str, Any]]] = None,
) -> str:
    rewritten = str(answer or "")
    for row in collect_negative_subtrahend_slots(
        calculation_result=calculation_result,
        subtask_results=subtask_results,
    ):
        label = str(row.get("label") or "").strip()
        negative = str(row.get("negative") or "").strip()
        positive = str(row.get("positive") or "").strip()
        if not negative or not positive or negative == positive:
            continue
        replacements = tuple(CALCULATION_RENDER_POLICY.get("sign_aware_subtraction_replacements") or ())
        for source_template, target_template in replacements:
            source = str(source_template or "").format(label=label, negative=negative, positive=positive)
            target = str(target_template or "").format(label=label, negative=negative, positive=positive)
            rewritten = rewritten.replace(source, target)
    return _normalise_spaces(rewritten)


def first_material_slot_for_role(
    answer_slots: Dict[str, Any],
    role: str,
    *,
    answer_slot_has_material: Callable[[Dict[str, Any]], bool],
) -> Dict[str, Any]:
    components_by_role = dict(answer_slots.get("components_by_role") or {})
    for slot in list(components_by_role.get(role) or []):
        slot_row = dict(slot or {})
        if answer_slot_has_material(slot_row):
            return slot_row
    fallback_key = {
        "minuend": "current_value",
        "subtrahend": "prior_value",
    }.get(role, "")
    if fallback_key:
        fallback = dict(answer_slots.get(fallback_key) or {})
        if answer_slot_has_material(fallback):
            return fallback
    return {}


def infer_company_from_answer_slots(answer_slots: Dict[str, Any]) -> str:
    candidate_slots: List[Dict[str, Any]] = []
    for slots in dict(answer_slots.get("components_by_role") or {}).values():
        candidate_slots.extend(dict(slot or {}) for slot in list(slots or []))
    for key in ("primary_value", "current_value", "prior_value", "delta_value"):
        candidate_slots.append(dict(answer_slots.get(key) or {}))

    for slot in candidate_slots:
        source_anchor = _normalise_spaces(str(slot.get("source_anchor") or ""))
        match = re.match(r"^\[\s*([^|\]]+?)\s*\|", source_anchor)
        if match:
            company = _normalise_spaces(match.group(1))
            if company and company != "?":
                return company
    return ""


def compose_slot_based_difference_answer(
    *,
    query: str,
    report_scope: Dict[str, Any],
    calculation_result: Dict[str, Any],
    answer_slot_has_material: Callable[[Dict[str, Any]], bool],
) -> str:
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    operation_family = _normalise_spaces(
        str(answer_slots.get("operation_family") or calculation_result.get("operation_family") or "")
    ).lower()
    if operation_family != "difference":
        subtask_rows = list(answer_slots.get("subtask_results") or calculation_result.get("subtask_results") or [])
        for row in subtask_rows:
            row_payload = dict(row or {})
            row_result = dict(row_payload.get("calculation_result") or {})
            row_slots = dict(row_result.get("answer_slots") or row_payload.get("answer_slots") or {})
            row_family = _normalise_spaces(
                str(row_slots.get("operation_family") or row_payload.get("operation_family") or "")
            ).lower()
            if row_family != "difference":
                continue
            candidate = dict(row_result)
            candidate["answer_slots"] = row_slots
            if not candidate.get("rendered_value"):
                candidate["rendered_value"] = row_payload.get("rendered_value") or row_payload.get("answer")
            answer = compose_slot_based_difference_answer(
                query=query,
                report_scope=report_scope,
                calculation_result=candidate,
                answer_slot_has_material=answer_slot_has_material,
            )
            if answer:
                return answer
        return ""

    minuend = first_material_slot_for_role(
        answer_slots,
        "minuend",
        answer_slot_has_material=answer_slot_has_material,
    )
    subtrahend = first_material_slot_for_role(
        answer_slots,
        "subtrahend",
        answer_slot_has_material=answer_slot_has_material,
    )
    result_slot = dict(answer_slots.get("primary_value") or answer_slots.get("delta_value") or {})
    if not all(answer_slot_has_material(slot) for slot in (minuend, subtrahend, result_slot)):
        return ""

    minuend_value = _normalise_spaces(str(minuend.get("rendered_value") or ""))
    subtrahend_value = _normalise_spaces(str(subtrahend.get("rendered_value") or ""))
    result_value = _normalise_spaces(str(result_slot.get("rendered_value") or calculation_result.get("rendered_value") or ""))
    if not (minuend_value and subtrahend_value and result_value):
        return ""

    company = _normalise_spaces(str((report_scope or {}).get("company") or ""))
    if not company:
        company = infer_company_from_answer_slots(answer_slots)
    period = _normalise_spaces(
        str(result_slot.get("period") or minuend.get("period") or subtrahend.get("period") or "")
    )
    scope = _desired_consolidation_scope(query, report_scope or {})
    scope_text = dict(CALCULATION_RENDER_POLICY.get("scope_labels") or {}).get(scope, "")
    period_prefix_template = str(CALCULATION_RENDER_POLICY.get("ratio_period_prefix_template") or "{period} ")
    period_suffix = period_prefix_template.replace("{period}", "").strip()
    period_text = (
        period_prefix_template.format(period=period).strip()
        if period and period_suffix and not period.endswith(period_suffix)
        else period
    )
    prefix_parts = [part for part in (company, period_text, scope_text) if part]
    prefix = " ".join(dict.fromkeys(prefix_parts))

    default_labels = dict(CALCULATION_RENDER_POLICY.get("difference_default_labels") or {})
    minuend_label = _normalise_spaces(str(minuend.get("label") or default_labels.get("minuend") or ""))
    subtrahend_label = _normalise_spaces(str(subtrahend.get("label") or default_labels.get("subtrahend") or ""))
    result_label = _normalise_spaces(
        str(result_slot.get("label") or calculation_result.get("metric_label") or default_labels.get("result") or "")
    )

    if prefix:
        first_sentence_template = str(CALCULATION_RENDER_POLICY.get("difference_first_sentence_with_prefix") or "")
        first_sentence = first_sentence_template.format(
            prefix=prefix,
            minuend_label=minuend_label,
            minuend_value=minuend_value,
        )
    else:
        first_sentence_template = str(CALCULATION_RENDER_POLICY.get("difference_first_sentence") or "")
        first_sentence = first_sentence_template.format(
            minuend_label=minuend_label,
            minuend_value=minuend_value,
        )
    return _normalise_spaces(
        str(CALCULATION_RENDER_POLICY.get("difference_answer_template") or "").format(
            first_sentence=first_sentence,
            subtrahend_label=subtrahend_label,
            subtrahend_value=subtrahend_value,
            result_label=result_label,
            result_value=result_value,
        )
    )
