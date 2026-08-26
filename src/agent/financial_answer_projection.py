"""
Answer projection helpers for aggregate/narrative runtime results.

This module keeps final-answer repair decisions separate from graph orchestration
and trace construction. The rules here are intentionally generic: compare answer
shape, numeric surface consistency, and subtask status without using company,
question, or metric-specific branches.
"""

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.agent import financial_graph_calculation_rendering as calculation_rendering
from src.agent.financial_answer_slots import (
    answer_slot_has_material,
    answer_slot_period_hint,
    period_match_key,
)
from src.agent.financial_numeric_surface import evidence_numeric_display_candidates
from src.agent.financial_runtime_normalization import _normalise_spaces
from src.agent.financial_text_surface import split_narrative_sentences
from src.config.retrieval_policy import (
    CALCULATION_FEEDBACK_POLICY,
    CALCULATION_NARRATIVE_POLICY,
    CALCULATION_RENDER_POLICY,
)


def query_requests_explanatory_context(query: str) -> bool:
    text = _normalise_spaces(str(query or "")).lower()
    if not text:
        return False
    explanatory_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("explanatory_markers") or ()))
    return any(marker in text for marker in explanatory_markers)


def sentence_has_growth_explanatory_signal(sentence: str) -> bool:
    text = _normalise_spaces(str(sentence or ""))
    if not text:
        return False
    direction_words = {
        _normalise_spaces(str(value))
        for value in (CALCULATION_NARRATIVE_POLICY.get("direction_words") or {}).values()
        if _normalise_spaces(str(value))
    }
    markers = tuple(
        marker
        for marker in (
            str(item)
            for item in (
                tuple(CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ())
                + tuple(CALCULATION_NARRATIVE_POLICY.get("growth_impact_markers") or ())
                + tuple(CALCULATION_NARRATIVE_POLICY.get("explanatory_markers") or ())
            )
        )
        if marker and marker not in direction_words
    )
    return any(marker in text for marker in markers)


def answer_looks_truncated(answer: str) -> bool:
    answer_text = _normalise_spaces(str(answer or ""))
    if not answer_text:
        return True
    if re.search(r"(?:다|니다|요|음|임)[.!?。]?$", answer_text):
        return False
    if re.search(r"[.!?。]$", answer_text):
        return False
    return True


def answer_covers_narrative_context(answer: str, context: str) -> bool:
    answer_text = _normalise_spaces(str(answer or "")).lower()
    context_text = _normalise_spaces(str(context or ""))
    if not context_text:
        return True
    if context_text.lower() in answer_text:
        return True
    sentences = split_narrative_sentences(context_text)
    for sentence in sentences:
        sentence_text = sentence.lower()
        if sentence_text in answer_text:
            continue
        tokens = [
            token.lower()
            for token in re.findall(r"[\w()]+", sentence, flags=re.UNICODE)
            if len(token) >= 3 and not re.fullmatch(r"\d+(?:\.\d+)?", token)
        ]
        if not tokens:
            return False
        covered = sum(1 for token in tokens if token in answer_text)
        if covered / max(len(tokens), 1) < 0.75:
            return False
    return True


def growth_uses_source_stated_result(row: Dict[str, Any]) -> bool:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    current_slot = dict(answer_slots.get("current_value") or {})
    if dict(calculation_result.get("derived_metrics") or {}).get("source_stated_result_used"):
        return True
    if _normalise_spaces(str(current_slot.get("stated_change_raw_value") or "")):
        return True
    operands = list(row.get("calculation_operands") or calculation_result.get("calculation_operands") or [])
    return any(
        str(operand.get("matched_operand_role") or operand.get("role") or "").strip() == "current_period"
        and _normalise_spaces(str(operand.get("stated_change_raw_value") or ""))
        for operand in operands
        if isinstance(operand, dict)
    )


def growth_sentence_has_untraced_material_numeric(
    sentence: str,
    complete_answer: str,
    required_values: List[str],
    evidence_items: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    cleaned = _normalise_spaces(str(sentence or ""))
    if not cleaned:
        return False
    evidence_surface = _normalise_spaces(
        " ".join(
            str(value or "")
            for item in (evidence_items or [])
            if isinstance(item, dict)
            for metadata in [dict(item.get("metadata") or {})]
            for value in [
                *(item.get(key) for key in ("claim", "quote_span", "raw_row_text", "source_context")),
                *(
                    metadata.get(key)
                    for key in (
                        "table_value_labels_text",
                        "table_summary_text",
                        "table_header_context",
                        "table_context",
                    )
                ),
            ]
        )
    )
    evidence_display_surface = _normalise_spaces(
        " ".join(
            str(candidate.get("text") or "")
            for candidate in evidence_numeric_display_candidates(evidence_items or [], evidence_surface)
            if str(candidate.get("text") or "").strip()
        )
    )
    allowed_surface = _normalise_spaces(
        " ".join([str(complete_answer or ""), *required_values, evidence_surface, evidence_display_surface])
    )
    if not allowed_surface:
        return False
    percent_pattern = str(CALCULATION_NARRATIVE_POLICY.get("percent_display_pattern") or "")
    if percent_pattern:
        for match in re.finditer(percent_pattern, cleaned):
            token = _normalise_spaces(match.group(0))
            if token and token not in allowed_surface:
                return True
    render_policy = dict(CALCULATION_RENDER_POLICY)
    unit_terms = [
        _normalise_spaces(str(unit))
        for unit in (render_policy.get("krw_display_units") or ())
        if _normalise_spaces(str(unit))
    ]
    for unit in unit_terms:
        pattern = rf"\d[\d,]*(?:\.\d+)?\s*{re.escape(unit)}"
        for match in re.finditer(pattern, cleaned):
            token = _normalise_spaces(match.group(0))
            if token and token not in allowed_surface:
                return True
    return False


def growth_answer_has_untraced_numeric_sentence(
    answer: str,
    complete_answer: str,
    required_values: List[str],
) -> bool:
    answer_text = _normalise_spaces(str(answer or ""))
    complete_text = _normalise_spaces(str(complete_answer or ""))
    allowed_surface = _normalise_spaces(" ".join([complete_text, *required_values]))
    if not answer_text or not allowed_surface:
        return False
    number_pattern = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
    for sentence in split_narrative_sentences(answer_text):
        cleaned = _normalise_spaces(sentence)
        if not cleaned or cleaned in complete_text:
            continue
        if not any(value and value in cleaned for value in required_values):
            continue
        numeric_tokens = [match.group(0) for match in number_pattern.finditer(cleaned)]
        if any(token and token not in allowed_surface for token in numeric_tokens):
            return True
    return False


def growth_row_has_conflicting_periods(row: Dict[str, Any]) -> bool:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    current_slot = dict(answer_slots.get("current_value") or {})
    prior_slot = dict(answer_slots.get("prior_value") or {})
    current_period = period_match_key(
        answer_slot_period_hint(current_slot) or str(calculation_result.get("current_period") or "")
    )
    prior_period = period_match_key(
        answer_slot_period_hint(prior_slot) or str(calculation_result.get("prior_period") or "")
    )
    if not (current_period and prior_period and current_period == prior_period):
        return False
    row_text = _normalise_spaces(
        " ".join(
            str(row.get(key) or "")
            for key in ("answer", "formatted_result", "rendered_value")
        )
    )
    result_text = _normalise_spaces(
        " ".join(
            str(calculation_result.get(key) or "")
            for key in ("formatted_result", "rendered_value")
        )
    )
    mentioned_periods = set(re.findall(r"20\d{2}", f"{row_text} {result_text}"))
    return len(mentioned_periods) < 2


def material_gap_feedback_for_subtask_result(row: Dict[str, Any]) -> str:
    feedback_policy = dict(CALCULATION_FEEDBACK_POLICY)
    metric_label = _normalise_spaces(
        str(
            row.get("metric_label")
            or row.get("answer")
            or row.get("task_id")
            or feedback_policy.get("default_metric_label")
            or ""
        )
    )
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    status = str(
        row.get("status")
        or calculation_result.get("status")
        or ""
    ).strip().lower()
    rendered_material = _normalise_spaces(
        str(
            calculation_result.get("formatted_result")
            or calculation_result.get("rendered_value")
            or row.get("answer")
            or ""
        )
    )
    operation_family = str(
        answer_slots.get("operation_family")
        or ((row.get("calculation_plan") or {}).get("operation_family"))
        or ((calculation_result.get("derived_metrics") or {}).get("operation_family"))
        or ""
    ).strip().lower()
    if not operation_family:
        operation_family = str((row.get("calculation_plan") or {}).get("operation") or "").strip().lower()
    if not operation_family:
        metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
        if metric_family.startswith("concept_"):
            operation_family = metric_family.removeprefix("concept_")

    if operation_family == "aggregate_subtasks":
        nested_results = list(
            answer_slots.get("subtask_results")
            or calculation_result.get("subtask_results")
            or []
        )
        for nested_row in reversed(nested_results):
            nested_metric_label = _normalise_spaces(
                str(
                    nested_row.get("metric_label")
                    or nested_row.get("task_id")
                    or ""
                )
            )
            if metric_label and nested_metric_label and nested_metric_label != metric_label:
                continue
            if not material_gap_feedback_for_subtask_result(dict(nested_row)):
                return ""

    if operation_family in {"lookup", "single_value"}:
        if not answer_slot_has_material(dict(answer_slots.get("primary_value") or {})):
            return str(feedback_policy.get("lookup_missing_template") or "").format(metric_label=metric_label)
        return ""

    if operation_family in {"difference", "growth_rate"}:
        current_slot = dict(answer_slots.get("current_value") or {})
        prior_slot = dict(answer_slots.get("prior_value") or {})
        primary_slot = dict(answer_slots.get("primary_value") or {})
        if operation_family == "difference" and not calculation_rendering.difference_slots_are_period_delta(
            answer_slots
        ):
            if answer_slot_has_material(primary_slot):
                return ""
            return str(feedback_policy.get("missing_result_template") or "").format(metric_label=metric_label)
        if operation_family == "growth_rate" and growth_row_has_conflicting_periods(row):
            return str(feedback_policy.get("generic_missing_material_template") or "").format(
                metric_label=metric_label
            )
        missing_labels: List[str] = []
        if not answer_slot_has_material(current_slot):
            period = str(
                current_slot.get("period")
                or calculation_result.get("current_period")
                or feedback_policy.get("default_current_period")
                or ""
            )
            missing_labels.append(
                str(feedback_policy.get("missing_period_value_template") or "").format(period=period)
            )
        if not answer_slot_has_material(prior_slot):
            period = str(
                prior_slot.get("period")
                or calculation_result.get("prior_period")
                or feedback_policy.get("default_prior_period")
                or ""
            )
            missing_labels.append(
                str(feedback_policy.get("missing_period_value_template") or "").format(period=period)
            )
        if operation_family == "difference":
            if not answer_slot_has_material(dict(answer_slots.get("delta_value") or primary_slot)):
                missing_labels.append(str(feedback_policy.get("difference_missing_result_label") or ""))
        else:
            if not answer_slot_has_material(primary_slot):
                if not (status == "ok" and rendered_material and re.search(r"\d", rendered_material)):
                    missing_labels.append(str(feedback_policy.get("growth_missing_result_label") or ""))
        if missing_labels:
            return str(feedback_policy.get("missing_material_template") or "").format(
                metric_label=metric_label,
                missing_labels=str(feedback_policy.get("missing_material_joiner") or "").join(missing_labels),
            )
        return ""

    if operation_family in {"ratio", "sum"}:
        if not answer_slot_has_material(dict(answer_slots.get("primary_value") or {})):
            if status == "ok" and rendered_material and re.search(r"\d", rendered_material):
                return ""
            return str(feedback_policy.get("missing_result_template") or "").format(metric_label=metric_label)
        return ""

    return ""


def subtask_row_has_material(row: Dict[str, Any]) -> bool:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    for slot_name in ("primary_value", "current_value", "prior_value", "delta_value"):
        if answer_slot_has_material(dict(answer_slots.get(slot_name) or {})):
            return True
    if str(calculation_result.get("rendered_value") or row.get("answer") or "").strip():
        return True
    return bool(list(calculation_result.get("source_row_ids") or []))


def nested_subtask_rows(calculation_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    def _walk(current: Dict[str, Any]) -> None:
        answer_slots = dict(current.get("answer_slots") or {})
        nested_children = [
            *list(current.get("subtask_results") or []),
            *list(answer_slots.get("subtask_results") or []),
        ]
        for child in nested_children:
            if not isinstance(child, dict):
                continue
            child_row = dict(child)
            rows.append(child_row)
            child_result = dict(child_row.get("calculation_result") or {})
            if child_result:
                _walk(child_result)

    _walk(dict(calculation_result or {}))
    return rows


def _subtask_row_operation_family(row: Dict[str, Any]) -> str:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    operation_family = _normalise_spaces(
        str(
            row.get("operation_family")
            or answer_slots.get("operation_family")
            or calculation_result.get("operation_family")
            or ""
        )
    ).lower()
    if operation_family:
        return operation_family
    if calculation_result.get("subtask_results"):
        return "aggregate_subtasks"
    metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
    if metric_family.startswith("concept_"):
        return metric_family.removeprefix("concept_")
    return ""


def _subtask_row_specificity_score(
    row: Dict[str, Any],
    *,
    active_subtask: Dict[str, Any],
) -> tuple[int, int, int, int, int, int]:
    active_task_id = _normalise_spaces(str(active_subtask.get("task_id") or ""))
    active_metric_family = _normalise_spaces(str(active_subtask.get("metric_family") or "")).lower()
    active_metric_label = _normalise_spaces(str(active_subtask.get("metric_label") or ""))
    active_operation = _normalise_spaces(str(active_subtask.get("operation_family") or "")).lower()

    task_id = _normalise_spaces(str(row.get("task_id") or ""))
    metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
    metric_label = _normalise_spaces(str(row.get("metric_label") or ""))
    operation_family = _subtask_row_operation_family(row)
    status = _normalise_spaces(
        str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
    ).lower()

    if active_task_id and task_id and active_task_id != task_id:
        return (0, 0, 0, 0, 0, 0)

    status_rank = {"ok": 4, "partial": 2, "ready": 2}.get(status, 0)
    material_rank = 1 if subtask_row_has_material(row) else 0
    operation_rank = 1 if active_operation and operation_family == active_operation else 0
    non_aggregate_rank = 0 if operation_family == "aggregate_subtasks" else 1
    family_rank = 1 if active_metric_family and metric_family == active_metric_family else 0
    label_rank = 0
    if active_metric_label and metric_label:
        if active_metric_label == metric_label:
            label_rank = 3
        elif active_metric_label in metric_label or metric_label in active_metric_label:
            label_rank = 2
        else:
            active_tokens = {token for token in re.split(r"\s+", active_metric_label) if token}
            row_tokens = {token for token in re.split(r"\s+", metric_label) if token}
            label_rank = 1 if active_tokens & row_tokens else 0
    return (status_rank, material_rank, non_aggregate_rank, operation_rank, family_rank, label_rank)


def promote_nested_subtask_result_if_more_specific(
    *,
    active_subtask: Dict[str, Any],
    answer: str,
    status: str,
    calculation_result: Dict[str, Any],
) -> tuple[str, str, Dict[str, Any]]:
    active_operation = _normalise_spaces(str(active_subtask.get("operation_family") or "")).lower()
    if not active_operation or active_operation == "aggregate_subtasks":
        return answer, status, calculation_result
    if not calculation_result.get("subtask_results"):
        return answer, status, calculation_result

    candidates = []
    for row in nested_subtask_rows(calculation_result):
        score = _subtask_row_specificity_score(row, active_subtask=active_subtask)
        if score[:2] == (0, 0):
            continue
        candidates.append((score, row))
    if not candidates:
        return answer, status, calculation_result

    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_row = candidates[0]
    current_material = subtask_row_has_material(
        {
            "answer": answer,
            "status": status,
            "metric_family": active_subtask.get("metric_family"),
            "metric_label": active_subtask.get("metric_label"),
            "operation_family": active_operation,
            "calculation_result": calculation_result,
        }
    )
    if current_material and best_score[0] < 4:
        return answer, status, calculation_result

    best_result = dict(best_row.get("calculation_result") or {})
    if not best_result or _subtask_row_operation_family(best_row) == "aggregate_subtasks":
        return answer, status, calculation_result
    promoted_answer = _normalise_spaces(
        str(
            best_row.get("answer")
            or best_result.get("formatted_result")
            or best_result.get("rendered_value")
            or answer
        )
    )
    promoted_status = str(best_row.get("status") or best_result.get("status") or status)
    return promoted_answer, promoted_status, best_result


def _normalise_projection_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _split_projection_sentences(text: str) -> List[str]:
    cleaned = _normalise_projection_spaces(text)
    if not cleaned:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|(?<=\uB2E4)\s+", cleaned) if part.strip()]


def _trace_operation_family_for_projection(
    *,
    calculation_plan: Mapping[str, Any],
    calculation_result: Mapping[str, Any],
) -> str:
    result_slots = dict(calculation_result.get("answer_slots") or {})
    return _normalise_projection_spaces(
        str(
            calculation_result.get("operation_family")
            or result_slots.get("operation_family")
            or calculation_plan.get("operation")
            or calculation_plan.get("operation_family")
            or calculation_plan.get("mode")
            or ""
        )
    ).lower()


def _numeric_surface_candidates_for_projection(text: str) -> List[Dict[str, Any]]:
    from src.agent.financial_numeric_surface import extract_numeric_surface_candidates

    return [
        dict(candidate)
        for candidate in extract_numeric_surface_candidates(str(text or ""))
        if str(candidate.get("kind") or "") in {"currency", "percent", "generic"}
    ]


def _numeric_surface_has_equivalent(
    candidate: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> bool:
    from src.agent.financial_numeric_surface import numeric_surface_candidates_equivalent

    return any(numeric_surface_candidates_equivalent(dict(candidate), dict(other)) for other in candidates)


def _candidate_reduces_conflicting_numeric_surfaces(answer_text: str, candidate: str) -> bool:
    answer_numbers = _numeric_surface_candidates_for_projection(answer_text)
    candidate_numbers = _numeric_surface_candidates_for_projection(candidate)
    if len(answer_numbers) < 2 or len(candidate_numbers) < 2:
        return False
    shared_candidate_numbers = [
        item
        for item in candidate_numbers
        if _numeric_surface_has_equivalent(item, answer_numbers)
    ]
    if len(shared_candidate_numbers) < 2:
        return False
    answer_only_numbers = [
        item
        for item in answer_numbers
        if not _numeric_surface_has_equivalent(item, candidate_numbers)
    ]
    candidate_only_numbers = [
        item
        for item in candidate_numbers
        if not _numeric_surface_has_equivalent(item, answer_numbers)
    ]
    if not answer_only_numbers or len(answer_only_numbers) <= len(candidate_only_numbers):
        return False
    return len(candidate) >= max(40, int(len(answer_text) * 0.35))


def preferred_complete_aggregate_subtask_answer(
    subtask_results: List[Dict[str, Any]],
    final_answer: str,
) -> str:
    answer_text = _normalise_projection_spaces(str(final_answer or ""))
    if not answer_text:
        return ""
    best_answer = ""
    for row in list(subtask_results or []):
        if not isinstance(row, Mapping):
            continue
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        operation_family = _trace_operation_family_for_projection(
            calculation_plan=dict(row.get("calculation_plan") or {}),
            calculation_result=calculation_result,
        ) or str(answer_slots.get("operation_family") or row.get("operation_family") or "").strip().lower()
        metric_family = _normalise_projection_spaces(str(row.get("metric_family") or "")).lower()
        if operation_family not in {"aggregate_subtasks", "narrative_summary"} and metric_family != "narrative_summary":
            continue
        status = _normalise_projection_spaces(
            str(row.get("status") or calculation_result.get("status") or "")
        ).lower()
        if status and status not in {"ok", "ready"}:
            continue
        candidate = _normalise_projection_spaces(
            str(
                row.get("answer")
                or calculation_result.get("formatted_result")
                or calculation_result.get("rendered_value")
                or ""
            )
        )
        if not candidate or candidate == answer_text or answer_text not in candidate:
            if candidate and candidate != answer_text and candidate in answer_text and re.search(r"\d", candidate):
                prefix = answer_text.split(candidate, 1)[0]
                if prefix and re.search(r"\d", prefix):
                    if not best_answer or len(candidate) > len(best_answer):
                        best_answer = candidate
                continue
            if (
                candidate
                and candidate != answer_text
                and re.search(r"\d", candidate)
                and _candidate_reduces_conflicting_numeric_surfaces(answer_text, candidate)
            ):
                if not best_answer or len(candidate) > len(best_answer):
                    best_answer = candidate
                continue
            continue
        suffix = candidate.split(answer_text, 1)[1]
        narrative_parts: List[str] = []
        for sentence in _split_projection_sentences(suffix):
            cleaned_sentence = re.sub(r"^[\s,;:\-.]+", "", _normalise_projection_spaces(sentence))
            if not cleaned_sentence or re.search(r"\d", cleaned_sentence):
                continue
            narrative_parts.append(cleaned_sentence)
        if not narrative_parts:
            continue
        completed_answer = _normalise_projection_spaces(" ".join([answer_text, *narrative_parts]))
        if not best_answer or len(completed_answer) > len(best_answer):
            best_answer = completed_answer
    return best_answer
