"""
Answer projection helpers for aggregate/narrative runtime results.

This module keeps final-answer repair decisions separate from graph orchestration
and trace construction. The rules here are intentionally generic: compare answer
shape, numeric surface consistency, and subtask status without using company,
question, or metric-specific branches.
"""

import re
from typing import Any, Dict, List, Mapping, Sequence


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


def _preferred_complete_aggregate_subtask_answer(
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
