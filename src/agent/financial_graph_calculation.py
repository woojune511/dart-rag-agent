"""
Calculation mixin for the financial graph agent.

This module owns the structured numeric path after reconciliation:
- extract normalized operands
- plan the calculation formula
- execute and verify the numeric result
- advance or aggregate multi-subtask calculations
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from src.agent.financial_graph_helpers import *  # noqa: F401,F403
from src.agent.financial_graph_models import AggregateSynthesisOutput, CalculationPlan, CalculationRenderOutput, CalculationResult, CalculationVerificationOutput, FinancialAgentState, OperandExtraction, validate_answer_slots_payload
from src.agent.financial_graph_planning import _synthesize_lookup_answer_slot_from_prose
from src.config import get_financial_ontology
from src.config.retrieval_policy import (
    CALCULATION_FEEDBACK_POLICY,
    CALCULATION_NARRATIVE_POLICY,
    CALCULATION_PROMPT_POLICY,
    CALCULATION_RENDER_POLICY,
    CALCULATION_SLOT_POLICY,
    CONSOLIDATION_SCOPE_POLICY,
    KOREAN_PERIOD_PREFIX_RE_FRAGMENT,
    NUMERIC_UNIT_NORMALIZATION_POLICY,
    OPERAND_CANDIDATE_SCORING_POLICY,
)
from src.schema import ArtifactKind, TaskKind, TaskStatus

logger = logging.getLogger(__name__)


def _task_artifact_integrity_feedback(trace: Dict[str, Any]) -> str:
    status = _normalise_spaces(str(trace.get("integrity_status") or "")).lower()
    if status != "error":
        return ""
    issue_surfaces: List[str] = []
    for issue in trace.get("integrity_issues") or []:
        if not isinstance(issue, dict):
            continue
        if str(issue.get("severity") or "").strip().lower() != "error":
            continue
        issue_type = str(issue.get("type") or "").strip()
        if not issue_type:
            continue
        detail_parts = [
            str(issue.get("task_id") or "").strip(),
            str(issue.get("artifact_kind") or issue.get("artifact_id") or "").strip(),
            str(issue.get("payload_key") or "").strip(),
        ]
        detail = ":".join(part for part in detail_parts if part)
        issue_surfaces.append(f"{issue_type}:{detail}" if detail else issue_type)
    issue_surface = ", ".join(sorted(set(issue_surfaces))) if issue_surfaces else "unknown_integrity_error"
    return (
        "Task/artifact ledger integrity error prevents final answer closure. "
        f"Repair the required artifact contract before closing: {issue_surface}."
    )


def _topic_particle(value: str) -> str:
    particles = dict(CALCULATION_NARRATIVE_POLICY.get("topic_particles") or {})
    with_final = str(particles.get("with_final_consonant") or "")
    without_final = str(particles.get("without_final_consonant") or "")
    text = _normalise_spaces(str(value or ""))
    if not text:
        return with_final
    last = text[-1]
    codepoint = ord(last)
    if 0xAC00 <= codepoint <= 0xD7A3:
        return with_final if (codepoint - 0xAC00) % 28 else without_final
    return without_final


def _split_narrative_sentences(text: str) -> List[str]:
    surface = _normalise_spaces(str(text or ""))
    if not surface:
        return []
    surface = re.sub(r"(?<=[.!?。])\s*(?=[\-ㆍ•·*]\s*)", " ", surface)
    surface = re.sub(r"(?<=[.!?。])(?=[\uac00-\ud7a3])", " ", surface)
    return [
        _normalise_spaces(fragment)
        for fragment in re.split(r"(?<=[.!?。])\s+|\n+", surface)
        if _normalise_spaces(fragment)
    ]


def _narrative_sentence_looks_table_noisy(sentence: str) -> bool:
    text = _normalise_spaces(str(sentence or ""))
    if not text:
        return True
    pipe_count = text.count("|")
    bullet_count = len(re.findall(r"(?:^|\s)[\-ㆍ•·*]\s*", text))
    bracket_header_count = len(re.findall(r"\[[^\]]+\]", text))
    numeric_count = len(re.findall(r"\d[\d,]*(?:\.\d+)?%?", text))
    if pipe_count >= 3:
        return True
    if len(text) >= 120 and numeric_count >= 6 and (pipe_count or bullet_count or bracket_header_count):
        return True
    if len(text) >= 180 and numeric_count >= 8:
        return True
    return False


def _narrative_sentence_looks_abbreviated_fragment(sentence: str, markers: tuple[str, ...]) -> bool:
    text = _normalise_spaces(str(sentence or ""))
    if not text or any(marker in text for marker in markers):
        return False
    return bool(re.search(r"\b[A-Za-z]{1,4}\.$", text))


class FinancialAgentCalculationMixin:
    def _calculation_operand_source_refs(self, operand_rows: List[Dict[str, Any]]) -> List[str]:
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

    def _enrich_reconciliation_artifact_refs(
        self,
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
                    *self._calculation_operand_source_refs(operand_rows),
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

    def _answer_slot_has_material(self, slot: Dict[str, Any]) -> bool:
        if not isinstance(slot, dict) or not slot:
            return False
        status = str(slot.get("status") or "").strip().lower()
        if status == "missing":
            return False
        if slot.get("normalized_value") is not None:
            return True
        return bool(str(slot.get("rendered_value") or slot.get("raw_value") or "").strip())

    def _slot_metric_keys(self, slot: Dict[str, Any]) -> set[str]:
        keys: set[str] = set()
        concept = _normalise_spaces(str(slot.get("concept") or ""))
        if concept:
            keys.add(concept)
        label = _normalise_spaces(str(slot.get("label") or ""))
        if label:
            slot_policy = dict(CALCULATION_SLOT_POLICY)
            period_pattern = str(slot_policy.get("period_pattern") or "")
            if period_pattern:
                label = re.sub(period_pattern, " ", label)
            for needle in tuple(slot_policy.get("label_drop_terms") or ()):
                label = label.replace(needle, " ")
            for pattern in tuple(slot_policy.get("label_drop_patterns") or ()):
                label = re.sub(str(pattern), " ", label)
            label = label.replace("(", " ").replace(")", " ")
            label = _normalise_spaces(label)
            if label:
                keys.add(label)
                compact_label = label.replace(" ", "")
                if compact_label and compact_label != label:
                    keys.add(compact_label)
        return keys

    def _slot_period_hint(self, slot: Dict[str, Any]) -> str:
        period = _normalise_spaces(str(slot.get("period") or ""))
        if period:
            return period
        label = _normalise_spaces(str(slot.get("label") or ""))
        period_pattern = str(CALCULATION_SLOT_POLICY.get("period_pattern") or "")
        if period_pattern:
            match = re.search(period_pattern, label)
            if match:
                return _normalise_spaces(match.group(0))
        return ""

    def _period_match_key(self, value: str) -> str:
        return re.sub(r"\D", "", _normalise_spaces(str(value or "")))

    def _iter_answer_slots(self, answer_slots: Dict[str, Any]) -> List[Dict[str, Any]]:
        slots: List[Dict[str, Any]] = []
        for key in ("primary_value", "current_value", "prior_value", "delta_value"):
            slot = answer_slots.get(key)
            if isinstance(slot, dict):
                slots.append(dict(slot))

        for group_key in ("components_by_role", "components_by_group"):
            grouped = answer_slots.get(group_key)
            if not isinstance(grouped, dict):
                continue
            for entries in grouped.values():
                if isinstance(entries, list):
                    slots.extend(dict(entry) for entry in entries if isinstance(entry, dict))
                elif isinstance(entries, dict):
                    slots.append(dict(entries))
        return slots

    def _lookup_gap_is_satisfied_by_sibling_slots(
        self,
        row: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        operation_family = self._aggregate_result_operation_family(row)
        metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
        if (not operation_family or operation_family == "aggregate_subtasks") and metric_family.startswith("concept_"):
            operation_family = metric_family.removeprefix("concept_")
        if operation_family not in {"lookup", "single_value"}:
            return False

        target_slot = dict(answer_slots.get("primary_value") or {})
        target_keys = self._slot_metric_keys(target_slot)
        metric_label = _normalise_spaces(str(row.get("metric_label") or row.get("answer") or ""))
        if metric_label:
            target_keys.update(self._slot_metric_keys({"label": metric_label}))
        if not target_keys:
            return False

        target_periods = {
            self._period_match_key(period)
            for period in [
                self._slot_period_hint(target_slot),
                *(
                    match.group(0)
                    for match in re.finditer(str(CALCULATION_SLOT_POLICY.get("period_pattern") or r"$^"), metric_label)
                ),
            ]
            if self._period_match_key(period)
        }

        target_concept = _normalise_spaces(str(target_slot.get("concept") or ""))
        for sibling in ordered_results:
            if sibling is row:
                continue
            sibling_result = dict(sibling.get("calculation_result") or {})
            sibling_slots = dict(sibling_result.get("answer_slots") or sibling.get("answer_slots") or {})
            for sibling_slot in self._iter_answer_slots(sibling_slots):
                if not self._answer_slot_has_material(sibling_slot):
                    continue
                if target_concept:
                    sibling_concept = _normalise_spaces(str(sibling_slot.get("concept") or ""))
                    if sibling_concept and sibling_concept != target_concept:
                        continue
                sibling_period = self._period_match_key(self._slot_period_hint(sibling_slot))
                if target_periods and sibling_period and sibling_period not in target_periods:
                    continue
                if target_periods and not sibling_period:
                    continue
                sibling_keys = self._slot_metric_keys(sibling_slot)
                if target_keys & sibling_keys:
                    return True
                if any(
                    target_key and sibling_key and (target_key in sibling_key or sibling_key in target_key)
                    for target_key in target_keys
                    for sibling_key in sibling_keys
                ):
                    return True
        return False

    def _sibling_lookup_gap_is_satisfied(
        self,
        row: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        operation_family = str(
            answer_slots.get("operation_family")
            or ((row.get("calculation_plan") or {}).get("operation_family"))
            or ((calculation_result.get("derived_metrics") or {}).get("operation_family"))
            or ""
        ).strip().lower()
        if operation_family not in {"difference", "growth_rate"}:
            return False

        current_slot = dict(answer_slots.get("current_value") or {})
        prior_slot = dict(answer_slots.get("prior_value") or {})
        current_material = self._answer_slot_has_material(current_slot)
        prior_material = self._answer_slot_has_material(prior_slot)
        if current_material and prior_material:
            return False

        target_keys = set()
        target_keys.update(self._slot_metric_keys(current_slot))
        target_keys.update(self._slot_metric_keys(prior_slot))
        if not target_keys:
            components = dict(answer_slots.get("components_by_role") or {})
            for role in ("current_period", "prior_period", "minuend", "subtrahend"):
                for slot in list(components.get(role) or []):
                    target_keys.update(self._slot_metric_keys(dict(slot or {})))
        if not target_keys:
            target_keys.add(_normalise_spaces(str(row.get("metric_label") or "")))

        current_period = self._slot_period_hint(current_slot)
        prior_period = self._slot_period_hint(prior_slot)
        sibling_periods: set[str] = set()

        for sibling in ordered_results:
            if sibling is row:
                continue
            sibling_result = dict(sibling.get("calculation_result") or {})
            sibling_slots = dict(sibling_result.get("answer_slots") or {})
            primary_slot = dict(sibling_slots.get("primary_value") or {})
            if not self._answer_slot_has_material(primary_slot):
                continue
            sibling_keys = self._slot_metric_keys(primary_slot)
            if not sibling_keys:
                continue
            if not (target_keys & sibling_keys):
                continue
            period_hint = self._slot_period_hint(primary_slot)
            if period_hint:
                sibling_periods.add(period_hint)

        if not sibling_periods:
            return False
        if not current_material and current_period and current_period in sibling_periods:
            current_material = True
        if not prior_material and prior_period and prior_period in sibling_periods:
            prior_material = True
        if not current_material and sibling_periods:
            current_material = True
        if not prior_material:
            if current_period:
                prior_material = any(period != current_period for period in sibling_periods)
            else:
                prior_material = len(sibling_periods) >= 2
        return current_material and prior_material

    def _narrative_summary_gap_is_satisfied(
        self,
        row: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        operation_family = str(
            row.get("operation_family")
            or answer_slots.get("operation_family")
            or (row.get("calculation_plan") or {}).get("operation")
            or ""
        ).strip().lower()
        if operation_family == "aggregate_subtasks":
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if metric_family.startswith("concept_"):
                operation_family = metric_family.removeprefix("concept_")
        if operation_family not in {"lookup", "single_value", "ratio", "sum"}:
            return False

        target_surfaces: List[str] = []
        metric_label = _normalise_spaces(str(row.get("metric_label") or ""))
        if metric_label:
            target_surfaces.append(metric_label)
            target_surfaces.append(_normalise_spaces(re.sub(r"^(20\d{2}년\s*)?(연결기준|별도기준)?\s*", "", metric_label)))
        primary_slot = dict(answer_slots.get("primary_value") or {})
        slot_label = _normalise_spaces(str(primary_slot.get("label") or ""))
        if slot_label:
            target_surfaces.append(slot_label)
        components_by_role = dict(answer_slots.get("components_by_role") or {})
        for entries in components_by_role.values():
            for entry in entries or []:
                label = _normalise_spaces(str((entry or {}).get("label") or ""))
                if label:
                    target_surfaces.append(label)
        target_surfaces = [surface for surface in dict.fromkeys(target_surfaces) if surface]
        if not target_surfaces:
            return False

        for sibling in ordered_results:
            if sibling is row:
                continue
            sibling_metric_family = _normalise_spaces(str(sibling.get("metric_family") or "")).lower()
            sibling_operation_family = self._aggregate_result_operation_family(sibling)
            if sibling_metric_family != "narrative_summary" and sibling_operation_family != "narrative_summary":
                continue
            sibling_answer = _normalise_spaces(str(sibling.get("answer") or ""))
            if not sibling_answer or not re.search(r"\d", sibling_answer):
                continue
            if any(surface and surface in sibling_answer for surface in target_surfaces):
                return True
        return False

    def _feedback_gap_is_satisfied_by_derived_slots(
        self,
        feedback: str,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        feedback_text = _normalise_spaces(str(feedback or ""))
        if not feedback_text:
            return False

        target_surface = re.split(
            r"(?:계산에 필요한|direct value|raw value|값[이가]?|재료)",
            feedback_text,
            maxsplit=1,
        )[0]
        target_keys = self._slot_metric_keys({"label": target_surface})
        if not target_keys:
            return False
        target_periods = {
            self._period_match_key(match.group(0))
            for match in re.finditer(r"20\d{2}\s*년?", feedback_text)
            if self._period_match_key(match.group(0))
        }

        for row in ordered_results:
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family not in {"difference", "growth_rate", "ratio", "sum"}:
                continue
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if status != "ok" or self._material_gap_feedback_for_subtask_result(row):
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            for slot in self._iter_answer_slots(answer_slots):
                if not self._answer_slot_has_material(slot):
                    continue
                slot_period = self._period_match_key(self._slot_period_hint(slot))
                if target_periods and slot_period and slot_period not in target_periods:
                    continue
                if target_periods and not slot_period:
                    continue
                slot_keys = self._slot_metric_keys(slot)
                if target_keys & slot_keys:
                    return True
                if any(
                    target_key and slot_key and (target_key in slot_key or slot_key in target_key)
                    for target_key in target_keys
                    for slot_key in slot_keys
                ):
                    return True
        return False

    def _row_is_narrative_summary(self, row: Dict[str, Any]) -> bool:
        metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
        operation_family = self._aggregate_result_operation_family(row)
        return metric_family == "narrative_summary" or operation_family == "narrative_summary"

    def _unresolved_structured_numeric_gap(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        for row in ordered_results:
            if self._row_is_narrative_summary(row):
                continue
            operation_family = self._aggregate_result_operation_family(row)
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if operation_family not in {"lookup", "single_value", "ratio", "sum", "difference", "growth_rate"}:
                if not metric_family.startswith("concept_"):
                    continue
            status = str(
                row.get("status")
                or (row.get("calculation_result") or {}).get("status")
                or ""
            ).strip().lower()
            gap = self._material_gap_feedback_for_subtask_result(row)
            if not gap and status and status != "ok":
                metric_label = _normalise_spaces(
                    str(row.get("metric_label") or row.get("task_id") or "계산 결과")
                )
                gap = f"{metric_label} 계산에 필요한 재료가 누락되었습니다."
            if not gap:
                continue
            if (
                self._sibling_lookup_gap_is_satisfied(row, ordered_results)
                or self._lookup_gap_is_satisfied_by_sibling_slots(row, ordered_results)
                or self._feedback_gap_is_satisfied_by_derived_slots(gap, ordered_results)
            ):
                continue
            return gap
        return ""

    def _safe_partial_answer_for_numeric_gap(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        safe_parts: List[str] = []
        for row in ordered_results:
            if self._row_is_narrative_summary(row):
                continue
            status = str(
                row.get("status")
                or (row.get("calculation_result") or {}).get("status")
                or ""
            ).strip().lower()
            if status != "ok":
                continue
            if self._material_gap_feedback_for_subtask_result(row):
                continue
            answer = _normalise_spaces(str(row.get("answer") or ""))
            if not answer:
                calculation_result = dict(row.get("calculation_result") or {})
                answer = _normalise_spaces(
                    str(calculation_result.get("formatted_result") or calculation_result.get("rendered_value") or "")
                )
            if answer:
                safe_parts.append(answer)
        return " ".join(dict.fromkeys(safe_parts)).strip()

    def _compose_lookup_list_numeric_answer(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        lookup_result_count = 0
        items: List[str] = []
        for row in ordered_results:
            if self._row_is_narrative_summary(row):
                continue
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family not in {"lookup", "single_value"}:
                return ""
            lookup_result_count += 1
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if status != "ok" or self._material_gap_feedback_for_subtask_result(row):
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            primary_slot = dict(answer_slots.get("primary_value") or {})
            value = _normalise_spaces(
                str(
                    primary_slot.get("rendered_value")
                    or calculation_result.get("formatted_result")
                    or calculation_result.get("rendered_value")
                    or row.get("answer")
                    or ""
                )
            )
            try:
                normalized_value = float(primary_slot.get("normalized_value"))
            except (TypeError, ValueError):
                normalized_value = None
            if normalized_value is not None and normalized_value >= 0 and value.startswith("("):
                value = _normalise_spaces(value[1:].replace(")", "", 1))
            label = _normalise_spaces(
                str(primary_slot.get("label") or row.get("metric_label") or "")
            )
            if not label or not value:
                continue
            item_template = str(CALCULATION_RENDER_POLICY.get("lookup_list_item_template") or "{label} {value}")
            items.append(_normalise_spaces(item_template.format(label=label, value=value)))
        items = list(dict.fromkeys(item for item in items if item))
        if lookup_result_count < 2 or len(items) < 2:
            return ""
        separator = str(CALCULATION_RENDER_POLICY.get("lookup_list_separator") or ", ")
        answer_template = str(CALCULATION_RENDER_POLICY.get("lookup_list_answer_template") or "{items}")
        return _normalise_spaces(answer_template.format(items=separator.join(items)))

    def _lookup_value_from_table_label_metadata(
        self,
        operand: Dict[str, Any],
        evidence_item: Dict[str, Any],
    ) -> Dict[str, Any]:
        metadata = dict(evidence_item.get("metadata") or {})
        value_labels_text = _normalise_spaces(str(metadata.get("table_value_labels_text") or ""))
        if not value_labels_text:
            return {}
        surface_contract = dict(operand.get("surface_contract") or {})
        surfaces = list(
            dict.fromkeys(
                str(item).strip()
                for item in (
                    [operand.get("label")]
                    + list(operand.get("aliases") or [])
                    + list(surface_contract.get("positive") or [])
                )
                if str(item or "").strip()
            )
        )
        if not surfaces:
            return {}
        label_keys = [
            key
            for key in self._slot_metric_keys(
                {
                    "label": str(operand.get("label") or ""),
                    "concept": "",
                }
            )
            if key
        ]
        surfaces = list(dict.fromkeys(surfaces + label_keys))
        value_pattern = r"\(?\s*[+-]?\d[\d,]*(?:\.\d+)?\s*\)?"
        percent_pattern = r"\(?\s*(?P<value>[+-]?\d[\d,]*(?:\.\d+)?)\s*%\s*\)?"

        def _operand_year_hint() -> str:
            year_candidates = re.findall(
                r"20\d{2}",
                " ".join(
                    str(operand.get(key) or "")
                    for key in ("period", "period_hint", "label", "name")
                ),
            )
            return year_candidates[0] if year_candidates else ""

        def _line_label_matches_operand(line_label: str) -> bool:
            normalized_label = _normalise_spaces(line_label)
            if not normalized_label:
                return False
            for surface in surfaces:
                normalized_surface = _normalise_spaces(surface)
                if not normalized_surface:
                    continue
                if normalized_surface == normalized_label:
                    return True
                if re.search(rf"(?<!\w){re.escape(normalized_label)}(?!\w)", normalized_surface):
                    return True
            return False

        matches: List[Dict[str, Any]] = []
        for line in str(metadata.get("table_value_labels_text") or "").splitlines():
            normalized_line = _normalise_spaces(line)
            if not normalized_line:
                continue
            matched_surface = ""
            matched_value = ""
            matched_line_label = ""
            for surface in sorted(surfaces, key=len, reverse=True):
                normalized_surface = _normalise_spaces(surface)
                if not normalized_surface:
                    continue
                match = re.search(
                    rf"(?<!\S){re.escape(normalized_surface)}\s+(?P<value>{value_pattern})(?!\S)",
                    normalized_line,
                )
                if not match:
                    continue
                matched_surface = normalized_surface
                matched_value = _normalise_spaces(match.group("value")).replace(" ", "")
                matched_line_label = _normalise_spaces(normalized_line[: match.start("value")])
                break
            if not matched_value:
                line_match = re.search(
                    rf"(?P<label>.+?)\s+(?P<value>{value_pattern})(?!\S)",
                    normalized_line,
                )
                if not line_match:
                    continue
                line_label = _normalise_spaces(line_match.group("label"))
                if not _line_label_matches_operand(line_label):
                    continue
                matched_surface = line_label
                matched_value = _normalise_spaces(line_match.group("value")).replace(" ", "")
                matched_line_label = line_label
            if matched_value:
                raw_value = matched_value
                raw_unit = _normalise_spaces(str(metadata.get("unit_hint") or ""))
                normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
                if normalized_value is None:
                    continue
                matches.append({
                    "status": "ok",
                    "role": str(operand.get("role") or "operand").strip() or "operand",
                    "label": str(operand.get("label") or normalized_surface).strip(),
                    "concept": str(operand.get("concept") or "").strip(),
                    "period": str(operand.get("period") or _operand_year_hint() or metadata.get("year") or ""),
                    "raw_value": raw_value,
                    "raw_unit": raw_unit,
                    "normalized_value": normalized_value,
                    "normalized_unit": normalized_unit,
                    "rendered_value": _normalise_spaces(f"{raw_value}{raw_unit}") if raw_unit else raw_value,
                    "source_row_id": str(evidence_item.get("evidence_id") or "").strip(),
                    "source_row_ids": [str(evidence_item.get("evidence_id") or "").strip()],
                    "source_anchor": evidence_item.get("source_anchor"),
                    "_semantic_label": normalized_line,
                    "_matched_surface": matched_surface,
                    "_matched_line_label": matched_line_label,
                })
        if not matches:
            return {}

        stated_change_raw_value = ""
        for line in str(metadata.get("table_value_labels_text") or "").splitlines():
            normalized_line = _normalise_spaces(line)
            if not normalized_line:
                continue
            percent_match = re.search(
                rf"(?P<label>.+?)\s+{percent_pattern}(?!\S)",
                normalized_line,
            )
            if not percent_match:
                continue
            line_label = _normalise_spaces(percent_match.group("label"))
            if not _line_label_matches_operand(line_label):
                continue
            stated_change_raw_value = _normalise_spaces(percent_match.group("value")).replace(" ", "")
            break

        role = str(operand.get("role") or "").strip()
        period_focus = _operand_period_focus(operand, "unknown")
        krw_matches = [
            match
            for match in matches
            if _normalise_spaces(str(match.get("normalized_unit") or "")).upper() == "KRW"
        ]
        candidate_pool = krw_matches or matches
        selected = candidate_pool[0]
        operand_year = _operand_year_hint()
        report_year = str(metadata.get("year") or "")
        if operand_year and report_year and operand_year.isdigit() and report_year.isdigit():
            period_offset = max(int(report_year) - int(operand_year), 0)
            if period_offset > 0:
                selected = candidate_pool[min(period_offset, len(candidate_pool) - 1)]
            else:
                selected = candidate_pool[0]
        elif role == "prior_period" or period_focus == "prior":
            selected = candidate_pool[1] if len(candidate_pool) >= 2 else candidate_pool[-1]
        elif role == "current_period" or period_focus == "current":
            selected = candidate_pool[0]
        if not operand_year and report_year and report_year.isdigit():
            if role == "prior_period" or period_focus == "prior":
                selected["period"] = str(int(report_year) - 1)
            elif role == "current_period" or period_focus == "current":
                selected["period"] = report_year
        if stated_change_raw_value:
            selected["stated_change_raw_value"] = stated_change_raw_value
            selected["stated_change_raw_unit"] = "%"

        semantic_label = str(selected.pop("_semantic_label", ""))
        return _coerce_lookup_magnitude_record(
            selected,
            evidence_item,
            concept=str(operand.get("concept") or ""),
            statement_type=str(metadata.get("statement_type") or ""),
            row_label=str(operand.get("label") or selected.get("label") or ""),
            semantic_label=semantic_label,
        )

    def _table_label_metadata_lookup_score(
        self,
        slot: Dict[str, Any],
        evidence_item: Dict[str, Any],
    ) -> float:
        if not slot:
            return 0.0
        normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
        metadata = dict(evidence_item.get("metadata") or {})
        if not _normalise_spaces(str(metadata.get("table_value_labels_text") or "")):
            return 0.0
        raw_unit = _normalise_spaces(str(slot.get("raw_unit") or metadata.get("unit_hint") or ""))
        raw_digit_count = len(re.findall(r"\d", str(slot.get("raw_value") or "")))
        if normalized_unit in {"", "UNKNOWN"} and not raw_unit and raw_digit_count < 4:
            return 0.0
        score = 6.5
        if _normalise_spaces(str(metadata.get("unit_hint") or "")):
            score += 0.5
        if _normalise_spaces(str(metadata.get("table_source_id") or "")):
            score += 0.5
        if _normalise_spaces(str(slot.get("source_anchor") or evidence_item.get("source_anchor") or "")):
            score += 0.25
        if normalized_unit in {"", "UNKNOWN"}:
            score -= 1.5
        else:
            score += 0.25
        return score

    def _direct_structured_lookup_evidence_score(
        self,
        operand: Dict[str, Any],
        evidence_item: Dict[str, Any],
    ) -> float:
        metadata = dict(evidence_item.get("metadata") or {})
        structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
        if not structured_cells:
            return 0.0

        score = 0.0
        row_label = _normalise_spaces(str(metadata.get("row_label") or ""))
        semantic_label = _normalise_spaces(str(metadata.get("semantic_label") or row_label))
        binding_policy = dict(operand.get("binding_policy") or {})
        requires_surface_contract = bool(
            binding_policy.get("require_surface_contract_for_direct_match")
            or binding_policy.get("require_surface_contract_for_direct_lookup")
        )
        if requires_surface_contract:
            authoritative_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        evidence_item.get("claim"),
                        evidence_item.get("quote_span"),
                        evidence_item.get("raw_row_text"),
                        row_label,
                        semantic_label,
                    )
                )
            )
            if not _text_has_positive_surface(authoritative_surface, operand):
                return 0.0

        operand_needles = [
            _normalise_spaces(str(needle))
            for needle in _operand_needles(operand)
            if _normalise_spaces(str(needle))
        ]
        def _surface_variants(text: str) -> set[str]:
            normalized = _normalise_spaces(text)
            compact = re.sub(r"\s+", "", normalized)
            return {item for item in (normalized, compact) if item}

        row_variants = _surface_variants(row_label) if row_label else set()
        semantic_variants = _surface_variants(semantic_label) if semantic_label else set()
        needle_variants = {
            variant
            for needle in operand_needles
            for variant in _surface_variants(needle)
            if variant
        }
        if row_variants and needle_variants and row_variants & needle_variants:
            score += 8.0
        elif row_label and _operand_text_match(row_label, operand):
            score += 4.0
        if semantic_variants and needle_variants and semantic_variants & needle_variants:
            score += 3.0
        elif semantic_label and semantic_label != row_label and _operand_text_match(semantic_label, operand):
            score += 1.5

        numeric_cells = 0
        header_affinity = False
        for cell in structured_cells:
            raw_value = _normalise_spaces(str(cell.get("value_text") or ""))
            raw_unit = _normalise_spaces(str(cell.get("unit_hint") or metadata.get("unit_hint") or ""))
            normalized_value, _normalized_unit = _normalise_operand_value(raw_value, raw_unit)
            if normalized_value is None:
                continue
            numeric_cells += 1
            headers = _normalise_spaces(
                " ".join(str(header) for header in (cell.get("column_headers") or []) if str(header).strip())
            )
            if headers and _operand_text_match(headers, operand):
                header_affinity = True
        if header_affinity:
            score += 1.0
        if numeric_cells == 1:
            score += 1.0
        elif numeric_cells > 1:
            score -= 2.0

        value_role = _normalise_spaces(str(metadata.get("value_role") or ""))
        aggregation_stage = _normalise_spaces(str(metadata.get("aggregation_stage") or ""))
        if value_role == "adjustment":
            score -= 4.0
        if aggregation_stage in {"direct", "final", "subtotal"}:
            score += 0.75
        return score

    def _lookup_row_from_direct_structured_evidence(
        self,
        operand: Dict[str, Any],
        evidence_item: Dict[str, Any],
        *,
        index: int,
    ) -> Dict[str, Any]:
        metadata = dict(evidence_item.get("metadata") or {})
        cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
        if not cells:
            return {}
        selected_cell = _select_structured_cell(
            [{**cell, "_report_year": metadata.get("year")} for cell in cells],
            operand=operand,
            query_years=[int(metadata["year"])] if str(metadata.get("year") or "").isdigit() else [],
            period_focus=_operand_period_focus(operand, "current"),
        )
        if not selected_cell:
            return {}
        raw_value = _normalise_spaces(str(selected_cell.get("value_text") or ""))
        raw_unit = _normalise_spaces(str(selected_cell.get("unit_hint") or metadata.get("unit_hint") or ""))
        normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
        if normalized_value is None:
            return {}
        evidence_id = str(evidence_item.get("evidence_id") or "").strip()
        row = {
            "operand_id": f"direct_lookup_{index:03d}",
            "evidence_id": evidence_id,
            "source_row_id": evidence_id,
            "source_row_ids": [evidence_id] if evidence_id else [],
            "source_anchor": _normalise_spaces(str(evidence_item.get("source_anchor") or "")),
            "label": _normalise_spaces(str(operand.get("label") or metadata.get("row_label") or "")),
            "raw_value": raw_value,
            "raw_unit": raw_unit,
            "normalized_value": normalized_value,
            "normalized_unit": normalized_unit,
            "period": _normalise_spaces(str(metadata.get("year") or "")),
            "matched_operand_label": _normalise_spaces(str(operand.get("label") or "")),
            "matched_operand_concept": _normalise_spaces(str(operand.get("concept") or "")),
            "matched_operand_role": _normalise_spaces(str(operand.get("role") or "")),
            "statement_type": metadata.get("statement_type"),
            "consolidation_scope": metadata.get("consolidation_scope"),
            "table_source_id": metadata.get("table_source_id"),
        }
        return _coerce_lookup_magnitude_record(
            row,
            evidence_item,
            concept=str(operand.get("concept") or ""),
            statement_type=str(metadata.get("statement_type") or ""),
            row_label=str(metadata.get("row_label") or operand.get("label") or ""),
            semantic_label=str(metadata.get("semantic_label") or metadata.get("row_label") or ""),
        )

    def _best_direct_lookup_slot_from_evidence_pool(
        self,
        operand: Dict[str, Any],
        evidence_pool: List[Dict[str, Any]],
        *,
        state: Optional[FinancialAgentState] = None,
    ) -> tuple[Dict[str, Any], float]:
        best_slot: Dict[str, Any] = {}
        best_score = 0.0
        for evidence_item in evidence_pool:
            evidence = dict(evidence_item or {})
            score = self._direct_structured_lookup_evidence_score(operand, evidence)
            if score > best_score:
                row = self._lookup_row_from_direct_structured_evidence(
                    operand,
                    evidence,
                    index=1,
                )
                if state is not None and self._lookup_direct_row_is_ambiguous_context_table(
                    row,
                    evidence,
                    state=state,
                    required_operands=[operand],
                ):
                    row = {}
                normalized_unit = _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
                raw_unit = _normalise_spaces(str(row.get("raw_unit") or ""))
                raw_digit_count = len(re.findall(r"\d", str(row.get("raw_value") or "")))
                if row and not (normalized_unit in {"", "UNKNOWN"} and not raw_unit and raw_digit_count < 4):
                    adjusted_score = score - 1.5 if normalized_unit in {"", "UNKNOWN"} else score
                    best_slot = self._build_operand_value_slot(
                        row,
                        default_role=str(operand.get("role") or "primary_value"),
                        preserve_source_display=True,
                    )
                    best_score = adjusted_score

            table_label_slot = self._lookup_value_from_table_label_metadata(operand, evidence)
            table_label_score = self._table_label_metadata_lookup_score(table_label_slot, evidence)
            if state is not None and self._lookup_direct_row_is_ambiguous_context_table(
                table_label_slot,
                evidence,
                state=state,
                required_operands=[operand],
            ):
                table_label_slot = {}
            if table_label_slot and table_label_score > best_score:
                best_slot = table_label_slot
                best_score = table_label_score

        if not best_slot or best_score < 6.0:
            return {}, 0.0
        return best_slot, best_score

    def _best_direct_lookup_slot_from_evidence_pool_compat(
        self,
        operand: Dict[str, Any],
        evidence_pool: List[Dict[str, Any]],
        *,
        state: Optional[FinancialAgentState] = None,
    ) -> tuple[Dict[str, Any], float]:
        try:
            return self._best_direct_lookup_slot_from_evidence_pool(
                operand,
                evidence_pool,
                state=state,
            )
        except TypeError as exc:
            if "unexpected keyword argument 'state'" not in str(exc):
                raise
            return self._best_direct_lookup_slot_from_evidence_pool(operand, evidence_pool)

    def _prefer_direct_structured_lookup_evidence_rows(
        self,
        direct_structured_rows: List[Dict[str, Any]],
        *,
        evidence_items: List[Dict[str, Any]],
        required_operands: List[Dict[str, Any]],
        operation_family: str,
    ) -> List[Dict[str, Any]]:
        if operation_family not in {"lookup", "single_value"} or len(required_operands) != 1:
            return direct_structured_rows
        operand = dict(required_operands[0])
        preferred_slot, best_score = self._best_direct_lookup_slot_from_evidence_pool(operand, evidence_items)
        if not preferred_slot:
            return direct_structured_rows

        evidence_by_id = {
            str(item.get("evidence_id") or "").strip(): dict(item)
            for item in evidence_items
            if str(item.get("evidence_id") or "").strip()
        }
        current_score = 0.0
        if direct_structured_rows:
            current = dict(direct_structured_rows[0])
            current_evidence = self._evidence_item_for_operand_row(current, evidence_by_id)
            if current_evidence:
                current_score = self._direct_structured_lookup_evidence_score(operand, current_evidence)
        if direct_structured_rows and current_score >= best_score:
            return direct_structured_rows
        preferred_row = {
            "operand_id": "direct_lookup_001",
            "evidence_id": preferred_slot.get("source_row_id"),
            "source_row_id": preferred_slot.get("source_row_id"),
            "source_row_ids": preferred_slot.get("source_row_ids") or [],
            "source_anchor": preferred_slot.get("source_anchor"),
            "label": preferred_slot.get("label"),
            "raw_value": preferred_slot.get("raw_value"),
            "raw_unit": preferred_slot.get("raw_unit"),
            "normalized_value": preferred_slot.get("normalized_value"),
            "normalized_unit": preferred_slot.get("normalized_unit"),
            "period": preferred_slot.get("period"),
            "matched_operand_label": _normalise_spaces(str(operand.get("label") or "")),
            "matched_operand_concept": _normalise_spaces(str(operand.get("concept") or "")),
            "matched_operand_role": _normalise_spaces(str(operand.get("role") or "")),
        }
        return [preferred_row]

    def _recover_lookup_results_from_sibling_table_evidence(
        self,
        ordered_results: List[Dict[str, Any]],
        state: FinancialAgentState,
    ) -> List[Dict[str, Any]]:
        task_by_id = {
            str(task.get("task_id") or ""): dict(task)
            for task in (state.get("calc_subtasks") or [])
            if str(task.get("task_id") or "").strip()
        }
        evidence_pool: List[Dict[str, Any]] = []
        for row in ordered_results:
            evidence_pool.extend(dict(item) for item in (row.get("runtime_evidence") or []) if isinstance(item, dict))
        evidence_pool.extend(dict(item) for item in (state.get("evidence_items") or []) if isinstance(item, dict))
        evidence_pool.extend(dict(item) for item in (state.get("runtime_evidence") or []) if isinstance(item, dict))
        if not evidence_pool:
            return ordered_results
        evidence_by_id = {
            str(item.get("evidence_id") or "").strip(): dict(item)
            for item in evidence_pool
            if str(item.get("evidence_id") or "").strip()
        }

        def _digit_count(value: Any) -> int:
            return len(re.findall(r"\d", str(value or "")))

        def _value_refinement_allowed(
            current_slot: Dict[str, Any],
            preferred_slot: Dict[str, Any],
            preferred_evidence: Optional[Dict[str, Any]],
        ) -> bool:
            preferred_metadata = dict((preferred_evidence or {}).get("metadata") or {})
            has_structured_surface = any(
                _normalise_spaces(str(value or ""))
                for value in (
                    preferred_metadata.get("table_value_labels_text"),
                    preferred_metadata.get("row_label"),
                    preferred_metadata.get("semantic_label"),
                    preferred_metadata.get("structured_cells"),
                )
            )
            if not has_structured_surface:
                return False
            if bool(preferred_metadata.get("table_value_labels_text")) and _recovered_slot_has_primary_label_match(
                preferred_slot
            ):
                current_raw_unit = _normalise_spaces(str(current_slot.get("raw_unit") or ""))
                preferred_raw_unit = _normalise_spaces(str(preferred_slot.get("raw_unit") or ""))
                if preferred_raw_unit and (not current_raw_unit or preferred_raw_unit == current_raw_unit):
                    return True
            current_unit = _normalise_spaces(str(current_slot.get("normalized_unit") or "")).upper()
            preferred_unit = _normalise_spaces(str(preferred_slot.get("normalized_unit") or "")).upper()
            if not current_unit or not preferred_unit or current_unit == "UNKNOWN" or preferred_unit == "UNKNOWN":
                return False
            if current_unit != preferred_unit:
                return False
            current_value = current_slot.get("normalized_value")
            preferred_value = preferred_slot.get("normalized_value")
            try:
                current_float = float(current_value)
                preferred_float = float(preferred_value)
            except (TypeError, ValueError):
                return False
            if current_float == 0:
                return False
            if (current_float < 0) != (preferred_float < 0):
                return False
            relative_delta = abs(preferred_float - current_float) / max(abs(current_float), abs(preferred_float), 1.0)
            if relative_delta > 0.005:
                evidence_score = (
                    self._direct_structured_lookup_evidence_score(operand, preferred_evidence)
                    if preferred_evidence
                    else 0.0
                )
                direct_label = _normalise_spaces(
                    str(
                        preferred_metadata.get("row_label")
                        or preferred_metadata.get("semantic_label")
                        or ""
                    )
                )
                if evidence_score >= 6.0 and direct_label:
                    return True
                return bool(preferred_metadata.get("table_value_labels_text")) and _recovered_slot_has_primary_label_match(
                    preferred_slot
                )
            return _digit_count(preferred_slot.get("raw_value")) > _digit_count(current_slot.get("raw_value"))

        def _normalize_lookup_slot_unit(slot: Dict[str, Any]) -> Dict[str, Any]:
            updated = dict(slot)
            raw_value = _normalise_spaces(str(updated.get("raw_value") or ""))
            raw_unit = _normalise_spaces(str(updated.get("raw_unit") or ""))
            evidence_item = self._evidence_item_for_operand_row(updated, evidence_by_id)
            metadata = dict((evidence_item or {}).get("metadata") or {})
            unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or ""))
            source_surface = _normalise_spaces(
                " ".join(
                    str((evidence_item or {}).get(key) or "")
                    for key in ("quote_span", "raw_row_text")
                )
            )
            if raw_value and unit_hint and raw_unit != unit_hint:
                source_has_value = raw_value in source_surface or raw_value.replace(",", "") in source_surface.replace(",", "")
                source_has_raw_unit = bool(raw_unit and raw_unit in source_surface)
                if source_has_value and not source_has_raw_unit:
                    coerced_unit = unit_hint
                else:
                    coerced_unit = self._coerce_operand_unit_from_evidence(
                        raw_value=raw_value,
                        raw_unit=raw_unit,
                        evidence_item=evidence_item,
                    )
            else:
                coerced_unit = self._coerce_operand_unit_from_evidence(
                    raw_value=raw_value,
                    raw_unit=raw_unit,
                    evidence_item=evidence_item,
                )
            if coerced_unit and coerced_unit != raw_unit:
                normalized_value, normalized_unit = _normalise_operand_value(raw_value, coerced_unit)
                updated["raw_unit"] = coerced_unit
                if normalized_value is not None:
                    updated["normalized_value"] = normalized_value
                    updated["normalized_unit"] = normalized_unit
                if raw_value:
                    updated["rendered_value"] = f"{raw_value}{coerced_unit}"
            return updated

        def _lookup_result_from_slot(slot: Dict[str, Any], source_note: str) -> Dict[str, Any]:
            slot = _normalize_lookup_slot_unit(slot)
            rendered_value = _normalise_spaces(str(slot.get("rendered_value") or ""))
            label = _normalise_spaces(str(slot.get("label") or ""))
            clean_slot = {
                key: value
                for key, value in slot.items()
                if not str(key).startswith("_")
            }
            return {
                "status": "ok",
                "result_value": clean_slot.get("normalized_value"),
                "result_unit": clean_slot.get("raw_unit") or clean_slot.get("normalized_unit"),
                "rendered_value": rendered_value,
                "formatted_result": _normalise_spaces(f"{label} {rendered_value}") if label and rendered_value else rendered_value,
                "source_row_ids": list(clean_slot.get("source_row_ids") or []),
                "answer_slots": {
                    "metric_label": label,
                    "operation_family": "lookup",
                    "primary_value": clean_slot,
                    "source_row_ids": list(clean_slot.get("source_row_ids") or []),
                },
                "explanation": source_note,
            }

        recovered_results: List[Dict[str, Any]] = []
        for row in ordered_results:
            task = task_by_id.get(str(row.get("task_id") or "")) or {}
            operation_family = _normalise_spaces(
                str(row.get("operation_family") or task.get("operation_family") or "")
            ).lower()
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if operation_family not in {"lookup", "single_value"}:
                recovered_results.append(row)
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            current_slot = dict(answer_slots.get("primary_value") or {})
            operands = [dict(item) for item in (task.get("required_operands") or []) if bool(item.get("required", True))]
            if len(operands) != 1 and current_slot:
                fallback_operand = {
                    "label": current_slot.get("label") or row.get("metric_label"),
                    "concept": current_slot.get("concept"),
                    "role": current_slot.get("role") or "primary_value",
                    "period": current_slot.get("period"),
                    "required": True,
                }
                if _normalise_spaces(str(fallback_operand.get("label") or fallback_operand.get("concept") or "")):
                    operands = [fallback_operand]
            if len(operands) != 1:
                recovered_results.append(row)
                continue
            operand = operands[0]

            def _recovered_slot_has_primary_label_match(slot: Dict[str, Any]) -> bool:
                matched_line_label = _normalise_spaces(str(slot.get("_matched_line_label") or ""))
                if not matched_line_label:
                    return False
                primary_keys = self._slot_metric_keys({"label": str(operand.get("label") or ""), "concept": ""})
                primary_keys.update(
                    key
                    for key in (
                        _normalise_spaces(str(operand.get("label") or "")),
                        _normalise_spaces(str(row.get("metric_label") or "")),
                        *[
                            _normalise_spaces(str(alias or ""))
                            for alias in (operand.get("aliases") or [])
                        ],
                    )
                    if key
                )
                primary_surfaces = [
                    _normalise_spaces(str(value or ""))
                    for value in (
                        operand.get("label"),
                        row.get("metric_label"),
                    )
                    if _normalise_spaces(str(value or ""))
                ]
                if any(
                    matched_line_label in surface or re.sub(r"\s+", "", matched_line_label) in re.sub(r"\s+", "", surface)
                    for surface in primary_surfaces
                ):
                    return True
                return matched_line_label in primary_keys

            if status == "ok":
                normalized_current_slot = _normalize_lookup_slot_unit(current_slot)
                unit_aligned_row: Optional[Dict[str, Any]] = None
                if (
                    _normalise_spaces(str(normalized_current_slot.get("raw_unit") or ""))
                    != _normalise_spaces(str(current_slot.get("raw_unit") or ""))
                    or normalized_current_slot.get("normalized_value") != current_slot.get("normalized_value")
                ):
                    current_slot = normalized_current_slot
                    normalized_result = _lookup_result_from_slot(
                        current_slot,
                        "lookup result unit aligned from structured evidence metadata.",
                    )
                    unit_aligned_row = {
                        **dict(row),
                        "answer": str(normalized_result.get("formatted_result") or ""),
                        "calculation_result": normalized_result,
                        "answer_slots": normalized_result["answer_slots"],
                        "unit_aligned_from_evidence_metadata": True,
                    }
                current_evidence = self._evidence_item_for_operand_row(current_slot, evidence_by_id)
                current_score = (
                    self._direct_structured_lookup_evidence_score(operand, current_evidence)
                    if current_evidence
                    else 0.0
                )
                preferred_slot, preferred_score = self._best_direct_lookup_slot_from_evidence_pool_compat(
                    operand,
                    evidence_pool,
                    state=state,
                )
                if not preferred_slot or preferred_score <= current_score:
                    recovered_results.append(unit_aligned_row or row)
                    continue
                preferred_slot = _normalize_lookup_slot_unit(preferred_slot)
                preferred_raw = _normalise_spaces(str(preferred_slot.get("raw_value") or ""))
                current_raw = _normalise_spaces(str(current_slot.get("raw_value") or ""))
                preferred_unit = _normalise_spaces(str(preferred_slot.get("raw_unit") or ""))
                current_unit = _normalise_spaces(str(current_slot.get("raw_unit") or ""))
                preferred_normalized = preferred_slot.get("normalized_value")
                current_normalized = current_slot.get("normalized_value")
                try:
                    if preferred_normalized is not None and current_normalized is not None:
                        normalized_differs = abs(float(preferred_normalized) - float(current_normalized)) > 1e-6
                    else:
                        normalized_differs = preferred_normalized != current_normalized
                except (TypeError, ValueError):
                    normalized_differs = preferred_normalized != current_normalized
                if normalized_differs:
                    preferred_evidence = self._evidence_item_for_operand_row(preferred_slot, evidence_by_id)
                    if not _value_refinement_allowed(current_slot, preferred_slot, preferred_evidence):
                        recovered_results.append(unit_aligned_row or row)
                        continue
                if preferred_raw == current_raw and preferred_unit == current_unit and not normalized_differs:
                    recovered_results.append(unit_aligned_row or row)
                    continue
                preferred_result = _lookup_result_from_slot(
                    preferred_slot,
                    "lookup result replaced with stronger direct structured evidence.",
                )
                recovered_results.append(
                    {
                        **dict(row),
                        "answer": str(preferred_result.get("formatted_result") or ""),
                        "calculation_result": preferred_result,
                        "answer_slots": preferred_result["answer_slots"],
                        "recovered_from_sibling_table_evidence": True,
                    }
                )
                continue
            sibling_surfaces = [
                _normalise_spaces(str(item))
                for item in (task.get("sibling_lookup_surfaces") or [])
                if _normalise_spaces(str(item))
            ]
            recovered_slot: Dict[str, Any] = {}
            for evidence_item in evidence_pool:
                metadata = dict(evidence_item.get("metadata") or {})
                table_value_labels = _normalise_spaces(str(metadata.get("table_value_labels_text") or ""))
                if not table_value_labels:
                    continue
                if sibling_surfaces and not any(surface in table_value_labels for surface in sibling_surfaces):
                    continue
                recovered_slot = self._lookup_value_from_table_label_metadata(operand, evidence_item)
                if recovered_slot:
                    if not _recovered_slot_has_primary_label_match(recovered_slot):
                        recovered_slot = {}
                        continue
                    if self._lookup_direct_row_is_ambiguous_context_table(
                        recovered_slot,
                        evidence_item,
                        state=state,
                        required_operands=[operand],
                    ):
                        recovered_slot = {}
                        continue
                    break
            if not recovered_slot:
                recovered_results.append(row)
                continue
            rendered_value = _normalise_spaces(str(recovered_slot.get("rendered_value") or ""))
            label = _normalise_spaces(str(recovered_slot.get("label") or row.get("metric_label") or ""))
            calculation_result = _lookup_result_from_slot(
                {**recovered_slot, "label": label},
                "lookup result recovered from sibling table evidence.",
            )
            recovered_results.append(
                {
                    **dict(row),
                    "status": "ok",
                    "answer": str(calculation_result.get("formatted_result") or ""),
                    "calculation_result": calculation_result,
                    "answer_slots": calculation_result["answer_slots"],
                    "runtime_evidence": list(row.get("runtime_evidence") or []),
                    "recovered_from_sibling_table_evidence": True,
                }
            )
        return recovered_results

    def _align_lookup_results_with_dependency_projection(
        self,
        ordered_results: List[Dict[str, Any]],
        state: FinancialAgentState,
        aggregate_projection: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        task_by_id = {
            str(task.get("task_id") or ""): dict(task)
            for task in (state.get("calc_subtasks") or [])
            if str(task.get("task_id") or "").strip()
        }
        projected_by_task: Dict[str, List[Dict[str, Any]]] = {}
        for operand in list(aggregate_projection.get("calculation_operands") or []):
            if not isinstance(operand, dict):
                continue
            source_ids = _clean_source_row_ids([operand.get("source_row_id"), operand.get("source_row_ids")])
            for source_id in source_ids:
                if not source_id.startswith("task_output:"):
                    continue
                task_id = source_id.split(":", 1)[1]
                if task_id:
                    projected_by_task.setdefault(task_id, []).append(dict(operand))
        def _projection_operand_matches_lookup(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
            if _operand_row_matches_requirement(candidate, operand):
                return True
            candidate_label = _normalise_spaces(
                str(candidate.get("matched_operand_label") or candidate.get("label") or "")
            )
            operand_label = _normalise_spaces(str(operand.get("label") or ""))
            if candidate_label and operand_label and candidate_label == operand_label:
                return True
            candidate_concept = _normalise_spaces(str(candidate.get("matched_operand_concept") or ""))
            operand_concept = _normalise_spaces(str(operand.get("concept") or ""))
            if candidate_concept and operand_concept and candidate_concept == operand_concept:
                return True
            return bool(candidate_label and _operand_text_match(candidate_label, operand))

        def _values_differ(left: Any, right: Any) -> bool:
            try:
                if left is not None and right is not None:
                    return abs(float(left) - float(right)) > 1e-6
            except (TypeError, ValueError):
                pass
            return left != right

        def _slot_differs_from_operand(slot: Dict[str, Any], operand: Dict[str, Any]) -> bool:
            return any(
                (
                    _normalise_spaces(str(slot.get("raw_value") or ""))
                    != _normalise_spaces(str(operand.get("raw_value") or "")),
                    _normalise_spaces(str(slot.get("raw_unit") or ""))
                    != _normalise_spaces(str(operand.get("raw_unit") or "")),
                    _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
                    != _normalise_spaces(str(operand.get("normalized_unit") or "")).upper(),
                    _values_differ(slot.get("normalized_value"), operand.get("normalized_value")),
                )
            )

        def _source_task_id_for_operand(operand: Dict[str, Any]) -> str:
            source_task_id = _normalise_spaces(str(operand.get("source_task_id") or ""))
            if source_task_id:
                return source_task_id
            for source_id in _clean_source_row_ids([operand.get("source_row_id"), operand.get("source_row_ids")]):
                if source_id.startswith("task_output:"):
                    return source_id.split(":", 1)[1]
            return ""

        def _lookup_slot_matches_arithmetic_slot(
            lookup_slot: Dict[str, Any],
            arithmetic_slot: Dict[str, Any],
            role: str,
        ) -> bool:
            lookup_role = _normalise_spaces(str(lookup_slot.get("role") or ""))
            arithmetic_role = _normalise_spaces(str(arithmetic_slot.get("role") or role or ""))
            if lookup_role and arithmetic_role:
                if lookup_role == arithmetic_role:
                    return True
                if lookup_role.startswith(f"{arithmetic_role}_") or arithmetic_role.startswith(f"{lookup_role}_"):
                    return True
            lookup_concept = _normalise_spaces(str(lookup_slot.get("concept") or ""))
            arithmetic_concept = _normalise_spaces(str(arithmetic_slot.get("concept") or ""))
            if lookup_concept and arithmetic_concept and lookup_concept == arithmetic_concept:
                return True
            lookup_label = _normalise_spaces(str(lookup_slot.get("label") or ""))
            arithmetic_label = _normalise_spaces(str(arithmetic_slot.get("label") or ""))
            if lookup_label and arithmetic_label:
                if lookup_label == arithmetic_label:
                    return True
                return _operand_text_match(lookup_label, {"label": arithmetic_label})
            return False

        def _lookup_source_for_arithmetic_slot(
            *,
            current_task_id: str,
            role: str,
            slot: Dict[str, Any],
        ) -> tuple[str, Dict[str, Any]]:
            for lookup_task_id, lookup_slot in lookup_slots_by_task.items():
                if lookup_task_id == current_task_id:
                    continue
                if _lookup_slot_matches_arithmetic_slot(lookup_slot, slot, role):
                    return lookup_task_id, dict(lookup_slot)
            return "", {}

        def _lookup_slots_by_task_id() -> Dict[str, Dict[str, Any]]:
            slots: Dict[str, Dict[str, Any]] = {}
            for result_row in ordered_results:
                result_task_id = _normalise_spaces(str(result_row.get("task_id") or ""))
                if not result_task_id:
                    continue
                metric_family = _normalise_spaces(str(result_row.get("metric_family") or "")).lower()
                operation = _normalise_spaces(
                    str(
                        result_row.get("operation_family")
                        or self._aggregate_result_operation_family(result_row)
                        or ""
                    )
                ).lower()
                if metric_family in {"concept_lookup", "generic_numeric"} and operation not in {"lookup", "single_value"}:
                    operation = "lookup"
                if operation not in {"lookup", "single_value"}:
                    continue
                result = dict(result_row.get("calculation_result") or {})
                result_slots = dict(result.get("answer_slots") or result_row.get("answer_slots") or {})
                slot = dict(result_slots.get("primary_value") or {})
                if not self._answer_slot_has_material(slot):
                    producer_task = dict(task_by_id.get(result_task_id) or {})
                    if not producer_task:
                        producer_task = {
                            "task_id": result_task_id,
                            "metric_family": result_row.get("metric_family") or "concept_lookup",
                            "metric_label": result_row.get("metric_label") or "",
                            "operation_family": "lookup",
                            "required_operands": [
                                {
                                    "label": result_row.get("metric_label") or "",
                                    "role": "primary_value",
                                    "period": "",
                                }
                            ],
                        }
                    synthetic_result = _synthesize_lookup_answer_slot_from_prose(
                        active_subtask=producer_task,
                        answer=_normalise_spaces(
                            str(
                                result_row.get("answer")
                                or result.get("formatted_result")
                                or result.get("rendered_value")
                                or ""
                            )
                        ),
                        calculation_result=result,
                        selected_claim_ids=[
                            str(claim_id).strip()
                            for claim_id in (result_row.get("selected_claim_ids") or [])
                            if str(claim_id).strip()
                        ],
                    )
                    if synthetic_result:
                        result_slots = dict(synthetic_result.get("answer_slots") or {})
                        slot = dict(result_slots.get("primary_value") or {})
                if self._answer_slot_has_material(slot):
                    slots[result_task_id] = slot
            return slots

        lookup_slots_by_task = _lookup_slots_by_task_id()

        def _operand_from_source_slot(
            operand: Dict[str, Any],
            slot: Dict[str, Any],
            *,
            source_task_id: str,
        ) -> Dict[str, Any]:
            source_row_ids = _clean_source_row_ids([
                f"task_output:{source_task_id}",
                slot.get("source_row_id"),
                slot.get("source_row_ids"),
            ])
            role = _normalise_spaces(
                str(operand.get("matched_operand_role") or operand.get("role") or slot.get("role") or "")
            )
            updated = {
                **dict(operand),
                "evidence_id": f"task_output:{source_task_id}",
                "source_row_id": source_row_ids[0] if source_row_ids else f"task_output:{source_task_id}",
                "source_row_ids": source_row_ids or [f"task_output:{source_task_id}"],
                "source_anchor": _normalise_spaces(
                    str(slot.get("source_anchor") or operand.get("source_anchor") or "")
                ),
                "label": _normalise_spaces(str(slot.get("label") or operand.get("label") or "")),
                "raw_value": _normalise_spaces(str(slot.get("raw_value") or operand.get("raw_value") or "")),
                "raw_unit": _normalise_spaces(str(slot.get("raw_unit") or operand.get("raw_unit") or "")),
                "normalized_value": slot.get("normalized_value"),
                "normalized_unit": _normalise_spaces(
                    str(slot.get("normalized_unit") or operand.get("normalized_unit") or "UNKNOWN")
                ).upper()
                or "UNKNOWN",
                "period": _normalise_spaces(str(slot.get("period") or operand.get("period") or "")),
                "matched_operand_label": _normalise_spaces(
                    str(operand.get("matched_operand_label") or slot.get("label") or "")
                ),
                "matched_operand_concept": _normalise_spaces(
                    str(operand.get("matched_operand_concept") or slot.get("concept") or "")
                ),
                "matched_operand_role": role,
                "stated_change_raw_value": _normalise_spaces(str(slot.get("stated_change_raw_value") or "")),
                "stated_change_raw_unit": _normalise_spaces(str(slot.get("stated_change_raw_unit") or "")),
                "source_task_id": source_task_id,
                "source_slot": _normalise_spaces(str(operand.get("source_slot") or "primary_value")) or "primary_value",
                "dependency_resolved": True,
            }
            return updated

        def _recalculate_row_from_source_slots(row: Dict[str, Any]) -> Dict[str, Any]:
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family not in {"ratio", "sum", "difference", "growth_rate"}:
                return row
            calculation_plan = dict(row.get("calculation_plan") or {})
            operands = [dict(item) for item in list(row.get("calculation_operands") or []) if isinstance(item, dict)]
            task_id = _normalise_spaces(str(row.get("task_id") or ""))
            active_subtask = {
                **dict(task_by_id.get(task_id) or {}),
                "task_id": task_id,
                "metric_family": row.get("metric_family") or (task_by_id.get(task_id) or {}).get("metric_family"),
                "metric_label": row.get("metric_label") or (task_by_id.get(task_id) or {}).get("metric_label"),
                "operation_family": operation_family,
            }

            def _derive_operands_from_source_task_slots() -> List[Dict[str, Any]]:
                calculation_result = dict(row.get("calculation_result") or {})
                answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
                slot_candidates: List[tuple[str, Dict[str, Any]]] = []
                for role, slot_key in (
                    ("current_period", "current_value"),
                    ("prior_period", "prior_value"),
                    ("minuend", "minuend"),
                    ("subtrahend", "subtrahend"),
                ):
                    slot = dict(answer_slots.get(slot_key) or {})
                    if slot:
                        slot_candidates.append((role, slot))
                components_by_role = dict(answer_slots.get("components_by_role") or {})
                dependency_role_prefixes = (
                    "current_period",
                    "prior_period",
                    "minuend",
                    "subtrahend",
                    "numerator",
                    "denominator",
                )
                for role_key, entries in components_by_role.items():
                    role = _normalise_spaces(str(role_key or ""))
                    if not role:
                        continue
                    if role not in dependency_role_prefixes and not any(
                        role.startswith(f"{prefix}_") for prefix in dependency_role_prefixes
                    ):
                        continue
                    for slot in list(entries or []):
                        if isinstance(slot, dict):
                            slot_candidates.append((role, dict(slot)))

                derived: List[Dict[str, Any]] = []
                seen_keys: set[str] = set()
                for role, slot in slot_candidates:
                    if not self._answer_slot_has_material(slot):
                        continue
                    operand_seed = {
                        "operand_id": _normalise_spaces(str(slot.get("operand_id") or role or f"operand_{len(derived) + 1}")),
                        "matched_operand_role": role,
                        "role": role,
                        "label": _normalise_spaces(str(slot.get("label") or "")),
                        "matched_operand_label": _normalise_spaces(str(slot.get("label") or "")),
                        "concept": _normalise_spaces(str(slot.get("concept") or "")),
                        "matched_operand_concept": _normalise_spaces(str(slot.get("concept") or "")),
                        "source_row_id": slot.get("source_row_id"),
                        "source_row_ids": slot.get("source_row_ids"),
                        "source_task_id": slot.get("source_task_id"),
                        "source_slot": slot.get("source_slot") or "primary_value",
                    }
                    source_task_id = _source_task_id_for_operand(operand_seed)
                    source_slot = dict(lookup_slots_by_task.get(source_task_id) or {})
                    if not source_task_id or not self._answer_slot_has_material(source_slot):
                        source_task_id, source_slot = _lookup_source_for_arithmetic_slot(
                            current_task_id=task_id,
                            role=role,
                            slot=slot,
                        )
                    if not source_task_id or not self._answer_slot_has_material(source_slot):
                        continue
                    derived_operand = _operand_from_source_slot(
                        operand_seed,
                        source_slot,
                        source_task_id=source_task_id,
                    )
                    key = "|".join(
                        (
                            str(derived_operand.get("matched_operand_role") or ""),
                            str(derived_operand.get("source_task_id") or ""),
                            str(derived_operand.get("raw_value") or ""),
                            str(derived_operand.get("raw_unit") or ""),
                        )
                    )
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    derived.append(derived_operand)
                return derived

            def _fallback_dependency_operation_plan(derived_operands: List[Dict[str, Any]]) -> Dict[str, Any]:
                if operation_family != "growth_rate":
                    return {}
                current = next(
                    (
                        operand
                        for operand in derived_operands
                        if _normalise_spaces(str(operand.get("matched_operand_role") or "")) == "current_period"
                    ),
                    {},
                )
                prior = next(
                    (
                        operand
                        for operand in derived_operands
                        if _normalise_spaces(str(operand.get("matched_operand_role") or "")) == "prior_period"
                    ),
                    {},
                )
                if not current or not prior:
                    return {}
                current_id = _normalise_spaces(str(current.get("operand_id") or ""))
                prior_id = _normalise_spaces(str(prior.get("operand_id") or ""))
                if not current_id or not prior_id:
                    return {}
                metric_label = _normalise_spaces(str(active_subtask.get("metric_label") or active_subtask.get("task_id") or ""))
                current_label = _normalise_spaces(str(current.get("label") or current.get("matched_operand_label") or "A"))
                prior_label = _normalise_spaces(str(prior.get("label") or prior.get("matched_operand_label") or "B"))
                return {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "growth_rate",
                    "ordered_operand_ids": [current_id, prior_id],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": current_id},
                        {"variable": "B", "operand_id": prior_id},
                    ],
                    "formula": "((A - B) / B) * 100",
                    "pairwise_formula": "",
                    "result_unit": "%",
                    "operation_text": f"({current_label} - {prior_label}) / {prior_label} * 100",
                    "explanation": f"{metric_label or 'growth rate'} is computed as ((A - B) / B) * 100 from dependency task outputs.",
                    "missing_info": [],
                }

            derived_from_slots = False
            if not operands:
                operands = _derive_operands_from_source_task_slots()
                derived_from_slots = bool(operands)
            if not operands:
                return row
            updated_operands: List[Dict[str, Any]] = []
            changed = derived_from_slots
            for operand in operands:
                source_task_id = _source_task_id_for_operand(operand)
                source_slot = dict(lookup_slots_by_task.get(source_task_id) or {})
                if not source_task_id or not self._answer_slot_has_material(source_slot):
                    source_task_id, source_slot = _lookup_source_for_arithmetic_slot(
                        current_task_id=task_id,
                        role=_normalise_spaces(
                            str(operand.get("matched_operand_role") or operand.get("role") or "")
                        ),
                        slot=operand,
                    )
                if (
                    source_task_id
                    and self._answer_slot_has_material(source_slot)
                    and _slot_differs_from_operand(source_slot, operand)
                ):
                    updated_operands.append(
                        _operand_from_source_slot(
                            operand,
                            source_slot,
                            source_task_id=source_task_id,
                        )
                    )
                    changed = True
                else:
                    updated_operands.append(operand)
            deduped_operands: List[Dict[str, Any]] = []
            operand_index_by_id: Dict[str, int] = {}
            for operand in updated_operands:
                operand_id = _normalise_spaces(str(operand.get("operand_id") or ""))
                if not operand_id:
                    deduped_operands.append(operand)
                    continue
                existing_index = operand_index_by_id.get(operand_id)
                if existing_index is None:
                    operand_index_by_id[operand_id] = len(deduped_operands)
                    deduped_operands.append(operand)
                else:
                    deduped_operands[existing_index] = operand
            updated_operands = deduped_operands
            if not changed:
                return row

            if not calculation_plan:
                plan_state = {
                    **dict(state),
                    "active_subtask": active_subtask,
                    "calculation_operands": updated_operands,
                    "resolved_calculation_trace": {
                        "calculation_operands": updated_operands,
                        "calculation_plan": {},
                        "calculation_result": {},
                    },
                }
                calculation_plan = self._build_deterministic_operation_plan(plan_state, updated_operands) or {}
                if not calculation_plan:
                    calculation_plan = _fallback_dependency_operation_plan(updated_operands)
            if not calculation_plan:
                return row
            recalculation_state = {
                **dict(state),
                "active_subtask": active_subtask,
                "calculation_operands": updated_operands,
                "calculation_plan": calculation_plan,
                "calculation_result": dict(row.get("calculation_result") or {}),
                "resolved_calculation_trace": {
                    "calculation_operands": updated_operands,
                    "calculation_plan": calculation_plan,
                    "calculation_result": dict(row.get("calculation_result") or {}),
                },
                "tasks": [],
                "artifacts": [],
            }
            recalculated = self._execute_calculation(recalculation_state)
            recalculated_trace = _resolve_runtime_calculation_trace(
                recalculated,
                allow_legacy_top_level=False,
            )
            recalculated_result = dict(recalculated_trace.get("calculation_result") or {})
            if _normalise_spaces(str(recalculated_result.get("status") or "")).lower() != "ok":
                return row
            if operation_family == "ratio":
                formatted_answer = self._compact_ratio_answer(recalculation_state, recalculated_result)
            else:
                formatted_answer = _normalise_spaces(
                    str(recalculated_result.get("formatted_result") or recalculated_result.get("rendered_value") or "")
                )
            if formatted_answer:
                recalculated_result["formatted_result"] = formatted_answer
            return {
                **dict(row),
                "answer": formatted_answer or str(row.get("answer") or ""),
                "calculation_operands": list(recalculated_trace.get("calculation_operands") or updated_operands),
                "calculation_plan": dict(recalculated_trace.get("calculation_plan") or calculation_plan),
                "calculation_result": recalculated_result,
                "source_row_ids": list(recalculated_result.get("source_row_ids") or row.get("source_row_ids") or []),
                "aligned_from_source_task_slots": True,
            }

        aligned_results: List[Dict[str, Any]] = []
        changed_any = False
        for row in ordered_results:
            row = _recalculate_row_from_source_slots(dict(row))
            if row.get("aligned_from_source_task_slots"):
                changed_any = True
            task_id = str(row.get("task_id") or "").strip()
            task = task_by_id.get(task_id) or {}
            operation_family = _normalise_spaces(
                str(
                    row.get("operation_family")
                    or task.get("operation_family")
                    or self._aggregate_result_operation_family(row)
                    or ""
                )
            ).lower()
            if operation_family not in {"lookup", "single_value"}:
                aligned_results.append(row)
                continue
            required_operands = [
                dict(item)
                for item in (task.get("required_operands") or [])
                if bool(item.get("required", True))
            ]
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            current_slot = dict(answer_slots.get("primary_value") or {})
            if len(required_operands) != 1 and current_slot:
                fallback_operand = {
                    "label": current_slot.get("label") or row.get("metric_label"),
                    "concept": current_slot.get("concept"),
                    "role": current_slot.get("role") or "primary_value",
                    "required": True,
                }
                if _normalise_spaces(str(fallback_operand.get("label") or fallback_operand.get("concept") or "")):
                    required_operands = [fallback_operand]
            if len(required_operands) != 1:
                aligned_results.append(row)
                continue
            candidate = next(
                (
                    dict(item)
                    for item in projected_by_task.get(task_id, [])
                    if _projection_operand_matches_lookup(dict(item), required_operands[0])
                ),
                {},
            )
            if not candidate:
                aligned_results.append(row)
                continue

            if not self._answer_slot_has_material(current_slot):
                aligned_results.append(row)
                continue
            candidate_raw = _normalise_spaces(str(candidate.get("raw_value") or ""))
            current_raw = _normalise_spaces(str(current_slot.get("raw_value") or ""))
            if not candidate_raw or not _slot_differs_from_operand(candidate, current_slot):
                aligned_results.append(row)
                continue

            source_ids = _clean_source_row_ids([candidate.get("source_row_id"), candidate.get("source_row_ids")])
            direct_source_ids = [source_id for source_id in source_ids if not source_id.startswith("task_output:")]
            if f"task_output:{task_id}" in source_ids:
                candidate_normalized = candidate.get("normalized_value")
                current_normalized = current_slot.get("normalized_value")
                normalized_differs = False
                try:
                    if candidate_normalized is not None and current_normalized is not None:
                        normalized_differs = abs(float(candidate_normalized) - float(current_normalized)) > 1e-6
                    else:
                        normalized_differs = candidate_normalized != current_normalized
                except (TypeError, ValueError):
                    normalized_differs = candidate_normalized != current_normalized
                candidate_unit = _normalise_spaces(str(candidate.get("raw_unit") or ""))
                current_unit = _normalise_spaces(str(current_slot.get("raw_unit") or ""))
                current_source_ids = _clean_source_row_ids(
                    [current_slot.get("source_row_id"), current_slot.get("source_row_ids")]
                )
                direct_current_source_ids = [
                    source_id for source_id in current_source_ids if not source_id.startswith("task_output:")
                ]
                evidence_backed_unit_realignment = bool(
                    direct_source_ids
                    and (not direct_current_source_ids or bool(set(direct_source_ids) & set(direct_current_source_ids)))
                    and candidate_unit
                    and current_unit
                    and candidate_unit != current_unit
                )
                if candidate_raw == current_raw and normalized_differs and not evidence_backed_unit_realignment:
                    aligned_results.append(row)
                    continue
            component_slot = self._build_operand_value_slot(
                candidate,
                default_role=str(
                    candidate.get("matched_operand_role")
                    or required_operands[0].get("role")
                    or current_slot.get("role")
                    or "primary_value"
                ),
                preserve_source_display=True,
            )
            if direct_source_ids:
                component_slot["source_row_id"] = direct_source_ids[0]
                component_slot["source_row_ids"] = direct_source_ids
            primary_slot = {**component_slot, "role": "primary_value"}

            rendered_value = _normalise_spaces(str(primary_slot.get("rendered_value") or ""))
            if not rendered_value:
                rendered_value = _normalise_spaces(
                    f"{primary_slot.get('raw_value') or ''}{primary_slot.get('raw_unit') or ''}"
                )
            result_source_ids = list(primary_slot.get("source_row_ids") or source_ids)
            updated_slots = dict(answer_slots)
            updated_slots["primary_value"] = primary_slot
            updated_slots["source_row_ids"] = result_source_ids
            role_key = _normalise_spaces(str(component_slot.get("role") or ""))
            if role_key:
                components_by_role = dict(updated_slots.get("components_by_role") or {})
                components_by_role[role_key] = [component_slot]
                updated_slots["components_by_role"] = components_by_role
                group_key = "denominator" if role_key.startswith("denominator") else "numerator"
                components_by_group = dict(updated_slots.get("components_by_group") or {})
                components_by_group[group_key] = [component_slot]
                updated_slots["components_by_group"] = components_by_group

            updated_result = {
                **calculation_result,
                "status": "ok",
                "result_value": primary_slot.get("normalized_value"),
                "result_unit": primary_slot.get("raw_unit") or calculation_result.get("result_unit"),
                "rendered_value": rendered_value,
                "formatted_result": rendered_value,
                "series": [
                    {
                        "label": primary_slot.get("label"),
                        "period": primary_slot.get("period"),
                        "raw_value": primary_slot.get("raw_value"),
                        "raw_unit": primary_slot.get("raw_unit"),
                        "normalized_value": primary_slot.get("normalized_value"),
                        "normalized_unit": primary_slot.get("normalized_unit"),
                        "rendered_value": rendered_value,
                    }
                ],
                "current_value": primary_slot.get("normalized_value"),
                "current_period": primary_slot.get("period") or calculation_result.get("current_period"),
                "source_row_ids": result_source_ids,
                "answer_slots": updated_slots,
            }
            lookup_slots_by_task[task_id] = primary_slot
            aligned_results.append(
                {
                    **dict(row),
                    "answer": rendered_value,
                    "calculation_result": updated_result,
                    "answer_slots": updated_slots,
                    "aligned_from_dependency_projection": True,
                }
            )
            changed_any = True
        return aligned_results if changed_any else ordered_results

    def _preferred_complete_numeric_answer(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        for row in reversed(ordered_results):
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family not in {"ratio", "sum", "difference", "growth_rate"}:
                continue
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if status != "ok" or self._material_gap_feedback_for_subtask_result(row):
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            if operation_family == "growth_rate":
                if self._growth_row_has_conflicting_periods(row):
                    continue
                answer = self._compose_complete_growth_numeric_answer(row, ordered_results)
                if answer:
                    return answer
            if operation_family == "ratio" and self._ratio_component_consolidation_scope(
                calculation_result,
                list(row.get("calculation_operands") or []),
            ):
                answer = self._compact_ratio_answer(
                    {
                        "active_subtask": {
                            "metric_label": row.get("metric_label") or calculation_result.get("metric_label") or "",
                        },
                        "resolved_calculation_trace": {
                            "calculation_operands": list(row.get("calculation_operands") or []),
                            "calculation_plan": dict(row.get("calculation_plan") or {}),
                            "calculation_result": calculation_result,
                        },
                    },
                    calculation_result,
                )
                if answer:
                    return answer
            answer = _normalise_spaces(
                str(
                    calculation_result.get("formatted_result")
                    or calculation_result.get("rendered_value")
                    or row.get("answer")
                    or ""
                )
            )
            if answer:
                return answer
        return ""

    def _aggregate_results_include_dependency_numeric_result(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        for row in ordered_results:
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family not in {"ratio", "sum", "difference", "growth_rate"}:
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            candidate_sources = _clean_source_row_ids([
                calculation_result.get("source_row_ids"),
                row.get("source_row_ids"),
                [
                    [
                        operand.get("evidence_id"),
                        operand.get("source_row_id"),
                        operand.get("source_row_ids"),
                    ]
                    for operand in list(row.get("calculation_operands") or [])
                    if isinstance(operand, dict)
                ],
                [
                    [
                        operand.get("evidence_id"),
                        operand.get("source_row_id"),
                        operand.get("source_row_ids"),
                    ]
                    for operand in list(calculation_result.get("calculation_operands") or [])
                    if isinstance(operand, dict)
                ],
            ])
            if any(str(source_id).startswith("task_output:") for source_id in candidate_sources):
                return True
            if any(
                bool((operand or {}).get("dependency_resolved"))
                for operand in list(row.get("calculation_operands") or [])
                if isinstance(operand, dict)
            ):
                return True
        return False

    def _slot_display_from_source_task(
        self,
        slot: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        source_task_id = _normalise_spaces(str(slot.get("source_task_id") or ""))
        if not source_task_id:
            source_row_id = _normalise_spaces(str(slot.get("source_row_id") or ""))
            if source_row_id.startswith("task_output:"):
                source_task_id = source_row_id.split(":", 1)[1]
        if not source_task_id:
            return ""
        source_slot_name = _normalise_spaces(str(slot.get("source_slot") or "primary_value")) or "primary_value"
        for row in ordered_results:
            if _normalise_spaces(str(row.get("task_id") or "")) != source_task_id:
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            source_slot = dict(answer_slots.get(source_slot_name) or answer_slots.get("primary_value") or {})
            if self._answer_slot_has_material(source_slot):
                return _normalise_spaces(
                    str(source_slot.get("rendered_value") or source_slot.get("raw_value") or "")
                )
        return ""

    def _source_task_display_compatible_with_slot(
        self,
        slot: Dict[str, Any],
        source_display: str,
    ) -> bool:
        display = _normalise_spaces(str(source_display or ""))
        if not display:
            return False
        slot_display = _normalise_spaces(str(slot.get("rendered_value") or slot.get("raw_value") or ""))
        if slot_display and display == slot_display:
            return True
        source_row_id = _normalise_spaces(str(slot.get("source_row_id") or ""))
        if source_row_id.startswith("task_output:"):
            return True
        raw_unit = _normalise_spaces(str(slot.get("raw_unit") or ""))
        if not raw_unit:
            return True
        if raw_unit in display:
            return True
        normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
        krw_normalized_unit = str(CALCULATION_RENDER_POLICY.get("krw_normalized_unit") or "").upper()
        if normalized_unit == krw_normalized_unit:
            krw_display_units = tuple(
                str(item)
                for item in (CALCULATION_RENDER_POLICY.get("krw_display_units") or ())
                if str(item)
            )
            if any(unit in display for unit in krw_display_units):
                return False
        return True

    def _growth_slot_display_value(
        self,
        slot: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        source_display = self._slot_display_from_source_task(slot, ordered_results)
        if source_display and self._source_task_display_compatible_with_slot(slot, source_display):
            return source_display
        return _normalise_spaces(str(slot.get("rendered_value") or slot.get("raw_value") or ""))

    def _growth_slots_share_material(
        self,
        current_slot: Dict[str, Any],
        prior_slot: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        current_display = self._growth_slot_display_value(current_slot, ordered_results)
        prior_display = self._growth_slot_display_value(prior_slot, ordered_results)
        if current_display and prior_display and current_display == prior_display:
            return True
        current_value = current_slot.get("normalized_value")
        prior_value = prior_slot.get("normalized_value")
        if current_value is None or prior_value is None:
            return False
        try:
            return float(current_value) == float(prior_value)
        except (TypeError, ValueError):
            return False

    def _recover_growth_prior_material_from_evidence(
        self,
        *,
        current_slot: Dict[str, Any],
        prior_slot: Dict[str, Any],
        evidence_items: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, str]:
        if not evidence_items:
            return {}
        current_year_match = re.search(r"\d{4}", str(current_slot.get("period") or current_slot.get("label") or ""))
        if not current_year_match:
            return {}
        current_year = int(current_year_match.group(0))
        current_raw = _normalise_spaces(str(current_slot.get("raw_value") or ""))
        raw_unit = _normalise_spaces(str(prior_slot.get("raw_unit") or current_slot.get("raw_unit") or ""))
        if raw_unit:
            unit_pattern = r"\s*".join(re.escape(part) for part in re.split(r"\s+", raw_unit) if part)
        else:
            unit_pattern = r"[^\s\d,.;:()]{0,12}"
        number_with_unit_pattern = re.compile(
            rf"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>{unit_pattern})"
        )
        for item in evidence_items:
            surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        (item or {}).get("claim"),
                        (item or {}).get("quote_span"),
                        (item or {}).get("raw_row_text"),
                    )
                )
            )
            if not surface:
                continue
            for sentence in _split_narrative_sentences(surface) or [surface]:
                years = [int(match.group(0)) for match in re.finditer(r"\d{4}", sentence)]
                if not years or min(years) >= current_year:
                    continue
                prior_year = max(year for year in years if year < current_year)
                for match in number_with_unit_pattern.finditer(sentence):
                    value_text = _normalise_spaces(match.group("value"))
                    if current_raw and value_text == current_raw:
                        continue
                    display = _normalise_spaces(match.group(0))
                    if display:
                        year_suffix = str(CALCULATION_NARRATIVE_POLICY.get("period_year_suffix") or "")
                        return {
                            "display": display,
                            "period": f"{prior_year}{year_suffix}" if year_suffix else str(prior_year),
                            "raw_value": value_text,
                            "source_quote": _normalise_spaces(sentence),
                        }
        return {}

    def _growth_required_display_values(
        self,
        row: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        primary_slot = dict(answer_slots.get("primary_value") or {})
        current_slot = dict(answer_slots.get("current_value") or {})
        prior_slot = dict(answer_slots.get("prior_value") or {})
        prior_display = self._growth_slot_display_value(prior_slot, ordered_results)
        if self._growth_slots_share_material(current_slot, prior_slot, ordered_results):
            recovered_prior_material = self._recover_growth_prior_material_from_evidence(
                current_slot=current_slot,
                prior_slot=prior_slot,
                evidence_items=evidence_items,
            )
            if recovered_prior_material.get("display"):
                prior_display = recovered_prior_material["display"]
        required_values = [
            self._growth_slot_display_value(current_slot, ordered_results),
            prior_display,
            _normalise_spaces(
                str(
                    calculation_result.get("rendered_value")
                    or self._growth_slot_display_value(primary_slot, ordered_results)
                    or ""
                )
            ),
        ]
        return list(dict.fromkeys(value for value in required_values if value))

    def _growth_uses_source_stated_result(self, row: Dict[str, Any]) -> bool:
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

    def _compose_complete_growth_numeric_answer(
        self,
        row: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        if self._aggregate_result_operation_family(row) != "growth_rate":
            return ""
        primary_slot = dict(answer_slots.get("primary_value") or {})
        current_slot = dict(answer_slots.get("current_value") or {})
        prior_slot = dict(answer_slots.get("prior_value") or {})
        if not self._answer_slot_has_material(primary_slot):
            return ""

        growth_value = _normalise_spaces(str(calculation_result.get("rendered_value") or ""))
        if not growth_value:
            growth_value = _normalise_spaces(str(primary_slot.get("rendered_value") or primary_slot.get("raw_value") or ""))
        current_value = self._absolute_display_value(self._growth_slot_display_value(current_slot, ordered_results))
        prior_value = self._absolute_display_value(self._growth_slot_display_value(prior_slot, ordered_results))
        recovered_prior_period = ""
        if self._growth_slots_share_material(current_slot, prior_slot, ordered_results):
            recovered_prior_material = self._recover_growth_prior_material_from_evidence(
                current_slot=current_slot,
                prior_slot=prior_slot,
                evidence_items=evidence_items,
            )
            if recovered_prior_material.get("display"):
                prior_value = self._absolute_display_value(str(recovered_prior_material["display"]))
                recovered_prior_period = _normalise_spaces(str(recovered_prior_material.get("period") or ""))
        if not (growth_value and current_value and prior_value):
            return ""

        metric_label = _normalise_spaces(
            str(current_slot.get("label") or primary_slot.get("label") or row.get("metric_label") or "")
        )
        metric_label = re.sub(str(CALCULATION_SLOT_POLICY.get("period_pattern") or r"$^"), " ", metric_label)
        metric_label = _normalise_spaces(metric_label)
        if not metric_label:
            return ""

        current_period = _normalise_spaces(str(current_slot.get("period") or primary_slot.get("period") or ""))
        prior_period = _normalise_spaces(
            str(prior_slot.get("period") or CALCULATION_NARRATIVE_POLICY.get("default_prior_period") or "")
        )
        if recovered_prior_period:
            prior_period = recovered_prior_period
        direction = _normalise_spaces(str(primary_slot.get("direction") or primary_slot.get("direction_hint") or "")).lower()
        if not direction:
            normalized_value = primary_slot.get("normalized_value")
            if normalized_value is not None:
                try:
                    direction = "decrease" if float(normalized_value) < 0 else "increase"
                except (TypeError, ValueError):
                    direction = ""
            if not direction:
                direction = "decrease" if str(primary_slot.get("rendered_value") or "").strip().startswith("-") else "increase"
        direction_words = dict(CALCULATION_NARRATIVE_POLICY.get("direction_words") or {})
        growth_direction_metric_terms = tuple(
            str(item)
            for item in (CALCULATION_NARRATIVE_POLICY.get("growth_direction_metric_terms") or ())
            if str(item)
        )
        if direction == "decrease":
            direction_word = str(direction_words.get("decrease") or "decrease")
        elif any(term in metric_label for term in growth_direction_metric_terms):
            direction_word = str(direction_words.get("growth") or direction_words.get("increase") or "increase")
        else:
            direction_word = str(direction_words.get("increase") or "increase")

        year_suffix = str(CALCULATION_NARRATIVE_POLICY.get("period_year_suffix") or "")
        if current_period and year_suffix and not current_period.endswith(year_suffix):
            period_prefix = str(CALCULATION_NARRATIVE_POLICY.get("period_prefix_with_year_template") or "").format(
                period=current_period
            )
        elif current_period:
            period_prefix = str(CALCULATION_NARRATIVE_POLICY.get("period_prefix_template") or "").format(
                period=current_period
            )
        else:
            period_prefix = ""
        prior_period_display = prior_period
        if prior_period_display and year_suffix and re.fullmatch(r"\d{4}", prior_period_display):
            prior_period_display = f"{prior_period_display}{year_suffix}"
        prior_phrase = str(CALCULATION_NARRATIVE_POLICY.get("prior_phrase_with_value_template") or "").format(
            period=prior_period_display,
            value=prior_value,
        )
        return _normalise_spaces(
            str(CALCULATION_NARRATIVE_POLICY.get("growth_numeric_sentence_template") or "").format(
                period_prefix=period_prefix,
                metric_label=metric_label,
                topic_particle=_topic_particle(metric_label),
                current_value=current_value,
                prior_phrase=prior_phrase,
                growth_value=self._absolute_display_value(growth_value),
                direction_word=direction_word,
            )
        )

    def _growth_row_has_conflicting_periods(self, row: Dict[str, Any]) -> bool:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        current_slot = dict(answer_slots.get("current_value") or {})
        prior_slot = dict(answer_slots.get("prior_value") or {})
        current_period = self._period_match_key(
            self._slot_period_hint(current_slot) or str(calculation_result.get("current_period") or "")
        )
        prior_period = self._period_match_key(
            self._slot_period_hint(prior_slot) or str(calculation_result.get("prior_period") or "")
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

    def _ensure_complete_growth_numeric_answer(
        self,
        answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        for row in reversed(ordered_results):
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            complete_answer = self._compose_complete_growth_numeric_answer(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
            if not complete_answer:
                continue
            required_values = self._growth_required_display_values(row, ordered_results, evidence_items)
            if (
                required_values
                and all(value in answer_text for value in required_values)
                and not self._growth_answer_has_untraced_numeric_sentence(
                    answer_text,
                    complete_answer,
                    required_values,
                )
            ):
                return answer_text
            extra_sentences: List[str] = []
            for sentence in _split_narrative_sentences(answer_text):
                cleaned = _normalise_spaces(sentence)
                if not cleaned or cleaned in complete_answer:
                    continue
                if any(value and value in cleaned for value in required_values):
                    continue
                if self._growth_sentence_has_untraced_material_numeric(
                    cleaned,
                    complete_answer,
                    required_values,
                ):
                    continue
                extra_sentences.append(cleaned)
            return _normalise_spaces(" ".join([complete_answer, *extra_sentences]))
        return answer_text

    def _enforce_source_stated_growth_answer_contract(
        self,
        answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text:
            return answer_text
        for row in reversed(ordered_results):
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            if not self._growth_uses_source_stated_result(row):
                continue
            complete_answer = self._compose_complete_growth_numeric_answer(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
            if not complete_answer:
                continue
            required_values = self._growth_required_display_values(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
            if (
                required_values
                and all(value in answer_text for value in required_values)
                and not self._growth_answer_has_untraced_numeric_sentence(
                    answer_text,
                    complete_answer,
                    required_values,
                )
            ):
                return answer_text
            extra_sentences: List[str] = []
            for sentence in _split_narrative_sentences(answer_text):
                cleaned = _normalise_spaces(sentence)
                if not cleaned or cleaned in complete_answer:
                    continue
                if any(value and value in cleaned for value in required_values):
                    continue
                if self._growth_sentence_has_untraced_material_numeric(
                    cleaned,
                    complete_answer,
                    required_values,
                ):
                    continue
                extra_sentences.append(cleaned)
            return _normalise_spaces(" ".join([complete_answer, *extra_sentences]))
        return answer_text

    def _supported_aggregate_subtask_answer(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        for row in ordered_results:
            if self._aggregate_result_operation_family(row) != "aggregate_subtasks":
                continue
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if status and status not in {"ok", "ready"}:
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            row_answer = _normalise_spaces(
                str(
                    row.get("answer")
                    or calculation_result.get("formatted_result")
                    or calculation_result.get("rendered_value")
                    or ""
                )
            )
            if not row_answer or not re.search(r"\d", row_answer):
                continue
            return row_answer
        return ""

    def _has_strong_growth_trace_for_answer_refresh(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        for row in ordered_results:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            primary_slot = dict(answer_slots.get("primary_value") or {})
            current_slot = dict(answer_slots.get("current_value") or {})
            prior_slot = dict(answer_slots.get("prior_value") or {})
            if not all(
                self._answer_slot_has_material(slot)
                for slot in (primary_slot, current_slot, prior_slot)
            ):
                continue
            direct_operand_count = 0
            for slot in (current_slot, prior_slot):
                source_ids = _clean_source_row_ids([
                    slot.get("source_row_id"),
                    slot.get("source_row_ids"),
                ])
                if slot.get("normalized_value") is not None and any(
                    source_id and not source_id.startswith("task_output:")
                    for source_id in source_ids
                ):
                    direct_operand_count += 1
            if direct_operand_count >= 2:
                return True
        return False

    def _answer_matches_supported_aggregate_subtask(
        self,
        answer: str,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text or not re.search(r"\d", answer_text):
            return False
        row_answer = self._supported_aggregate_subtask_answer(ordered_results)
        if not row_answer or not (answer_text == row_answer or row_answer in answer_text):
            return False
        if (
            self._has_strong_growth_trace_for_answer_refresh(ordered_results)
            and self._growth_answer_has_untraced_numeric_material(answer_text, ordered_results)
        ):
            return False
        return True

    def _growth_sentence_has_untraced_material_numeric(
        self,
        sentence: str,
        complete_answer: str,
        required_values: List[str],
    ) -> bool:
        cleaned = _normalise_spaces(str(sentence or ""))
        if not cleaned:
            return False
        allowed_surface = _normalise_spaces(" ".join([str(complete_answer or ""), *required_values]))
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

    def _growth_answer_has_untraced_numeric_sentence(
        self,
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
        for sentence in _split_narrative_sentences(answer_text):
            cleaned = _normalise_spaces(sentence)
            if not cleaned or cleaned in complete_text:
                continue
            if not any(value and value in cleaned for value in required_values):
                continue
            numeric_tokens = [match.group(0) for match in number_pattern.finditer(cleaned)]
            if any(token and token not in allowed_surface for token in numeric_tokens):
                return True
        return False

    def _growth_answer_has_untraced_numeric_material(
        self,
        answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text:
            return False
        for row in ordered_results:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            complete_answer = self._compose_complete_growth_numeric_answer(row, ordered_results)
            required_values = self._growth_required_display_values(row, ordered_results, evidence_items)
            if not complete_answer or not required_values:
                continue
            if self._growth_answer_has_untraced_numeric_sentence(answer_text, complete_answer, required_values):
                return True
            for sentence in _split_narrative_sentences(answer_text):
                if self._growth_sentence_has_untraced_material_numeric(
                    sentence,
                    complete_answer,
                    required_values,
                ):
                    return True
        return False

    def _narrative_summary_conflicts_with_growth_trace(
        self,
        narrative_answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        answer_text = _normalise_spaces(str(narrative_answer or ""))
        if not answer_text:
            return False
        percent_pattern = str(CALCULATION_NARRATIVE_POLICY.get("percent_display_pattern") or r"\d[\d,]*(?:\.\d+)?%")
        for row in ordered_results:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            complete_answer = self._compose_complete_growth_numeric_answer(row, ordered_results)
            required_values = self._growth_required_display_values(row, ordered_results, evidence_items)
            if not complete_answer or not required_values:
                continue
            allowed_surface = _normalise_spaces(" ".join([complete_answer, *required_values]))
            percent_tokens = [
                _normalise_spaces(match.group(0))
                for match in re.finditer(percent_pattern, answer_text)
                if _normalise_spaces(match.group(0))
            ]
            if percent_tokens and any(token not in allowed_surface for token in percent_tokens):
                return True
        return False

    def _preferred_conflicting_growth_narrative_answer(
        self,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        missing_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ()))
        for row in ordered_results:
            if not self._row_is_narrative_summary(row):
                continue
            row_answer = _normalise_spaces(
                str(
                    row.get("answer")
                    or (row.get("calculation_result") or {}).get("formatted_result")
                    or (row.get("calculation_result") or {}).get("rendered_value")
                    or ""
                )
            )
            if not row_answer or any(marker and marker in row_answer for marker in missing_markers):
                continue
            if not self._narrative_summary_conflicts_with_growth_trace(row_answer, ordered_results, evidence_items):
                continue
            clean_candidates = self._growth_narrative_sentence_candidates(
                query=query,
                ordered_results=[row],
                evidence_items=evidence_items or [],
            )
            if clean_candidates:
                _score, row_answer, candidate_claim_ids = clean_candidates[0]
                selected_claim_ids = [
                    str(claim_id).strip()
                    for claim_id in (candidate_claim_ids or [])
                    if str(claim_id).strip()
                ]
            elif _narrative_sentence_looks_table_noisy(row_answer):
                continue
            else:
                selected_claim_ids = [
                    str(claim_id).strip()
                    for claim_id in (row.get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                ]
            return {
                "answer": row_answer,
                "selected_claim_ids": selected_claim_ids,
            }
        return {}

    def _aggregate_results_include_source_task_slot_realignment(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        for row in ordered_results:
            if not row.get("aligned_from_source_task_slots"):
                continue
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family in {"ratio", "sum", "difference", "growth_rate"}:
                return True
        return False

    def _query_requests_explanatory_context(
        self,
        query: str,
    ) -> bool:
        text = _normalise_spaces(str(query or "")).lower()
        if not text:
            return False
        explanatory_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("explanatory_markers") or ()))
        return any(marker in text for marker in explanatory_markers)

    def _answer_reuses_narrative_summary_text(
        self,
        answer: str,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text:
            return False
        for row in ordered_results:
            if not self._row_is_narrative_summary(row):
                continue
            narrative_answer = _normalise_spaces(str(row.get("answer") or ""))
            if len(narrative_answer) < 20 or not re.search(r"\d", narrative_answer):
                continue
            if narrative_answer in answer_text or answer_text in narrative_answer:
                return True
        return False

    def _refresh_numeric_answer_preserving_narrative_context(
        self,
        *,
        query: str,
        current_answer: str,
        numeric_answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        numeric_text = _normalise_spaces(str(numeric_answer or ""))
        if not any(self._row_is_narrative_summary(row) for row in ordered_results):
            return {"answer": numeric_text, "selected_claim_ids": []}

        query_text = _normalise_spaces(str(query or ""))
        conflicting_narrative = self._preferred_conflicting_growth_narrative_answer(
            query=query_text,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )
        if conflicting_narrative:
            return conflicting_narrative

        candidate_answer = self._ensure_complete_growth_numeric_answer(
            current_answer,
            ordered_results,
            evidence_items=evidence_items,
        )
        if (
            not self._growth_answer_has_untraced_numeric_material(candidate_answer, ordered_results, evidence_items)
            and self._answer_satisfies_growth_narrative_intent(
                query=query_text,
                answer=candidate_answer,
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        ):
            return {"answer": candidate_answer, "selected_claim_ids": []}

        composed = self._compose_growth_narrative_answer(
            query=query_text,
            ordered_results=ordered_results,
            existing_answer=candidate_answer or numeric_text,
            evidence_items=evidence_items,
        )
        composed_answer = _normalise_spaces(str((composed or {}).get("compressed_answer") or ""))
        if self._growth_answer_has_untraced_numeric_material(
            composed_answer,
            ordered_results,
            evidence_items,
        ):
            composed_answer = self._ensure_complete_growth_numeric_answer(
                composed_answer,
                ordered_results,
                evidence_items=evidence_items,
            )
        if composed_answer and self._answer_satisfies_growth_narrative_intent(
            query=query_text,
            answer=composed_answer,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        ) and not self._growth_answer_has_untraced_numeric_material(
            composed_answer,
            ordered_results,
            evidence_items,
        ):
            return {
                "answer": composed_answer,
                "selected_claim_ids": [
                    str(claim_id).strip()
                    for claim_id in ((composed or {}).get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                ],
            }

        missing_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ()))
        narrative_parts: List[str] = []
        selected_claim_ids: List[str] = []
        for _score, sentence, claim_ids in self._growth_narrative_sentence_candidates(
            query=query_text,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        ):
            candidate_sentence = _normalise_spaces(sentence)
            if not candidate_sentence or candidate_sentence in numeric_text:
                continue
            narrative_parts.append(candidate_sentence)
            selected_claim_ids.extend(str(claim_id).strip() for claim_id in (claim_ids or []) if str(claim_id).strip())
            break
        if not narrative_parts:
            for row in ordered_results:
                if not self._row_is_narrative_summary(row):
                    continue
                row_answer = _normalise_spaces(
                    str(
                        row.get("answer")
                        or (row.get("calculation_result") or {}).get("formatted_result")
                        or (row.get("calculation_result") or {}).get("rendered_value")
                        or ""
                    )
                )
                if not row_answer or any(marker and marker in row_answer for marker in missing_markers):
                    continue
                if row_answer in numeric_text:
                    continue
                narrative_parts.append(row_answer)
                selected_claim_ids.extend(
                    str(claim_id).strip()
                    for claim_id in (row.get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                )

        if narrative_parts:
            raw_combined_answer = _normalise_spaces(" ".join([numeric_text, *narrative_parts]))
            combined_answer = self._ensure_complete_growth_numeric_answer(
                raw_combined_answer,
                ordered_results,
                evidence_items=evidence_items,
            )
            for candidate_combined_answer in (raw_combined_answer, combined_answer):
                if not candidate_combined_answer:
                    continue
                if self._growth_answer_has_untraced_numeric_material(
                    candidate_combined_answer,
                    ordered_results,
                    evidence_items,
                ):
                    continue
                contains_narrative_part = any(
                    part and part in candidate_combined_answer
                    for part in narrative_parts
                )
                if self._answer_satisfies_growth_narrative_intent(
                    query=query_text,
                    answer=candidate_combined_answer,
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                ) or contains_narrative_part:
                    return {
                        "answer": candidate_combined_answer,
                        "selected_claim_ids": list(dict.fromkeys(selected_claim_ids)),
                    }
            if self._query_requests_explanatory_context(query_text):
                if self._growth_answer_has_untraced_numeric_material(
                    combined_answer,
                    ordered_results,
                    evidence_items,
                ):
                    clean_numeric = self._ensure_complete_growth_numeric_answer(
                        numeric_text,
                        ordered_results,
                        evidence_items=evidence_items,
                    )
                    return {"answer": clean_numeric or numeric_text, "selected_claim_ids": []}
                return {
                    "answer": combined_answer,
                    "selected_claim_ids": list(dict.fromkeys(selected_claim_ids)),
                }

        if self._growth_answer_has_untraced_numeric_material(numeric_text, ordered_results, evidence_items):
            clean_numeric = self._ensure_complete_growth_numeric_answer(
                numeric_text,
                ordered_results,
                evidence_items=evidence_items,
            )
            return {"answer": clean_numeric or candidate_answer or numeric_text, "selected_claim_ids": []}
        return {"answer": numeric_text, "selected_claim_ids": []}

    def _preferred_aggregate_fallback_answer(
        self,
        ordered_results: List[Dict[str, Any]],
        default_answer: str,
    ) -> str:
        if self._unresolved_structured_numeric_gap(ordered_results):
            safe_answer = self._safe_partial_answer_for_numeric_gap(ordered_results)
            return safe_answer

        supported_aggregate_answer = self._supported_aggregate_subtask_answer(ordered_results)
        if supported_aggregate_answer:
            return supported_aggregate_answer

        conflicting_narrative = self._preferred_conflicting_growth_narrative_answer(
            query="",
            ordered_results=ordered_results,
            evidence_items=[],
        )
        if conflicting_narrative:
            return str(conflicting_narrative.get("answer") or default_answer)

        has_narrative_summary = any(self._row_is_narrative_summary(row) for row in ordered_results)
        complete_numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
        if complete_numeric_answer and (
            has_narrative_summary
            or self._aggregate_results_include_dependency_numeric_result(ordered_results)
        ):
            return complete_numeric_answer

        for row in ordered_results:
            if not self._row_is_narrative_summary(row):
                continue
            sibling_answer = _normalise_spaces(str(row.get("answer") or ""))
            if sibling_answer and re.search(r"\d", sibling_answer):
                return sibling_answer
        return default_answer

    def _answer_evidence_numeric_candidates(self, text: str) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        render_policy = dict(CALCULATION_RENDER_POLICY)
        unit_scale = {
            str(unit): float(scale)
            for unit, scale in dict(render_policy.get("krw_display_unit_scales") or {}).items()
            if str(unit)
        }
        percent_units = [
            str(unit)
            for unit in (NUMERIC_UNIT_NORMALIZATION_POLICY.get("percent_units") or ())
            if str(unit)
        ]
        unit_terms = sorted([*unit_scale.keys(), *percent_units], key=len, reverse=True)
        unit_pattern = "|".join(re.escape(unit) for unit in unit_terms)
        if unit_pattern:
            pattern = re.compile(
                rf"(?P<value>\(?-?\d[\d,]*(?:\.\d+)?\)?)(?:\s*(?P<unit>{unit_pattern}))?"
            )
        else:
            pattern = re.compile(r"(?P<value>\(?-?\d[\d,]*(?:\.\d+)?\)?)")
        text_surface = str(text or "")
        context_unit = next((unit for unit in unit_terms if unit in unit_scale and unit in text_surface), "")
        for match in pattern.finditer(str(text or "")):
            raw_value = match.group("value")
            unit = match.groupdict().get("unit") or ""
            parsed = _parse_number_text(raw_value)
            if parsed is None:
                continue
            digit_count = len(re.sub(r"\D", "", raw_value))
            if not unit and digit_count == 4 and 1900 <= abs(parsed) <= 2100:
                continue
            if unit in set(percent_units):
                candidates.append(
                    {
                        "kind": "percent",
                        "value": parsed,
                        "unit": unit,
                        "display_step": 0.01 if "." in raw_value else 1.0,
                    }
                )
            elif unit in unit_scale:
                candidates.append(
                    {
                        "kind": "currency",
                        "value": parsed * unit_scale[unit],
                        "unit": unit,
                        "display_step": unit_scale[unit],
                    }
                )
            elif context_unit and digit_count >= 4:
                candidates.append(
                    {
                        "kind": "currency",
                        "value": parsed * unit_scale[context_unit],
                        "unit": context_unit,
                        "display_step": unit_scale[context_unit],
                    }
                )
            elif digit_count >= 4:
                candidates.append(
                    {
                        "kind": "generic",
                        "value": parsed,
                        "unit": unit,
                        "display_step": 1.0,
                    }
                )
        return candidates

    def _numeric_candidates_equivalent_for_evidence(
        self,
        left: Dict[str, Any],
        right: Dict[str, Any],
    ) -> bool:
        if str(left.get("kind") or "") != str(right.get("kind") or ""):
            return False
        try:
            left_value = float(left.get("value"))
            right_value = float(right.get("value"))
        except (TypeError, ValueError):
            return False
        kind = str(left.get("kind") or "")
        if kind == "currency":
            left_value = abs(left_value)
            right_value = abs(right_value)
            tolerance = max(
                abs(left_value) * 5e-4,
                float(left.get("display_step") or 1.0),
                float(right.get("display_step") or 1.0),
            )
        elif kind == "percent":
            tolerance = max(
                0.06,
                float(left.get("display_step") or 0.01) / 2.0,
                float(right.get("display_step") or 0.01) / 2.0,
            )
        else:
            tolerance = max(abs(left_value) * 1e-6, 0.5)
        return abs(left_value - right_value) <= tolerance

    def _evidence_text_for_final_support(self, evidence: Dict[str, Any]) -> str:
        metadata = dict(evidence.get("metadata") or {})
        return _normalise_spaces(
            " ".join(
                str(value or "")
                for value in (
                    evidence.get("claim"),
                    evidence.get("quote_span"),
                    evidence.get("raw_row_text"),
                    evidence.get("source_context"),
                    metadata.get("table_value_labels_text"),
                    metadata.get("table_header_context"),
                    metadata.get("table_summary_text"),
                )
            )
        )

    def _evidence_supports_final_answer_numeric_material(
        self,
        evidence: Dict[str, Any],
        answer_candidates: List[Dict[str, Any]],
    ) -> bool:
        evidence_candidates = self._answer_evidence_numeric_candidates(
            self._evidence_text_for_final_support(evidence)
        )
        if not evidence_candidates:
            return False
        return any(
            self._numeric_candidates_equivalent_for_evidence(answer_candidate, evidence_candidate)
            for answer_candidate in answer_candidates
            for evidence_candidate in evidence_candidates
        )

    def _text_supports_final_answer_numeric_material(
        self,
        text: str,
        answer_candidates: List[Dict[str, Any]],
    ) -> bool:
        text_candidates = self._answer_evidence_numeric_candidates(text)
        if not text_candidates:
            return False
        return any(
            self._numeric_candidates_equivalent_for_evidence(answer_candidate, text_candidate)
            for answer_candidate in answer_candidates
            for text_candidate in text_candidates
        )

    def _table_numeric_support_text_for_final_answer(
        self,
        evidence: Dict[str, Any],
        *,
        final_answer: str,
        answer_candidates: List[Dict[str, Any]],
    ) -> str:
        metadata = dict(evidence.get("metadata") or {})
        table_lines = [
            _normalise_spaces(line)
            for line in str(metadata.get("table_value_labels_text") or "").splitlines()
            if _normalise_spaces(line)
        ]
        if not table_lines:
            return ""
        answer_surface = re.sub(r"\s+", "", _normalise_spaces(final_answer))
        unit_terms = sorted(
            {
                *[str(unit) for unit in dict(CALCULATION_RENDER_POLICY.get("krw_display_unit_scales") or {})],
                *[str(unit) for unit in (NUMERIC_UNIT_NORMALIZATION_POLICY.get("percent_units") or ())],
            },
            key=len,
            reverse=True,
        )
        unit_pattern = "|".join(re.escape(unit) for unit in unit_terms if unit)

        def _line_label(line: str) -> str:
            label = re.sub(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", " ", line)
            if unit_pattern:
                label = re.sub(unit_pattern, " ", label)
            label = re.sub(r"[|:;()\[\]/,]+", " ", label)
            return re.sub(r"\s+", "", _normalise_spaces(label))

        support_lines: List[str] = []
        for line in table_lines:
            label = _line_label(line)
            if len(label) < 2 or label not in answer_surface:
                continue
            line_candidates = self._answer_evidence_numeric_candidates(line)
            if not line_candidates:
                continue
            if any(
                self._numeric_candidates_equivalent_for_evidence(answer_candidate, line_candidate)
                for answer_candidate in answer_candidates
                for line_candidate in line_candidates
            ):
                support_lines.append(line)
            if len(support_lines) >= 4:
                break
        if not support_lines:
            return ""
        header = _normalise_spaces(
            " ".join(
                str(value or "")
                for value in (
                    metadata.get("table_header_context"),
                    metadata.get("table_context"),
                )
            )
        )
        return _normalise_spaces(" ; ".join([header, *support_lines] if header else support_lines))

    def _promote_table_numeric_support_evidence(
        self,
        evidence: Dict[str, Any],
        *,
        final_answer: str,
        answer_candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        support_text = self._table_numeric_support_text_for_final_answer(
            evidence,
            final_answer=final_answer,
            answer_candidates=answer_candidates,
        )
        if not support_text:
            return evidence
        promoted = dict(evidence)
        claim = _normalise_spaces(str(promoted.get("claim") or ""))
        quote_span = _normalise_spaces(str(promoted.get("quote_span") or ""))
        promoted["claim"] = _normalise_spaces(" | ".join(part for part in (claim, support_text) if part))
        promoted["quote_span"] = _normalise_spaces(" | ".join(part for part in (quote_span, support_text) if part))
        metadata = dict(promoted.get("metadata") or {})
        metadata["final_answer_table_numeric_support"] = support_text
        promoted["metadata"] = metadata
        return promoted

    def _filter_aggregate_evidence_for_final_answer(
        self,
        evidence_items: List[Dict[str, Any]],
        *,
        final_answer: str,
        selected_claim_ids: List[str],
    ) -> List[Dict[str, Any]]:
        answer_candidates = self._answer_evidence_numeric_candidates(final_answer)
        if not evidence_items or not answer_candidates:
            return list(evidence_items or [])
        answer_has_percent = any(str(candidate.get("kind") or "") == "percent" for candidate in answer_candidates)
        selected = {str(value).strip() for value in (selected_claim_ids or []) if str(value).strip()}
        selected_or_operand_numeric_support = any(
            (
                str((item or {}).get("evidence_id") or "").strip() in selected
                or str((item or {}).get("evidence_id") or "").strip().startswith("operand::")
            )
            and self._evidence_supports_final_answer_numeric_material(dict(item or {}), answer_candidates)
            for item in list(evidence_items or [])
        )
        operand_surface_support = any(
            str((item or {}).get("evidence_id") or "").strip().startswith("operand::")
            and bool(dict((item or {}).get("metadata") or {}).get("supports_answer_numeric_surface"))
            for item in list(evidence_items or [])
        )
        filtered: List[Dict[str, Any]] = []
        for item in list(evidence_items or []):
            evidence = dict(item or {})
            evidence_id = str(evidence.get("evidence_id") or "").strip()
            metadata = dict(evidence.get("metadata") or {})
            if not evidence_id.startswith("retrieved_narrative::"):
                evidence = self._promote_table_numeric_support_evidence(
                    evidence,
                    final_answer=final_answer,
                    answer_candidates=answer_candidates,
                )
            if evidence_id and evidence_id in selected:
                quote_span = _normalise_spaces(str(evidence.get("quote_span") or ""))
                raw_row_text = _normalise_spaces(str(evidence.get("raw_row_text") or ""))
                if (
                    operand_surface_support
                    and raw_row_text
                    and quote_span
                    and not evidence_id.startswith("retrieved_narrative::")
                    and not self._text_supports_final_answer_numeric_material(quote_span, answer_candidates)
                ):
                    continue
                filtered.append(evidence)
                continue
            if (
                selected
                and selected_or_operand_numeric_support
                and evidence_id
                and not evidence_id.startswith("operand::")
                and not evidence_id.startswith("recon::")
            ):
                continue
            if answer_has_percent and evidence_id.startswith("operand::") and metadata.get("supports_derived_percent"):
                filtered.append(evidence)
                continue
            if evidence_id.startswith("operand::") and metadata.get("supports_answer_numeric_surface"):
                filtered.append(evidence)
                continue
            if self._evidence_supports_final_answer_numeric_material(evidence, answer_candidates):
                filtered.append(evidence)
        return filtered or list(evidence_items or [])

    def _append_operand_evidence_for_final_answer(
        self,
        evidence_items: List[Dict[str, Any]],
        *,
        operands: List[Dict[str, Any]],
        final_answer: str,
    ) -> List[Dict[str, Any]]:
        answer_candidates = self._answer_evidence_numeric_candidates(final_answer)
        if not operands or not answer_candidates:
            return list(evidence_items or [])
        answer_has_percent = any(str(candidate.get("kind") or "") == "percent" for candidate in answer_candidates)
        derivation_roles = {
            "current_period",
            "prior_period",
            "numerator",
            "denominator",
            "numerator_1",
            "denominator_1",
            "minuend",
            "subtrahend",
        }
        updated = [dict(item or {}) for item in (evidence_items or [])]
        seen_ids = {
            str(item.get("evidence_id") or "").strip()
            for item in updated
            if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
        }
        for operand in list(operands or []):
            row = dict(operand or {})
            raw_value = _normalise_spaces(str(row.get("raw_value") or row.get("value") or ""))
            raw_unit = _normalise_spaces(str(row.get("raw_unit") or ""))
            rendered_value = _normalise_spaces(str(row.get("rendered_value") or row.get("display") or ""))
            source_anchor = _normalise_spaces(str(row.get("source_anchor") or ""))
            source_quote = _normalise_spaces(
                str(row.get("source_quote") or row.get("quote_span") or row.get("raw_row_text") or "")
            )
            if (not raw_value and not rendered_value) or not source_anchor:
                continue
            display_value = rendered_value or _normalise_spaces(f"{raw_value}{raw_unit}")
            operand_text = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        row.get("label"),
                        row.get("period"),
                        display_value,
                    )
                )
            )
            operand_candidates = self._answer_evidence_numeric_candidates(operand_text)
            supports_answer_numeric = any(
                self._numeric_candidates_equivalent_for_evidence(answer_candidate, operand_candidate)
                for answer_candidate in answer_candidates
                for operand_candidate in operand_candidates
            )
            supports_answer_numeric_surface = False
            answer_surface = re.sub(r"[\s,]", "", _normalise_spaces(final_answer))
            raw_surface = re.sub(r"[\s,]", "", raw_value)
            raw_unit_surface = re.sub(r"[\s,]", "", f"{raw_value}{raw_unit}")
            rendered_surface = re.sub(r"[\s,]", "", rendered_value)
            if raw_surface and raw_surface in answer_surface:
                supports_answer_numeric = True
                supports_answer_numeric_surface = True
            if raw_unit_surface and raw_unit_surface in answer_surface:
                supports_answer_numeric = True
                supports_answer_numeric_surface = True
            if rendered_surface and rendered_surface in answer_surface:
                supports_answer_numeric = True
                supports_answer_numeric_surface = True
            role = _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or ""))
            normalized_unit = _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
            supports_derived_percent = bool(
                answer_has_percent
                and role in derivation_roles
                and normalized_unit == "KRW"
                and operand_candidates
            )
            if not supports_answer_numeric and not supports_derived_percent:
                continue
            operand_id = _normalise_spaces(str(row.get("operand_id") or row.get("matched_operand_role") or "operand"))
            evidence_id = f"operand::{operand_id}"
            if evidence_id in seen_ids:
                continue
            seen_ids.add(evidence_id)
            updated.append(
                {
                    "evidence_id": evidence_id,
                    "source_anchor": source_anchor,
                    "claim": operand_text,
                    "quote_span": source_quote or operand_text,
                    "support_level": "direct",
                    "question_relevance": "high",
                    "metadata": {
                        "section_path": source_anchor,
                        "unit_hint": raw_unit,
                        "operand_role": role,
                        "supports_derived_percent": supports_derived_percent,
                        "supports_answer_numeric_surface": supports_answer_numeric_surface,
                    },
                }
            )
        return updated

    def _append_retrieved_narrative_evidence_for_final_answer(
        self,
        evidence_items: List[Dict[str, Any]],
        *,
        final_answer: str,
        docs: List[Any],
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        answer_text = _normalise_spaces(str(final_answer or ""))
        if not answer_text or not docs:
            return list(evidence_items or []), []
        answer_numeric_candidates = self._answer_evidence_numeric_candidates(answer_text)

        updated = [dict(item or {}) for item in (evidence_items or [])]
        selected_ids: List[str] = []
        existing_ids = {
            str(item.get("evidence_id") or "").strip()
            for item in updated
            if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
        }
        existing_texts = [
            _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        item.get("claim"),
                        item.get("quote_span"),
                        item.get("raw_row_text"),
                    )
                )
            )
            for item in updated
            if isinstance(item, dict)
        ]

        def _content_terms(text: str) -> set[str]:
            return {
                term.lower()
                for term in self._narrative_context_terms(text)
                if len(term) >= 3
            }

        def _sentence_already_supported(sentence: str) -> bool:
            sentence_terms = _content_terms(sentence)
            if not sentence_terms:
                return True
            sentence_lower = sentence.lower()
            for existing in existing_texts:
                existing_lower = existing.lower()
                if sentence_lower and sentence_lower in existing_lower:
                    return True
                existing_terms = _content_terms(existing)
                if not existing_terms:
                    continue
                overlap = sentence_terms & existing_terms
                if len(overlap) >= max(2, min(len(sentence_terms), len(existing_terms)) // 2):
                    return True
            return False

        def _supporting_doc_quote(page_content: str, target_sentence: str) -> str:
            content = _normalise_spaces(page_content)
            target = _normalise_spaces(target_sentence)
            if not content or not target:
                return content[:700]
            content_lower = content.lower()
            target_lower = target.lower()
            exact_index = content_lower.find(target_lower)
            if exact_index >= 0:
                start = max(0, exact_index - 120)
                end = min(len(content), exact_index + len(target) + 220)
                return _normalise_spaces(content[start:end])
            target_terms = _content_terms(target)
            best_sentence = ""
            best_score = 0
            for sentence in _split_narrative_sentences(content):
                cleaned_sentence = _normalise_spaces(sentence)
                if not cleaned_sentence:
                    continue
                sentence_terms = _content_terms(cleaned_sentence)
                score = len(target_terms & sentence_terms)
                if score > best_score:
                    best_sentence = cleaned_sentence
                    best_score = score
            if best_sentence:
                return best_sentence[:700]
            return content[:700]

        doc_rows: List[Dict[str, Any]] = []
        for item in docs or []:
            doc = item[0] if isinstance(item, (tuple, list)) and item else item
            page_content = _normalise_spaces(
                str(getattr(doc, "page_content", None) or getattr(doc, "content", None) or "")
            )
            if not page_content:
                continue
            metadata = dict(getattr(doc, "metadata", {}) or {})
            source_anchor = _normalise_spaces(
                str(
                    metadata.get("source_anchor")
                    or metadata.get("section_path")
                    or metadata.get("section_title")
                    or metadata.get("section")
                    or ""
                )
            )
            doc_rows.append(
                {
                    "page_content": page_content,
                    "metadata": metadata,
                    "source_anchor": source_anchor,
                    "terms": _content_terms(page_content),
                }
            )

        for sentence in _split_narrative_sentences(answer_text):
            cleaned = _normalise_spaces(sentence)
            sentence_terms = _content_terms(cleaned)
            if not cleaned or not sentence_terms or _sentence_already_supported(cleaned):
                continue
            if self._text_supports_final_answer_numeric_material(cleaned, answer_numeric_candidates):
                continue
            scored_docs: List[tuple[int, Dict[str, Any]]] = []
            for row in doc_rows:
                doc_terms = set(row.get("terms") or set())
                overlap = sentence_terms & doc_terms
                exact_bonus = 4 if cleaned.lower() in str(row.get("page_content") or "").lower() else 0
                score = len(overlap) + exact_bonus
                if score:
                    scored_docs.append((score, row))
            scored_docs.sort(key=lambda item: item[0], reverse=True)
            if not scored_docs:
                continue
            best_score, best_doc = scored_docs[0]
            min_score = max(2, min(4, len(sentence_terms) // 2 or 1))
            if best_score < min_score:
                continue
            evidence_id = f"retrieved_narrative::{len(selected_ids) + 1:03d}"
            while evidence_id in existing_ids:
                evidence_id = f"retrieved_narrative::{len(selected_ids) + len(existing_ids) + 1:03d}"
            existing_ids.add(evidence_id)
            selected_ids.append(evidence_id)
            updated.append(
                {
                    "evidence_id": evidence_id,
                    "source_anchor": best_doc.get("source_anchor") or "",
                    "claim": cleaned,
                    "quote_span": _supporting_doc_quote(str(best_doc.get("page_content") or ""), cleaned),
                    "support_level": "direct",
                    "question_relevance": "high",
                    "metadata": dict(best_doc.get("metadata") or {}),
                }
            )
        return updated, selected_ids

    def _filter_aggregate_projection_provenance(
        self,
        projection: Dict[str, Any],
        kept_evidence_ids: List[str],
    ) -> Dict[str, Any]:
        kept = {str(value).strip() for value in (kept_evidence_ids or []) if str(value).strip()}
        if not kept:
            return projection

        def _filter_ids(values: Any) -> List[str]:
            current = _clean_source_row_ids([values])
            return [
                value
                for value in current
                if not (value.startswith("ev_") or value.startswith("recon::")) or value in kept
            ]

        updated = dict(projection)
        calculation_result = dict(updated.get("calculation_result") or {})
        calculation_result["source_evidence_ids"] = _filter_ids(calculation_result.get("source_evidence_ids"))
        calculation_result["source_row_ids"] = _filter_ids(calculation_result.get("source_row_ids"))
        derived_metrics = dict(calculation_result.get("derived_metrics") or {})
        for key in ("aggregate_source_evidence_ids", "aggregate_source_row_ids"):
            if key in derived_metrics:
                derived_metrics[key] = _filter_ids(derived_metrics.get(key))
        calculation_result["derived_metrics"] = derived_metrics
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        if answer_slots:
            answer_slots["source_row_ids"] = _filter_ids(answer_slots.get("source_row_ids"))
            subtask_results: List[Dict[str, Any]] = []
            for subtask in list(answer_slots.get("subtask_results") or []):
                if not isinstance(subtask, dict):
                    continue
                row = dict(subtask)
                row["source_evidence_ids"] = _filter_ids(row.get("source_evidence_ids"))
                row["source_row_ids"] = _filter_ids(row.get("source_row_ids"))
                subtask_results.append(row)
            if subtask_results:
                answer_slots["subtask_results"] = subtask_results
            calculation_result["answer_slots"] = answer_slots
        updated["calculation_result"] = calculation_result
        return updated

    def _dependency_slot_matches_input(
        self,
        binding: Dict[str, Any],
        slot: Dict[str, Any],
        *,
        sibling_row: Dict[str, Any],
    ) -> bool:
        binding_concept = _normalise_spaces(str(binding.get("concept") or ""))
        slot_concept = _normalise_spaces(str(slot.get("concept") or ""))
        if binding_concept and slot_concept and binding_concept != slot_concept:
            return False

        binding_period = _normalise_spaces(str(binding.get("period") or ""))
        slot_period = _normalise_spaces(str(slot.get("period") or ""))
        if binding_period and slot_period and binding_period != slot_period:
            return False

        binding_label = _normalise_spaces(str(binding.get("label") or ""))
        slot_label = _normalise_spaces(str(slot.get("label") or ""))
        sibling_label = _normalise_spaces(str(sibling_row.get("metric_label") or ""))
        if binding_label and slot_label and binding_label != slot_label:
            if binding_label not in slot_label and binding_label not in sibling_label:
                return False

        binding_segment = _normalise_spaces(str(binding.get("segment_label") or ""))
        if binding_segment:
            label_text = " ".join(
                part
                for part in [
                    slot_label.lower(),
                    sibling_label.lower(),
                ]
                if part
            )
            if binding_segment.lower() not in label_text:
                return False

        return True

    def _infer_dependency_row_unit(
        self,
        slot: Dict[str, Any],
        sibling_result: Dict[str, Any],
    ) -> tuple[str, str]:
        raw_unit = _normalise_spaces(
            str(
                slot.get("raw_unit")
                or sibling_result.get("result_unit")
                or ""
            )
        )
        normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "UNKNOWN")).upper() or "UNKNOWN"
        if normalized_unit == "UNKNOWN":
            render_policy = dict(CALCULATION_RENDER_POLICY)
            if raw_unit in set(render_policy.get("percent_display_units") or ()):
                normalized_unit = "PERCENT"
            elif raw_unit in set(render_policy.get("krw_display_units") or ()):
                normalized_unit = str(render_policy.get("krw_normalized_unit") or "KRW").upper()
            elif raw_unit in set(render_policy.get("count_display_units") or ()):
                normalized_unit = "COUNT"
        return raw_unit, normalized_unit

    def _build_dependency_operand_rows(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        active_subtask = dict(state.get("active_subtask") or {})
        input_bindings = [dict(item) for item in (active_subtask.get("inputs") or [])]
        if not input_bindings:
            return []

        sibling_rows = {
            str(row.get("task_id") or "").strip(): dict(row)
            for row in (state.get("subtask_results") or [])
            if str(row.get("task_id") or "").strip()
        }
        evidence_by_id = {
            str(item.get("evidence_id") or "").strip(): dict(item)
            for row in sibling_rows.values()
            for item in list(row.get("runtime_evidence") or [])
            if str(item.get("evidence_id") or "").strip()
        }
        evidence_by_id.update(
            {
                str(item.get("evidence_id") or "").strip(): dict(item)
                for item in list(state.get("evidence_items") or [])
                if str(item.get("evidence_id") or "").strip()
            }
        )
        evidence_by_id.update(
            {
                str(item.get("evidence_id") or "").strip(): dict(item)
                for item in list(state.get("runtime_evidence") or [])
                if str(item.get("evidence_id") or "").strip()
            }
        )
        evidence_pool = list(evidence_by_id.values())
        dependency_rows: List[Dict[str, Any]] = []
        for index, binding in enumerate(input_bindings, start=1):
            source_preference = [
                _normalise_spaces(str(item or "")).lower()
                for item in (binding.get("source_preference") or [])
                if _normalise_spaces(str(item or ""))
            ]
            if "task_output" not in source_preference:
                continue
            preferred_task_id = _normalise_spaces(str(binding.get("preferred_task_id") or ""))
            if not preferred_task_id:
                continue
            sibling_row = sibling_rows.get(preferred_task_id)
            if not sibling_row:
                continue
            sibling_result = dict(sibling_row.get("calculation_result") or {})
            answer_slots = dict(sibling_result.get("answer_slots") or {})
            source_slot_name = _normalise_spaces(str(binding.get("source_slot") or "primary_value")) or "primary_value"
            source_slot = dict(answer_slots.get(source_slot_name) or {})
            source_slot_from_answer_slots = self._answer_slot_has_material(source_slot)
            if not self._answer_slot_has_material(source_slot):
                producer_task = self._producer_task_for_dependency_binding(state, binding)
                if not producer_task:
                    producer_task = {
                        "task_id": preferred_task_id,
                        "metric_family": sibling_row.get("metric_family") or "concept_lookup",
                        "metric_label": sibling_row.get("metric_label") or binding.get("label") or "",
                        "operation_family": "lookup",
                        "required_operands": [dict(binding)],
                    }
                synthetic_result = _synthesize_lookup_answer_slot_from_prose(
                    active_subtask=producer_task,
                    answer=_normalise_spaces(
                        str(
                            sibling_row.get("answer")
                            or sibling_result.get("formatted_result")
                            or sibling_result.get("rendered_value")
                            or ""
                        )
                    ),
                    calculation_result=sibling_result,
                    selected_claim_ids=[
                        str(claim_id).strip()
                        for claim_id in (sibling_row.get("selected_claim_ids") or [])
                        if str(claim_id).strip()
                    ],
                )
                if synthetic_result:
                    sibling_result = synthetic_result
                    answer_slots = dict(sibling_result.get("answer_slots") or {})
                    source_slot = dict(answer_slots.get(source_slot_name) or answer_slots.get("primary_value") or {})
            if not self._answer_slot_has_material(source_slot) and sibling_result.get("result_value") is not None:
                source_slot = {
                    "status": "ok",
                    "role": source_slot_name,
                    "label": _normalise_spaces(str(binding.get("label") or sibling_row.get("metric_label") or "")),
                    "concept": _normalise_spaces(str(binding.get("concept") or "")),
                    "period": _normalise_spaces(str(binding.get("period") or "")),
                    "raw_value": _normalise_spaces(
                        str(sibling_result.get("rendered_value") or sibling_result.get("result_value") or "")
                    ),
                    "raw_unit": _normalise_spaces(str(sibling_result.get("result_unit") or "")),
                    "normalized_value": sibling_result.get("result_value"),
                    "normalized_unit": _normalise_spaces(str(sibling_result.get("normalized_unit") or "UNKNOWN")).upper()
                    or "UNKNOWN",
                    "rendered_value": _normalise_spaces(
                        str(sibling_result.get("rendered_value") or sibling_result.get("result_value") or "")
                    ),
                    "source_anchor": _normalise_spaces(str(sibling_result.get("source_anchor") or "")),
                    "source_row_ids": list(sibling_result.get("source_row_ids") or []),
                }
            if not self._answer_slot_has_material(source_slot):
                continue
            if not self._dependency_slot_matches_input(binding, source_slot, sibling_row=sibling_row):
                continue
            source_slot_from_answer_slots = True
            current_evidence = self._evidence_item_for_operand_row(source_slot, evidence_by_id)
            current_score = (
                self._direct_structured_lookup_evidence_score(binding, current_evidence)
                if current_evidence
                else 0.0
            )
            preferred_slot: Dict[str, Any] = {}
            preferred_score = 0.0
            if source_slot_from_answer_slots and "retrieval" in source_preference:
                source_raw_number = _parse_number_text(str(source_slot.get("raw_value") or ""))
                preferred_raw_number = None
                candidate_slot, candidate_score = self._best_direct_lookup_slot_from_evidence_pool_compat(
                    binding,
                    evidence_pool,
                    state=state,
                )
                def _candidate_slot_has_sibling_input_context(slot: Dict[str, Any]) -> bool:
                    candidate_evidence = self._evidence_item_for_operand_row(slot, evidence_by_id)
                    if not candidate_evidence:
                        return False
                    candidate_metadata = dict(candidate_evidence.get("metadata") or {})
                    table_surface = _normalise_spaces(
                        " ".join(
                            str(value or "")
                            for value in (
                                candidate_metadata.get("table_value_labels_text"),
                                candidate_metadata.get("table_row_labels_text"),
                                candidate_evidence.get("claim"),
                                candidate_evidence.get("quote_span"),
                                candidate_evidence.get("raw_row_text"),
                            )
                        )
                    )
                    if not table_surface:
                        return False
                    table_surface_compact = re.sub(r"\s+", "", table_surface)
                    binding_identity = self._dependency_binding_identity(binding)
                    for other_binding in input_bindings:
                        other_identity = self._dependency_binding_identity(other_binding)
                        if other_identity == binding_identity:
                            continue
                        sibling_surfaces = [
                            _normalise_spaces(str(surface or ""))
                            for surface in (
                                [other_binding.get("label")]
                                + list(other_binding.get("aliases") or [])
                                + list((other_binding.get("surface_contract") or {}).get("positive") or [])
                            )
                            if _normalise_spaces(str(surface or ""))
                        ]
                        if any(
                            surface in table_surface
                            or re.sub(r"\s+", "", surface) in table_surface_compact
                            for surface in sibling_surfaces
                        ):
                            return True
                    return False
                sibling_candidate_slot: Dict[str, Any] = {}
                sibling_candidate_score = 0.0
                for evidence_item in evidence_pool:
                    evidence = dict(evidence_item or {})
                    table_label_slot = self._lookup_value_from_table_label_metadata(binding, evidence)
                    table_label_score = self._table_label_metadata_lookup_score(table_label_slot, evidence)
                    if (
                        table_label_slot
                        and table_label_score > sibling_candidate_score
                        and _candidate_slot_has_sibling_input_context(table_label_slot)
                    ):
                        sibling_candidate_slot = table_label_slot
                        sibling_candidate_score = table_label_score
                if sibling_candidate_slot:
                    candidate_slot = sibling_candidate_slot
                    candidate_score = sibling_candidate_score
                if candidate_slot:
                    preferred_raw_number = _parse_number_text(str(candidate_slot.get("raw_value") or ""))
                candidate_has_sibling_context = bool(candidate_slot) and _candidate_slot_has_sibling_input_context(candidate_slot)
                allow_preferred_slot_lookup = (
                    bool(candidate_slot)
                    and source_raw_number is not None
                    and preferred_raw_number is not None
                    and (
                        abs(float(source_raw_number) - float(preferred_raw_number)) <= 1e-6
                        or candidate_has_sibling_context
                    )
                )
                if allow_preferred_slot_lookup:
                    preferred_slot, preferred_score = candidate_slot, candidate_score
                    if candidate_has_sibling_context and preferred_score <= current_score:
                        preferred_score = current_score + 0.1
            else:
                preferred_slot, preferred_score = self._best_direct_lookup_slot_from_evidence_pool_compat(
                    binding,
                    evidence_pool,
                    state=state,
                )
            if preferred_slot and preferred_score > current_score:
                preferred_raw = _normalise_spaces(str(preferred_slot.get("raw_value") or ""))
                current_raw = _normalise_spaces(str(source_slot.get("raw_value") or ""))
                preferred_unit = _normalise_spaces(str(preferred_slot.get("raw_unit") or ""))
                current_unit = _normalise_spaces(str(source_slot.get("raw_unit") or ""))
                preferred_normalized = preferred_slot.get("normalized_value")
                current_normalized = source_slot.get("normalized_value")
                normalized_differs = False
                try:
                    if preferred_normalized is not None and current_normalized is not None:
                        normalized_differs = abs(float(preferred_normalized) - float(current_normalized)) > 1e-6
                    else:
                        normalized_differs = preferred_normalized != current_normalized
                except (TypeError, ValueError):
                    normalized_differs = preferred_normalized != current_normalized
                if preferred_raw and (
                    preferred_raw != current_raw
                    or preferred_unit != current_unit
                    or normalized_differs
                ):
                    source_slot = preferred_slot
            raw_unit, normalized_unit = self._infer_dependency_row_unit(source_slot, sibling_result)
            normalized_value = source_slot.get("normalized_value")
            if normalized_value is None:
                normalized_value = sibling_result.get("result_value")
            matched_operand_candidate: Dict[str, Any] = {}
            for operand_row in list(sibling_row.get("calculation_operands") or []):
                operand_candidate = dict(operand_row or {})
                if not _operand_row_matches_requirement(operand_candidate, binding):
                    continue
                candidate_normalized = operand_candidate.get("normalized_value")
                candidate_raw = _normalise_spaces(str(operand_candidate.get("raw_value") or ""))
                slot_raw = _normalise_spaces(str(source_slot.get("raw_value") or source_slot.get("rendered_value") or ""))
                values_match = False
                try:
                    if normalized_value is not None and candidate_normalized is not None:
                        values_match = abs(float(normalized_value) - float(candidate_normalized)) <= 1e-6
                except (TypeError, ValueError):
                    values_match = False
                if not values_match and candidate_raw and slot_raw:
                    values_match = candidate_raw == slot_raw
                if values_match or not matched_operand_candidate:
                    matched_operand_candidate = operand_candidate
                if values_match:
                    break
            if matched_operand_candidate:
                candidate_normalized = matched_operand_candidate.get("normalized_value")
                candidate_raw = _normalise_spaces(str(matched_operand_candidate.get("raw_value") or ""))
                slot_raw = _normalise_spaces(str(source_slot.get("raw_value") or source_slot.get("rendered_value") or ""))
                candidate_conflicts = False
                try:
                    if normalized_value is not None and candidate_normalized is not None:
                        candidate_conflicts = abs(float(normalized_value) - float(candidate_normalized)) > 1e-6
                except (TypeError, ValueError):
                    candidate_conflicts = False
                if not candidate_conflicts and candidate_raw and slot_raw:
                    candidate_conflicts = candidate_raw != slot_raw
                if candidate_conflicts and (candidate_normalized is not None or candidate_raw):
                    updated_slot = dict(source_slot)
                    for key in (
                        "label",
                        "concept",
                        "period",
                        "raw_value",
                        "raw_unit",
                        "normalized_value",
                        "normalized_unit",
                        "rendered_value",
                        "source_row_id",
                        "source_row_ids",
                        "source_anchor",
                        "consolidation_scope",
                        "statement_type",
                        "table_source_id",
                    ):
                        value = matched_operand_candidate.get(key)
                        if value not in (None, "", []):
                            updated_slot[key] = value
                    updated_slot["status"] = updated_slot.get("status") or "ok"
                    updated_slot["role"] = (
                        updated_slot.get("role")
                        or matched_operand_candidate.get("matched_operand_role")
                        or binding.get("role")
                        or source_slot_name
                    )
                    source_slot = updated_slot
                    raw_unit, normalized_unit = self._infer_dependency_row_unit(source_slot, sibling_result)
                    normalized_value = source_slot.get("normalized_value")
                    if normalized_value is None:
                        normalized_value = sibling_result.get("result_value")
            source_row_ids = _clean_source_row_ids([
                f"task_output:{preferred_task_id}",
                source_slot.get("source_row_id"),
                source_slot.get("source_row_ids"),
                matched_operand_candidate.get("source_row_id"),
                matched_operand_candidate.get("source_row_ids"),
                sibling_result.get("source_row_ids"),
            ])
            source_anchor = _normalise_spaces(str(source_slot.get("source_anchor") or ""))
            if not source_anchor:
                for evidence_id in source_row_ids:
                    if str(evidence_id).startswith("task_output:"):
                        continue
                    evidence = evidence_by_id.get(evidence_id)
                    if not evidence:
                        continue
                    source_anchor = _normalise_spaces(str(evidence.get("source_anchor") or ""))
                    if source_anchor:
                        break
            if not source_anchor:
                source_anchor = _normalise_spaces(str(matched_operand_candidate.get("source_anchor") or ""))
            if not source_anchor:
                source_anchor = _normalise_spaces(str(sibling_result.get("source_anchor") or ""))
            dependency_row = {
                "operand_id": f"dep_{preferred_task_id}_{index:03d}",
                "evidence_id": f"task_output:{preferred_task_id}",
                "source_row_id": source_row_ids[0] if source_row_ids else f"task_output:{preferred_task_id}",
                "source_row_ids": source_row_ids or [f"task_output:{preferred_task_id}"],
                "source_anchor": source_anchor,
                "label": _normalise_spaces(
                    str(binding.get("label") or source_slot.get("label") or sibling_row.get("metric_label") or "")
                ),
                "raw_value": _normalise_spaces(
                    str(
                        source_slot.get("raw_value")
                        or source_slot.get("rendered_value")
                        or sibling_result.get("rendered_value")
                        or ""
                    )
                ),
                "raw_unit": raw_unit,
                "normalized_value": normalized_value,
                "normalized_unit": normalized_unit,
                "period": _normalise_spaces(str(source_slot.get("period") or binding.get("period") or "")),
                "consolidation_scope": _normalise_spaces(
                    str(source_slot.get("consolidation_scope") or matched_operand_candidate.get("consolidation_scope") or "")
                ),
                "statement_type": _normalise_spaces(
                    str(source_slot.get("statement_type") or matched_operand_candidate.get("statement_type") or "")
                ),
                "table_source_id": _normalise_spaces(
                    str(source_slot.get("table_source_id") or matched_operand_candidate.get("table_source_id") or "")
                ),
                "matched_operand_label": _normalise_spaces(str(binding.get("label") or "")),
                "matched_operand_concept": _normalise_spaces(str(binding.get("concept") or "")),
                "matched_operand_role": _normalise_spaces(str(binding.get("role") or "")),
                "source_task_id": preferred_task_id,
                "source_slot": source_slot_name,
                "dependency_resolved": True,
            }
            structured_provenance = self._structured_graph_provenance_for_dependency_operand(
                state,
                binding=binding,
                row=dependency_row,
            )
            if structured_provenance:
                structured_anchor = _normalise_spaces(str(structured_provenance.get("source_anchor") or ""))
                structured_chunk_uid = _normalise_spaces(str(structured_provenance.get("chunk_uid") or ""))
                if structured_anchor:
                    dependency_row["source_anchor"] = structured_anchor
                if structured_chunk_uid:
                    dependency_row["source_row_ids"] = _clean_source_row_ids([
                        dependency_row.get("source_row_ids"),
                        structured_chunk_uid,
                    ])
                for key in ("consolidation_scope", "statement_type", "table_source_id"):
                    value = _normalise_spaces(str(structured_provenance.get(key) or ""))
                    if value:
                        dependency_row[key] = value
            source_evidence = self._evidence_item_for_operand_row(dependency_row, evidence_by_id)
            dependency_rows.append(self._coerce_operand_row_from_evidence(dependency_row, source_evidence))
        return dependency_rows

    def _structured_graph_provenance_for_dependency_operand(
        self,
        state: FinancialAgentState,
        *,
        binding: Dict[str, Any],
        row: Dict[str, Any],
    ) -> Dict[str, Any]:
        graph = getattr(getattr(self, "vsm", None), "_structure_graph", {}) or {}
        nodes = dict(graph.get("nodes", {}) or {})
        if not nodes:
            return {}
        raw_value = _normalise_spaces(str(row.get("raw_value") or ""))
        if not raw_value:
            return {}
        raw_value_variants = {
            raw_value,
            re.sub(r"[,\s()]", "", raw_value),
            raw_value.replace("△", "-"),
        }
        raw_value_variants = {item for item in raw_value_variants if item}
        report_scope = dict(state.get("report_scope") or {})
        desired_scope = _desired_consolidation_scope(str(state.get("query") or ""), report_scope)
        preferred_statement_types = set(self._producer_statement_types_for_dependency_binding(state, binding))
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        note_markers = tuple(str(item).lower() for item in (scoring_policy.get("note_context_markers") or ()) if str(item))
        best_payload: Dict[str, Any] = {}
        best_score = -1
        for chunk_uid, node in nodes.items():
            node_data = dict(node or {})
            metadata = dict(node_data.get("metadata") or {})
            if report_scope.get("rcept_no") and str(metadata.get("rcept_no") or "") != str(report_scope.get("rcept_no")):
                continue
            if report_scope.get("year") and str(metadata.get("year") or "") != str(report_scope.get("year")):
                continue
            surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        metadata.get("table_value_labels_text"),
                        metadata.get("table_row_labels_text"),
                        node_data.get("text"),
                    )
                )
            )
            if not surface:
                continue
            compact_surface = re.sub(r"[,\s()]", "", surface)
            if not any(value in surface or value in compact_surface for value in raw_value_variants):
                continue
            if not _operand_text_match(surface, binding):
                continue
            node_scope = _normalise_spaces(str(metadata.get("consolidation_scope") or ""))
            if desired_scope in {"consolidated", "separate"} and node_scope and node_scope != desired_scope:
                continue
            score = 10
            statement_type = _normalise_spaces(str(metadata.get("statement_type") or ""))
            if statement_type and statement_type in preferred_statement_types:
                score += 6
            elif preferred_statement_types and statement_type == "notes":
                score -= 4
            if node_scope and node_scope == desired_scope:
                score += 4
            section_path = _normalise_spaces(str(metadata.get("section_path") or ""))
            section_path_lower = section_path.lower()
            if section_path and not any(marker in section_path_lower for marker in note_markers) and "note" not in section_path_lower:
                score += 2
            if score <= best_score:
                continue
            payload = {
                "source_anchor": self._build_source_anchor(metadata),
                "chunk_uid": str(chunk_uid),
                "consolidation_scope": node_scope,
                "statement_type": statement_type,
                "table_source_id": _normalise_spaces(str(metadata.get("table_source_id") or "")),
            }
            if not payload["source_anchor"]:
                continue
            best_payload = payload
            best_score = score
        return best_payload

    def _active_retry_strategy(self, state: FinancialAgentState) -> str:
        for candidate in (
            state.get("retry_strategy"),
            dict(state.get("reconciliation_result") or {}).get("retry_strategy"),
            dict(state.get("reflection_plan") or {}).get("retry_strategy"),
        ):
            cleaned = _normalise_spaces(str(candidate or "")).lower()
            if cleaned:
                return cleaned
        return ""

    def _task_prefers_sibling_output_synthesis(self, state: FinancialAgentState) -> bool:
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = _normalise_spaces(str(active_subtask.get("operation_family") or "")).lower()
        if operation_family not in {"difference", "growth_rate", "ratio", "sum"}:
            return False
        for binding in (active_subtask.get("inputs") or []):
            binding_data = dict(binding)
            source_preference = [
                _normalise_spaces(str(item or "")).lower()
                for item in (binding_data.get("source_preference") or [])
                if _normalise_spaces(str(item or ""))
            ]
            if "task_output" in source_preference and _normalise_spaces(str(binding_data.get("preferred_task_id") or "")):
                return True
        return False

    def _task_output_input_bindings(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        active_subtask = dict(state.get("active_subtask") or {})
        bindings: List[Dict[str, Any]] = []
        for binding in (active_subtask.get("inputs") or []):
            binding_data = dict(binding)
            source_preference = [
                _normalise_spaces(str(item or "")).lower()
                for item in (binding_data.get("source_preference") or [])
                if _normalise_spaces(str(item or ""))
            ]
            if "task_output" not in source_preference:
                continue
            if not _normalise_spaces(str(binding_data.get("preferred_task_id") or "")):
                continue
            bindings.append(binding_data)
        return bindings

    def _dependency_binding_resolution_state(self, state: FinancialAgentState) -> Dict[str, Any]:
        dependency_bindings = self._task_output_input_bindings(state)
        dependency_rows = self._build_dependency_operand_rows(state)
        dependency_binding_keys = {
            self._dependency_binding_identity(binding)
            for binding in dependency_bindings
            if any(self._dependency_binding_identity(binding))
        }
        resolved_dependency_keys = {
            (
                _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or "")),
                _normalise_spaces(str(row.get("matched_operand_role") or "")),
            )
            for row in dependency_rows
        }
        missing_dependency_bindings = [
            dict(binding)
            for binding in dependency_bindings
            if self._dependency_binding_identity(binding) not in resolved_dependency_keys
        ]
        resolved_binding_count = max(len(dependency_bindings) - len(missing_dependency_bindings), 0)
        return {
            "bindings": dependency_bindings,
            "rows": dependency_rows,
            "binding_keys": dependency_binding_keys,
            "resolved_keys": resolved_dependency_keys,
            "missing_bindings": missing_dependency_bindings,
            "binding_count": len(dependency_bindings),
            "resolved_binding_count": resolved_binding_count,
            "has_bindings": bool(dependency_bindings),
            "has_rows": bool(dependency_rows),
            "all_resolved": bool(dependency_bindings) and not missing_dependency_bindings and bool(dependency_rows),
        }

    def _direct_rows_resolved_dependency_keys(
        self,
        bindings: List[Dict[str, Any]],
        operand_rows: List[Dict[str, Any]],
    ) -> set[tuple[str, str]]:
        resolved_keys: set[tuple[str, str]] = set()
        for binding in bindings:
            binding_key = self._dependency_binding_identity(binding)
            if not any(binding_key):
                continue
            if any(_operand_row_matches_requirement(row, binding) for row in (operand_rows or [])):
                resolved_keys.add(binding_key)
        return resolved_keys

    def _producer_task_for_dependency_binding(
        self,
        state: FinancialAgentState,
        binding: Dict[str, Any],
    ) -> Dict[str, Any]:
        preferred_task_id = _normalise_spaces(str(binding.get("preferred_task_id") or ""))
        if not preferred_task_id:
            return {}
        for task in list(state.get("calc_subtasks") or []):
            task_row = dict(task or {})
            if _normalise_spaces(str(task_row.get("task_id") or "")) == preferred_task_id:
                return task_row
        for task in list((dict(state.get("semantic_plan") or {}).get("tasks") or [])):
            task_row = dict(task or {})
            if _normalise_spaces(str(task_row.get("task_id") or "")) == preferred_task_id:
                return task_row
        return {}

    def _producer_statement_types_for_dependency_binding(
        self,
        state: FinancialAgentState,
        binding: Dict[str, Any],
    ) -> List[str]:
        producer_task = self._producer_task_for_dependency_binding(state, binding)
        if not producer_task:
            return []
        preferred_types: List[str] = []
        binding_role = _normalise_spaces(str(binding.get("role") or ""))
        binding_concept = _normalise_spaces(str(binding.get("concept") or ""))
        for operand in list(producer_task.get("required_operands") or []):
            operand_row = dict(operand or {})
            operand_role = _normalise_spaces(str(operand_row.get("role") or ""))
            operand_concept = _normalise_spaces(str(operand_row.get("concept") or ""))
            if binding_role and operand_role and binding_role != operand_role:
                continue
            if binding_concept and operand_concept and binding_concept != operand_concept:
                continue
            preferred_types.extend(
                _normalise_spaces(str(item))
                for item in list(operand_row.get("preferred_statement_types") or [])
                if _normalise_spaces(str(item))
            )
        preferred_types.extend(
            _normalise_spaces(str(item))
            for item in list(producer_task.get("preferred_statement_types") or [])
            if _normalise_spaces(str(item))
        )
        return list(dict.fromkeys(preferred_types))

    def _producer_sections_for_dependency_binding(
        self,
        state: FinancialAgentState,
        binding: Dict[str, Any],
    ) -> List[str]:
        producer_task = self._producer_task_for_dependency_binding(state, binding)
        if not producer_task:
            return []
        preferred_sections: List[str] = []
        binding_role = _normalise_spaces(str(binding.get("role") or ""))
        binding_concept = _normalise_spaces(str(binding.get("concept") or ""))
        for operand in list(producer_task.get("required_operands") or []):
            operand_row = dict(operand or {})
            operand_role = _normalise_spaces(str(operand_row.get("role") or ""))
            operand_concept = _normalise_spaces(str(operand_row.get("concept") or ""))
            if binding_role and operand_role and binding_role != operand_role:
                continue
            if binding_concept and operand_concept and binding_concept != operand_concept:
                continue
            preferred_sections.extend(
                _normalise_spaces(str(item))
                for item in list(operand_row.get("preferred_sections") or [])
                if _normalise_spaces(str(item))
            )
        preferred_sections.extend(
            _normalise_spaces(str(item))
            for item in list(producer_task.get("preferred_sections") or [])
            if _normalise_spaces(str(item))
        )
        return list(dict.fromkeys(preferred_sections))

    def _dependency_row_violates_producer_scope(
        self,
        row: Dict[str, Any],
        *,
        preferred_statement_types: List[str],
        preferred_sections: List[str],
    ) -> tuple[bool, str]:
        row_statement_type = _normalise_spaces(str(row.get("statement_type") or ""))
        if (
            preferred_statement_types
            and row_statement_type
            and row_statement_type not in preferred_statement_types
        ):
            return True, "statement_type"

        row_scope_text = _normalise_spaces(
            " ".join(
                str(row.get(key) or "")
                for key in ("source_anchor", "table_source_id", "source_context")
            )
        ).lower()
        if not row_scope_text:
            return False, ""
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        note_markers = tuple(str(item).lower() for item in (scoring_policy.get("note_context_markers") or ()) if str(item))
        row_is_note_scoped = any(marker in row_scope_text for marker in note_markers) or "note" in row_scope_text
        producer_allows_notes = (
            "notes" in preferred_statement_types
            or any(
                any(marker in _normalise_spaces(str(section)).lower() for marker in note_markers)
                or "note" in _normalise_spaces(str(section)).lower()
                for section in preferred_sections
            )
        )
        if row_is_note_scoped and not producer_allows_notes:
            return True, "section_scope"
        return False, ""

    def _filter_direct_rows_by_dependency_producer_scope(
        self,
        state: FinancialAgentState,
        *,
        bindings: List[Dict[str, Any]],
        operand_rows: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not bindings or not operand_rows:
            return list(operand_rows or []), []
        filtered_rows: List[Dict[str, Any]] = []
        rejected_rows: List[Dict[str, Any]] = []
        for row in list(operand_rows or []):
            row_data = dict(row or {})
            matching_binding = next(
                (
                    dict(binding)
                    for binding in bindings
                    if _operand_row_matches_requirement(row_data, dict(binding))
                ),
                {},
            )
            if not matching_binding:
                filtered_rows.append(row_data)
                continue
            preferred_statement_types = self._producer_statement_types_for_dependency_binding(
                state,
                matching_binding,
            )
            preferred_sections = self._producer_sections_for_dependency_binding(
                state,
                matching_binding,
            )
            violates_scope, reject_reason = self._dependency_row_violates_producer_scope(
                row_data,
                preferred_statement_types=preferred_statement_types,
                preferred_sections=preferred_sections,
            )
            if violates_scope:
                rejected_rows.append(
                    {
                        "binding": matching_binding,
                        "row": row_data,
                        "reject_reason": reject_reason,
                        "preferred_statement_types": preferred_statement_types,
                        "preferred_sections": preferred_sections,
                        "row_statement_type": _normalise_spaces(str(row_data.get("statement_type") or "")),
                    }
                )
                continue
            filtered_rows.append(row_data)
        return filtered_rows, rejected_rows

    def _dependency_binding_identity(self, binding: Dict[str, Any]) -> tuple[str, str]:
        return (
            _normalise_spaces(str(binding.get("label") or "")),
            _normalise_spaces(str(binding.get("role") or "")),
        )

    def _material_gap_feedback_for_subtask_result(self, row: Dict[str, Any]) -> str:
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
                if not self._material_gap_feedback_for_subtask_result(dict(nested_row)):
                    return ""

        if operation_family in {"lookup", "single_value"}:
            if not self._answer_slot_has_material(dict(answer_slots.get("primary_value") or {})):
                return str(feedback_policy.get("lookup_missing_template") or "").format(metric_label=metric_label)
            return ""

        if operation_family in {"difference", "growth_rate"}:
            current_slot = dict(answer_slots.get("current_value") or {})
            prior_slot = dict(answer_slots.get("prior_value") or {})
            primary_slot = dict(answer_slots.get("primary_value") or {})
            missing_labels: List[str] = []
            if not self._answer_slot_has_material(current_slot):
                period = str(
                    current_slot.get("period")
                    or calculation_result.get("current_period")
                    or feedback_policy.get("default_current_period")
                    or ""
                )
                missing_labels.append(
                    str(feedback_policy.get("missing_period_value_template") or "").format(period=period)
                )
            if not self._answer_slot_has_material(prior_slot):
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
                if not self._answer_slot_has_material(dict(answer_slots.get("delta_value") or primary_slot)):
                    missing_labels.append(str(feedback_policy.get("difference_missing_result_label") or ""))
            else:
                if not self._answer_slot_has_material(primary_slot):
                    if not (status == "ok" and rendered_material and re.search(r"\d", rendered_material)):
                        missing_labels.append(str(feedback_policy.get("growth_missing_result_label") or ""))
            if missing_labels:
                return str(feedback_policy.get("missing_material_template") or "").format(
                    metric_label=metric_label,
                    missing_labels=str(feedback_policy.get("missing_material_joiner") or "").join(missing_labels),
                )
            return ""

        if operation_family in {"ratio", "sum"}:
            if not self._answer_slot_has_material(dict(answer_slots.get("primary_value") or {})):
                if status == "ok" and rendered_material and re.search(r"\d", rendered_material):
                    return ""
                return str(feedback_policy.get("missing_result_template") or "").format(metric_label=metric_label)
            return ""

        return ""

    def _infer_planner_feedback_from_answer_slots(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        for row in ordered_results:
            operation_family = self._aggregate_result_operation_family(row)
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            status = str(
                row.get("status")
                or (row.get("calculation_result") or {}).get("status")
                or ""
            ).strip().lower()
            if (
                (operation_family == "narrative_summary" or metric_family == "narrative_summary")
                and _normalise_spaces(str(row.get("answer") or ""))
                and re.search(r"\d", str(row.get("answer") or ""))
            ):
                continue
            if status and status != "ok":
                if (
                    self._sibling_lookup_gap_is_satisfied(row, ordered_results)
                    or self._lookup_gap_is_satisfied_by_sibling_slots(row, ordered_results)
                ):
                    continue
                gap = self._material_gap_feedback_for_subtask_result(row)
                if gap:
                    if self._feedback_gap_is_satisfied_by_derived_slots(gap, ordered_results):
                        continue
                    return gap
                metric_label = _normalise_spaces(
                    str(
                        row.get("metric_label")
                        or row.get("task_id")
                        or CALCULATION_FEEDBACK_POLICY.get("default_metric_label")
                        or ""
                    )
                )
                generic_gap = str(CALCULATION_FEEDBACK_POLICY.get("generic_missing_material_template") or "").format(
                    metric_label=metric_label
                )
                if self._feedback_gap_is_satisfied_by_derived_slots(generic_gap, ordered_results):
                    continue
                return generic_gap

            gap = self._material_gap_feedback_for_subtask_result(row)
            if gap and (
                self._sibling_lookup_gap_is_satisfied(row, ordered_results)
                or self._lookup_gap_is_satisfied_by_sibling_slots(row, ordered_results)
                or self._feedback_gap_is_satisfied_by_derived_slots(gap, ordered_results)
            ):
                continue
            if gap:
                return gap
        return ""

    def _aggregate_result_operation_family(self, row: Dict[str, Any]) -> str:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        operation_family = _normalise_spaces(
            str(
                row.get("operation_family")
                or answer_slots.get("operation_family")
                or (row.get("calculation_plan") or {}).get("operation")
                or ""
            )
        ).lower()
        if not operation_family:
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if metric_family.startswith("concept_"):
                operation_family = metric_family.removeprefix("concept_")
        return operation_family

    def _aggregate_result_signature(self, row: Dict[str, Any]) -> str:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        metric_label = _normalise_spaces(
            str(
                row.get("metric_label")
                or answer_slots.get("metric_label")
                or row.get("task_id")
                or ""
            )
        )
        if not metric_label:
            return ""
        operation_family = self._aggregate_result_operation_family(row)
        if operation_family:
            return f"{operation_family}:{metric_label}"
        return metric_label

    def _aggregate_result_rank(self, row: Dict[str, Any]) -> tuple[int, int, int, int]:
        calculation_result = dict(row.get("calculation_result") or {})
        status = _normalise_spaces(
            str(
                row.get("status")
                or calculation_result.get("status")
                or ""
            )
        ).lower()
        status_rank = {
            "ok": 4,
            "partial": 3,
            "ready": 3,
            "insufficient_operands": 1,
            "retry_retrieval": 1,
            "missing": 0,
        }.get(status, 0)
        material_rank = 0 if self._material_gap_feedback_for_subtask_result(row) else 1
        answer_rank = 1 if _normalise_spaces(str(row.get("answer") or "")) else 0
        operand_rank = len(list(calculation_result.get("source_row_ids") or []))
        return status_rank, material_rank, answer_rank, operand_rank

    def _nested_aggregate_result_rank(self, row: Dict[str, Any]) -> tuple[int, int, int, int, int, int, int]:
        calculation_result = dict(row.get("calculation_result") or {})
        status = _normalise_spaces(
            str(row.get("status") or calculation_result.get("status") or "")
        ).lower()
        status_rank = {
            "ok": 4,
            "partial": 3,
            "ready": 3,
            "insufficient_operands": 1,
            "retry_retrieval": 1,
            "missing": 0,
        }.get(status, 0)
        material_rank = 1 if self._subtask_row_has_material(row) else 0
        gap_free_rank = 0 if self._material_gap_feedback_for_subtask_result(row) else 1
        operation_family = self._aggregate_result_operation_family(row)
        non_aggregate_rank = 0 if operation_family == "aggregate_subtasks" else 1
        source_count = len(_clean_source_row_ids([
            row.get("source_row_ids"),
            calculation_result.get("source_row_ids"),
            row.get("selected_claim_ids"),
            calculation_result.get("source_evidence_ids"),
        ]))
        answer_text = _normalise_spaces(
            str(
                row.get("answer")
                or calculation_result.get("formatted_result")
                or calculation_result.get("rendered_value")
                or ""
            )
        )
        digit_count = len(re.findall(r"\d", answer_text))
        return (
            status_rank,
            material_rank,
            gap_free_rank,
            non_aggregate_rank,
            source_count,
            digit_count,
            len(answer_text),
        )

    def _promote_stronger_nested_aggregate_results(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        by_task_id = {
            _normalise_spaces(str(row.get("task_id") or "")): dict(row)
            for row in ordered_results
            if _normalise_spaces(str(row.get("task_id") or ""))
        }
        replacements: Dict[str, Dict[str, Any]] = {}
        for row in ordered_results:
            if self._aggregate_result_operation_family(row) != "aggregate_subtasks":
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            for nested_row in self._nested_subtask_rows(calculation_result):
                nested_task_id = _normalise_spaces(str(nested_row.get("task_id") or ""))
                if not nested_task_id:
                    continue
                if self._aggregate_result_operation_family(nested_row) == "aggregate_subtasks":
                    continue
                current_row = replacements.get(nested_task_id) or by_task_id.get(nested_task_id)
                if not current_row:
                    continue
                if self._nested_aggregate_result_rank(nested_row) <= self._nested_aggregate_result_rank(current_row):
                    continue
                promoted = {
                    **dict(current_row),
                    **dict(nested_row),
                    "promoted_from_nested_aggregate": True,
                }
                for key in ("runtime_evidence", "artifact_ids", "selected_claim_ids", "source_evidence_ids"):
                    if not promoted.get(key) and current_row.get(key):
                        promoted[key] = current_row.get(key)
                replacements[nested_task_id] = promoted
        if not replacements:
            return ordered_results
        return [
            dict(replacements.get(_normalise_spaces(str(row.get("task_id") or ""))) or row)
            for row in ordered_results
        ]

    def _dedupe_aggregate_subtask_results(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        winners: Dict[str, tuple[int, tuple[int, int, int, int], Dict[str, Any]]] = {}
        passthrough: List[tuple[int, Dict[str, Any]]] = []
        for index, row in enumerate(ordered_results):
            signature = self._aggregate_result_signature(row)
            if not signature:
                passthrough.append((index, row))
                continue
            rank = self._aggregate_result_rank(row)
            incumbent = winners.get(signature)
            if incumbent is None or rank > incumbent[1] or (rank == incumbent[1] and index > incumbent[0]):
                winners[signature] = (index, rank, row)
        deduped = sorted(
            [item for item in winners.values()] + [(index, (0, 0, 0, 0), row) for index, row in passthrough],
            key=lambda item: item[0],
        )
        return [dict(item[2]) for item in deduped]

    def _narrative_context_terms(self, query: str) -> List[str]:
        tokens = re.findall(r"[가-힣A-Za-z0-9()]+", _normalise_spaces(str(query or "")))
        stopwords = {
            str(item)
            for item in (CALCULATION_NARRATIVE_POLICY.get("context_stopwords") or ())
            if str(item)
        }
        terms: List[str] = []
        for token in tokens:
            cleaned = token.strip()
            if len(cleaned) < 2 or cleaned in stopwords:
                continue
            if re.search(r"\d", cleaned):
                continue
            if re.fullmatch(r"\d+", cleaned):
                continue
            terms.append(cleaned)
        return list(dict.fromkeys(terms))

    def _narrative_focus_variants(self, query: str) -> List[str]:
        generic_terms = {
            _normalise_spaces(str(item)).lower()
            for item in (
                tuple(CALCULATION_NARRATIVE_POLICY.get("growth_generic_focus_terms") or ())
                + tuple(CALCULATION_NARRATIVE_POLICY.get("context_reuse_excluded_terms") or ())
            )
            if _normalise_spaces(str(item))
        }
        variants: List[str] = []
        for term in self._narrative_context_terms(query):
            cleaned = _normalise_spaces(str(term))
            if not cleaned or cleaned.lower() in generic_terms:
                continue
            candidates = [cleaned]
            candidates.extend(
                _normalise_spaces(match)
                for match in re.findall(r"\(([^)]+)\)", cleaned)
                if _normalise_spaces(match)
            )
            outside_parentheses = _normalise_spaces(re.sub(r"\([^)]*\)", " ", cleaned))
            if outside_parentheses:
                candidates.append(outside_parentheses)
            for candidate in candidates:
                if len(candidate) < 2:
                    continue
                if candidate.lower() in generic_terms:
                    continue
                variants.append(candidate)
        return list(dict.fromkeys(variants))

    def _parenthetical_focus_variants(self, query: str) -> List[str]:
        variants: List[str] = []
        for term in self._narrative_context_terms(query):
            cleaned = _normalise_spaces(str(term))
            if not cleaned or "(" not in cleaned:
                continue
            variants.extend(
                _normalise_spaces(match)
                for match in re.findall(r"\(([^)]+)\)", cleaned)
                if _normalise_spaces(match)
            )
            outside_parentheses = _normalise_spaces(re.sub(r"\([^)]*\)", " ", cleaned))
            if outside_parentheses:
                variants.append(outside_parentheses)
        return list(dict.fromkeys(variant for variant in variants if len(variant) >= 2))

    def _narrative_context_sentence_from_evidence(
        self,
        query: str,
        evidence_items: List[Dict[str, Any]],
    ) -> str:
        if not _query_requests_narrative_context(query):
            return ""
        query_terms = self._narrative_context_terms(query)
        if not query_terms:
            return ""

        best_score = 0
        best_sentence = ""
        for item in evidence_items or []:
            evidence = dict(item or {})
            source_text = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in [
                        evidence.get("source_anchor"),
                        (evidence.get("metadata") or {}).get("section_path"),
                        (evidence.get("metadata") or {}).get("section"),
                    ]
                )
            )
            claim = _normalise_spaces(
                str(
                    evidence.get("claim")
                    or evidence.get("quote_span")
                    or evidence.get("raw_row_text")
                    or ""
                )
            )
            if not claim:
                continue
            haystack = f"{source_text} {claim}".lower()
            term_score = sum(1 for term in query_terms if term.lower() in haystack)
            if any(
                str(term) in source_text
                for term in (CALCULATION_NARRATIVE_POLICY.get("context_priority_section_terms") or ())
            ):
                term_score += 2
            if str(evidence.get("support_level") or "").lower() in {
                str(item).lower()
                for item in (CALCULATION_NARRATIVE_POLICY.get("context_support_levels") or ())
                if str(item)
            }:
                term_score += 1
            if term_score <= best_score:
                continue
            best_score = term_score
            best_sentence = claim

        if best_score <= 0 or not best_sentence:
            return ""
        split_sentences = _split_narrative_sentences(best_sentence)
        best_sentence = split_sentences[0] if split_sentences else best_sentence
        return best_sentence[:220].rstrip()

    def _include_narrative_context_if_needed(
        self,
        answer: str,
        *,
        query: str,
        narrative_context: str,
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        context = _normalise_spaces(str(narrative_context or ""))
        if not answer_text or not context or not _query_requests_narrative_context(query):
            return answer_text
        key_terms = [
            term
            for term in self._narrative_context_terms(query)
            if term not in {
                str(item)
                for item in (CALCULATION_NARRATIVE_POLICY.get("context_reuse_excluded_terms") or ())
                if str(item)
            }
        ]
        context_terms = [term for term in key_terms if term in context]
        if context_terms and any(term in answer_text for term in context_terms):
            return answer_text
        if context in answer_text:
            return answer_text
        return _normalise_spaces(f"{context} {answer_text}")

    def _preserve_source_visible_query_terms(
        self,
        answer: str,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
        docs: List[Any],
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text:
            return answer_text

        marker_groups: List[List[str]] = []
        for group in self._query_focus_marker_groups(query):
            group_markers: List[str] = []
            for variant in group.get("variants") or []:
                marker = _normalise_spaces(str(variant or ""))
                if not marker:
                    continue
                if len(marker) > 32 or not re.search(r"[A-Z]", marker):
                    continue
                group_markers.append(marker)
            if group_markers:
                marker_groups.append(group_markers)
        marker_variants: List[str] = []
        for group in marker_groups:
            for marker in group:
                if marker.lower() not in {item.lower() for item in marker_variants}:
                    marker_variants.append(marker)
        if not marker_variants:
            return answer_text

        support_parts: List[str] = []
        for item in evidence_items or []:
            evidence = dict(item or {})
            metadata = dict(evidence.get("metadata") or {})
            support_parts.extend(
                str(value or "")
                for value in (
                    evidence.get("claim"),
                    evidence.get("quote_span"),
                    evidence.get("raw_row_text"),
                    " ".join(str(term or "") for term in (evidence.get("allowed_terms") or [])),
                    metadata.get("table_context"),
                    metadata.get("table_header_context"),
                    metadata.get("table_summary_text"),
                    metadata.get("text"),
                )
            )
        for row in ordered_results or []:
            calculation_result = dict(row.get("calculation_result") or {})
            support_parts.extend(
                str(value or "")
                for value in (
                    row.get("answer"),
                    row.get("metric_label"),
                    calculation_result.get("formatted_result"),
                    calculation_result.get("rendered_value"),
                )
            )
        for item in docs or []:
            doc = item[0] if isinstance(item, (tuple, list)) and item else item
            metadata = getattr(doc, "metadata", {}) or {}
            support_parts.extend(
                str(value or "")
                for value in (
                    getattr(doc, "page_content", ""),
                    metadata.get("table_context"),
                    metadata.get("table_header_context"),
                    metadata.get("table_summary_text"),
                    metadata.get("section_path"),
                    metadata.get("local_heading"),
                )
            )

        support_blob = _normalise_spaces(" ".join(part for part in support_parts if part)).lower()
        grounded_blob = _normalise_spaces(f"{answer_text} {support_blob}").lower()
        matched_concepts = get_financial_ontology().match_concepts(query)
        concept_surfaces_by_key: Dict[str, List[str]] = {}
        for concept in matched_concepts:
            concept_key = str(concept.get("key") or "").strip()
            if not concept_key:
                continue
            surfaces = [
                _normalise_spaces(str(surface or ""))
                for surface in [
                    concept.get("display_name"),
                    *(concept.get("aliases") or []),
                    *(concept.get("keywords") or []),
                ]
                if _normalise_spaces(str(surface or ""))
            ]
            if surfaces:
                concept_surfaces_by_key[concept_key] = list(dict.fromkeys(surfaces))

        def _marker_has_ontology_support(marker: str, siblings: List[str]) -> bool:
            marker_lower = marker.lower()
            sibling_lowers = [sibling.lower() for sibling in siblings if sibling]
            for surfaces in concept_surfaces_by_key.values():
                surface_lowers = [surface.lower() for surface in surfaces]
                if marker_lower not in surface_lowers and not any(
                    sibling and any(sibling in surface or surface in sibling for surface in surface_lowers)
                    for sibling in sibling_lowers
                ):
                    continue
                if any(surface != marker_lower and surface in grounded_blob for surface in surface_lowers):
                    return True
            return False

        answer_lower = answer_text.lower()
        missing_terms: List[str] = []
        for group in marker_groups:
            for marker in group:
                marker_lower = marker.lower()
                if marker_lower in answer_lower:
                    continue
                if marker_lower in support_blob or _marker_has_ontology_support(marker, group):
                    if marker_lower not in {item.lower() for item in missing_terms}:
                        missing_terms.append(marker)
        if not missing_terms:
            return answer_text
        template = str(CALCULATION_NARRATIVE_POLICY.get("source_visible_term_note_template") or "{terms}")
        addition = _normalise_spaces(template.format(terms=", ".join(missing_terms[:4])))
        if not addition or addition.lower() in answer_lower:
            return answer_text
        return _normalise_spaces(f"{answer_text} {addition}")

    def _preserve_retrieved_narrative_source_surface(
        self,
        answer: str,
        evidence_items: List[Dict[str, Any]],
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text or not evidence_items:
            return answer_text
        answer_numeric_candidates = self._answer_evidence_numeric_candidates(answer_text)
        sentences = [_normalise_spaces(sentence) for sentence in _split_narrative_sentences(answer_text)]
        if not sentences:
            return answer_text

        def _content_terms(text: str) -> set[str]:
            return {
                term.lower()
                for term in self._narrative_context_terms(text)
                if len(term) >= 3
            }

        replacements: Dict[str, str] = {}
        for item in evidence_items or []:
            evidence = dict(item or {})
            evidence_id = str(evidence.get("evidence_id") or "").strip()
            if not evidence_id.startswith("retrieved_narrative::"):
                continue
            claim = _normalise_spaces(str(evidence.get("claim") or ""))
            quote = _normalise_spaces(str(evidence.get("quote_span") or evidence.get("raw_row_text") or ""))
            if not claim or not quote or claim == quote:
                continue
            claim_terms = _content_terms(claim)
            if not claim_terms:
                continue
            best_quote_sentence = ""
            best_score = 0
            for quote_sentence in _split_narrative_sentences(quote) or [quote]:
                quote_sentence = _normalise_spaces(quote_sentence)
                quote_terms = _content_terms(quote_sentence)
                if not quote_terms:
                    continue
                score = len(claim_terms & quote_terms)
                if score > best_score:
                    best_score = score
                    best_quote_sentence = quote_sentence
            if not best_quote_sentence:
                continue
            min_score = max(2, min(4, len(claim_terms) // 2 or 1))
            if best_score < min_score:
                continue
            for sentence in sentences:
                if not sentence or sentence in replacements:
                    continue
                if self._text_supports_final_answer_numeric_material(sentence, answer_numeric_candidates):
                    continue
                sentence_terms = _content_terms(sentence)
                if not sentence_terms:
                    continue
                if sentence == claim or len(sentence_terms & claim_terms) >= min_score:
                    replacements[sentence] = best_quote_sentence
                    break
        if not replacements:
            return answer_text
        return _normalise_spaces(" ".join(replacements.get(sentence, sentence) for sentence in sentences))

    def _answer_looks_truncated(self, answer: str) -> bool:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text:
            return True
        if re.search(r"(?:다|니다|요|음|임)[.!?。]?$", answer_text):
            return False
        if re.search(r"[.!?。]$", answer_text):
            return False
        return True

    def _growth_narrative_sentence_candidates(
        self,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
    ) -> List[tuple[int, str, List[str]]]:
        query_terms = self._narrative_context_terms(query)
        driver_groups = self._narrative_driver_groups(query)
        narrative_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ()))
        missing_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ()))
        candidates: List[tuple[int, str, List[str]]] = []

        def _add_candidate(text: str, claim_ids: List[str], base_score: int) -> None:
            normalized = _normalise_spaces(text)
            if not normalized or any(marker in normalized for marker in missing_markers):
                return
            for sentence in _split_narrative_sentences(normalized):
                cleaned = _normalise_spaces(sentence)
                if not cleaned or any(marker in cleaned for marker in missing_markers):
                    continue
                if _narrative_sentence_looks_table_noisy(cleaned):
                    continue
                if _narrative_sentence_looks_abbreviated_fragment(cleaned, narrative_markers):
                    continue
                haystack = cleaned.lower()
                score = base_score
                score += sum(3 for term in query_terms if term.lower() in haystack)
                for group in driver_groups:
                    variants = [
                        str(variant).strip()
                        for variant in (group.get("variants") or [])
                        if str(variant).strip()
                    ]
                    if any(variant.lower() in haystack for variant in variants):
                        score += 4
                score += sum(2 for marker in narrative_markers if marker in cleaned)
                if score <= base_score:
                    continue
                candidates.append((score, cleaned, claim_ids))

        for row in ordered_results or []:
            operation_family = self._aggregate_result_operation_family(row)
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if operation_family != "narrative_summary" and metric_family != "narrative_summary":
                continue
            claim_ids = [str(value).strip() for value in (row.get("selected_claim_ids") or []) if str(value).strip()]
            _add_candidate(str(row.get("answer") or ""), claim_ids, 8)

        for item in evidence_items or []:
            evidence = dict(item or {})
            claim_id = str(evidence.get("evidence_id") or "").strip()
            seen_texts: set[str] = set()
            for key, base_score in (("claim", 2), ("quote_span", 2), ("raw_row_text", 1)):
                candidate_text = _normalise_spaces(str(evidence.get(key) or ""))
                if not candidate_text or candidate_text in seen_texts:
                    continue
                seen_texts.add(candidate_text)
                _add_candidate(candidate_text, [claim_id] if claim_id else [], base_score)

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates

    def _supported_growth_driver_groups(
        self,
        *,
        query: str,
        narrative_candidates: List[tuple[int, str, List[str]]],
    ) -> List[Dict[str, Any]]:
        supported: List[Dict[str, Any]] = []
        for group in self._narrative_driver_groups(query):
            variants = [
                str(variant).strip()
                for variant in (group.get("variants") or [])
                if str(variant).strip()
            ]
            if not variants:
                continue
            if not any(
                any(variant.lower() in candidate_text.lower() for variant in variants)
                for _score, candidate_text, _claim_ids in narrative_candidates
            ):
                continue
            supported.append({**group, "variants": variants})
        return supported

    def _narrative_row_focus_sentence(
        self,
        *,
        ordered_results: List[Dict[str, Any]],
        focus_variants: List[str],
    ) -> Optional[tuple[int, str, List[str]]]:
        if not focus_variants:
            return None
        for row in ordered_results or []:
            operation_family = self._aggregate_result_operation_family(row)
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if operation_family != "narrative_summary" and metric_family != "narrative_summary":
                continue
            claim_ids = [str(value).strip() for value in (row.get("selected_claim_ids") or []) if str(value).strip()]
            narrative_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ()))
            for sentence in _split_narrative_sentences(str(row.get("answer") or "")):
                cleaned = _normalise_spaces(sentence)
                if not cleaned:
                    continue
                if _narrative_sentence_looks_table_noisy(cleaned):
                    continue
                if _narrative_sentence_looks_abbreviated_fragment(cleaned, narrative_markers):
                    continue
                haystack = cleaned.lower()
                if any(variant.lower() in haystack for variant in focus_variants):
                    return (0, cleaned, claim_ids)
        return None

    def _answer_covers_narrative_context(self, answer: str, context: str) -> bool:
        answer_text = _normalise_spaces(str(answer or "")).lower()
        context_text = _normalise_spaces(str(context or ""))
        if not context_text:
            return True
        if context_text.lower() in answer_text:
            return True
        sentences = _split_narrative_sentences(context_text)
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

    def _narrative_row_focus_context(
        self,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        focus_variants: List[str],
        max_sentences: int = 2,
    ) -> Optional[tuple[int, str, List[str]]]:
        if not focus_variants:
            return None
        query_terms = self._narrative_context_terms(query)
        impact_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("growth_impact_markers") or ()))
        for row in ordered_results or []:
            operation_family = self._aggregate_result_operation_family(row)
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if operation_family != "narrative_summary" and metric_family != "narrative_summary":
                continue
            claim_ids = [str(value).strip() for value in (row.get("selected_claim_ids") or []) if str(value).strip()]
            sentences = [
                sentence
                for sentence in _split_narrative_sentences(str(row.get("answer") or ""))
                if not _narrative_sentence_looks_table_noisy(sentence)
                and not _narrative_sentence_looks_abbreviated_fragment(sentence, impact_markers)
            ]
            scored_focus_indexes: List[tuple[int, int]] = []
            for index, sentence in enumerate(sentences):
                haystack = sentence.lower()
                focus_hits = sum(1 for variant in focus_variants if variant.lower() in haystack)
                if not focus_hits:
                    continue
                marker_hits = sum(1 for marker in impact_markers if marker in sentence)
                query_hits = sum(1 for term in query_terms if term.lower() in haystack)
                numeric_hits = len(re.findall(r"\d[\d,]*(?:\.\d+)?%?", sentence))
                score = focus_hits * 5 + marker_hits * 3 + query_hits - numeric_hits
                scored_focus_indexes.append((score, index))
            scored_focus_indexes.sort(key=lambda item: item[0], reverse=True)
            focus_indexes = [index for _, index in scored_focus_indexes]
            if not focus_indexes:
                continue
            selected: List[str] = []
            selected_indexes: set[int] = set()

            def _select(index: int) -> None:
                if index in selected_indexes or index < 0 or index >= len(sentences):
                    return
                selected_indexes.add(index)
                selected.append(sentences[index])

            focus_index = focus_indexes[0]
            _select(focus_index)
            if any(marker in sentences[focus_index] for marker in impact_markers):
                return (0, _normalise_spaces(" ".join(selected)), claim_ids)
            ordered_indexes = [
                *range(focus_index + 1, len(sentences)),
                *range(0, focus_index),
            ]
            for index in ordered_indexes:
                if len(selected) >= max_sentences:
                    break
                if index in selected_indexes:
                    continue
                sentence = sentences[index]
                haystack = sentence.lower()
                if any(term.lower() in haystack for term in query_terms) or any(marker in sentence for marker in impact_markers):
                    _select(index)
            if selected:
                return (0, _normalise_spaces(" ".join(selected)), claim_ids)
        return None

    def _compose_growth_narrative_answer(
        self,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        existing_answer: str,
        evidence_items: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not _query_requests_narrative_context(query):
            return None
        existing_answer_text = _normalise_spaces(str(existing_answer or ""))
        missing_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ()))
        answer_has_missing_claim = any(marker in existing_answer_text for marker in missing_markers)
        answer_is_truncated = self._answer_looks_truncated(existing_answer)

        growth_row: Optional[Dict[str, Any]] = None
        growth_slots: Dict[str, Any] = {}
        for row in ordered_results or []:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            primary_slot = dict(answer_slots.get("primary_value") or {})
            current_slot = dict(answer_slots.get("current_value") or {})
            prior_slot = dict(answer_slots.get("prior_value") or {})
            if not (
                self._answer_slot_has_material(primary_slot)
                and self._answer_slot_has_material(current_slot)
                and self._answer_slot_has_material(prior_slot)
            ):
                continue
            growth_row = dict(row)
            growth_slots = {
                "primary_value": primary_slot,
                "current_value": current_slot,
                "prior_value": prior_slot,
            }
            break

        if not growth_row or not growth_slots:
            return None

        narrative_candidates = self._growth_narrative_sentence_candidates(
            query=query,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )
        if not narrative_candidates:
            return None
        supported_driver_groups = self._supported_growth_driver_groups(
            query=query,
            narrative_candidates=narrative_candidates,
        )

        primary_slot = growth_slots["primary_value"]
        current_slot = growth_slots["current_value"]
        prior_slot = growth_slots["prior_value"]
        growth_value = _normalise_spaces(str(primary_slot.get("rendered_value") or primary_slot.get("raw_value") or ""))
        current_value = self._growth_slot_display_value(current_slot, ordered_results)
        prior_value = self._growth_slot_display_value(prior_slot, ordered_results)
        prior_period = _normalise_spaces(
            str(prior_slot.get("period") or CALCULATION_NARRATIVE_POLICY.get("default_prior_period") or "")
        )
        current_period = _normalise_spaces(str(current_slot.get("period") or primary_slot.get("period") or ""))
        metric_label_raw = _normalise_spaces(
            str(current_slot.get("label") or primary_slot.get("label") or growth_row.get("metric_label") or "")
        )
        metric_label = metric_label_raw
        metric_label = re.sub(str(CALCULATION_SLOT_POLICY.get("period_pattern") or r"$^"), " ", metric_label)
        metric_label = _normalise_spaces(metric_label)
        if not growth_value or not current_value or not metric_label:
            return None
        if self._growth_slots_share_material(current_slot, prior_slot, ordered_results):
            recovered_prior_material = self._recover_growth_prior_material_from_evidence(
                current_slot=current_slot,
                prior_slot=prior_slot,
                evidence_items=evidence_items,
            )
            if recovered_prior_material.get("display"):
                prior_value = recovered_prior_material["display"]
                prior_period = recovered_prior_material.get("period") or prior_period
        required_displays = self._growth_required_display_values(
            growth_row,
            ordered_results,
            evidence_items=evidence_items,
        )
        focus_variants = self._narrative_focus_variants(query)
        focus_required_variants = self._parenthetical_focus_variants(query) or focus_variants
        answer_has_focus = not focus_required_variants or any(
            variant.lower() in existing_answer_text.lower()
            for variant in focus_required_variants
        )
        row_focus_context = self._narrative_row_focus_context(
            query=query,
            ordered_results=ordered_results,
            focus_variants=focus_required_variants or focus_variants,
        )
        answer_has_row_context = not row_focus_context or self._answer_covers_narrative_context(
            existing_answer_text,
            row_focus_context[1],
        )
        answer_has_supported_driver_groups = True
        existing_answer_lower = existing_answer_text.lower()
        for group in supported_driver_groups:
            variants = [
                _normalise_spaces(str(variant or ""))
                for variant in (group.get("variants") or [])
                if _normalise_spaces(str(variant or ""))
            ]
            phrase = _normalise_spaces(str(group.get("phrase") or ""))
            if not variants:
                continue
            coverage_terms = variants + ([phrase] if phrase else [])
            if not any(term.lower() in existing_answer_lower for term in coverage_terms):
                answer_has_supported_driver_groups = False
                break
        if (
            not answer_is_truncated
            and not answer_has_missing_claim
            and required_displays
            and all(value in existing_answer_text for value in required_displays)
            and answer_has_focus
            and answer_has_row_context
            and answer_has_supported_driver_groups
        ):
            return None

        direction = _normalise_spaces(str(primary_slot.get("direction") or primary_slot.get("direction_hint") or "")).lower()
        if not direction:
            normalized_value = primary_slot.get("normalized_value")
            try:
                direction = "decrease" if normalized_value is not None and float(normalized_value) < 0 else "increase"
            except (TypeError, ValueError):
                direction = "decrease" if growth_value.startswith("-") else "increase"
        direction_words = dict(CALCULATION_NARRATIVE_POLICY.get("direction_words") or {})
        growth_direction_metric_terms = tuple(
            str(item)
            for item in (CALCULATION_NARRATIVE_POLICY.get("growth_direction_metric_terms") or ())
            if str(item)
        )
        if direction == "decrease":
            direction_word = str(direction_words.get("decrease") or "decrease")
        elif any(term in metric_label for term in growth_direction_metric_terms):
            direction_word = str(direction_words.get("growth") or direction_words.get("increase") or "increase")
        else:
            direction_word = str(direction_words.get("increase") or "increase")
        year_suffix = str(CALCULATION_NARRATIVE_POLICY.get("period_year_suffix") or "")
        if current_period and current_period in metric_label_raw:
            period_prefix = ""
        elif current_period and year_suffix and not current_period.endswith(year_suffix):
            period_prefix = str(CALCULATION_NARRATIVE_POLICY.get("period_prefix_with_year_template") or "").format(
                period=current_period
            )
        elif current_period:
            period_prefix = str(CALCULATION_NARRATIVE_POLICY.get("period_prefix_template") or "").format(
                period=current_period
            )
        else:
            period_prefix = ""
        if prior_value:
            prior_period_display = prior_period
            if prior_period_display and year_suffix and re.fullmatch(r"\d{4}", prior_period_display):
                prior_period_display = f"{prior_period_display}{year_suffix}"
            prior_phrase = str(CALCULATION_NARRATIVE_POLICY.get("prior_phrase_with_value_template") or "").format(
                period=prior_period_display,
                value=prior_value,
            )
        else:
            prior_period_display = prior_period
            if prior_period_display and year_suffix and re.fullmatch(r"\d{4}", prior_period_display):
                prior_period_display = f"{prior_period_display}{year_suffix}"
            prior_phrase = str(CALCULATION_NARRATIVE_POLICY.get("prior_phrase_template") or "").format(
                period=prior_period_display
            )
        numeric_sentence = _normalise_spaces(
            str(CALCULATION_NARRATIVE_POLICY.get("growth_numeric_sentence_template") or "").format(
                period_prefix=period_prefix,
                metric_label=metric_label,
                topic_particle=_topic_particle(metric_label),
                current_value=current_value,
                prior_phrase=prior_phrase,
                growth_value=growth_value,
                direction_word=direction_word,
            )
        )
        existing_context = f"{existing_answer_text} {numeric_sentence}".lower()
        uncovered_focus_variants = [
            variant
            for variant in focus_variants
            if variant.lower() not in existing_context
        ]
        chosen_candidate = narrative_candidates[0]
        if row_focus_context and not self._answer_covers_narrative_context(existing_answer_text, row_focus_context[1]):
            chosen_candidate = row_focus_context
        elif uncovered_focus_variants:
            parenthetical_variants = [
                variant
                for variant in self._parenthetical_focus_variants(query)
                if variant.lower() not in existing_context
            ]
            row_focus_candidate = self._narrative_row_focus_sentence(
                ordered_results=ordered_results,
                focus_variants=parenthetical_variants,
            )
            if row_focus_candidate:
                chosen_candidate = row_focus_candidate
            elif not parenthetical_variants:
                scored_candidates = []
                for candidate in narrative_candidates:
                    candidate_text = candidate[1].lower()
                    hits = [
                        variant
                        for variant in uncovered_focus_variants
                        if variant.lower() in candidate_text
                    ]
                    scored_candidates.append((sum(len(hit) for hit in hits), candidate))
                scored_candidates.sort(key=lambda item: item[0], reverse=True)
                if scored_candidates and scored_candidates[0][0] > 0:
                    chosen_candidate = scored_candidates[0][1]
        if uncovered_focus_variants and chosen_candidate == narrative_candidates[0]:
            for candidate in narrative_candidates:
                candidate_text = candidate[1].lower()
                if any(variant.lower() in candidate_text for variant in uncovered_focus_variants):
                    chosen_candidate = candidate
                    break
        narrative_sentence, selected_claim_ids = chosen_candidate[1], chosen_candidate[2]
        terminal_pattern = str(CALCULATION_NARRATIVE_POLICY.get("sentence_terminal_pattern") or "")
        terminal_suffix = str(CALCULATION_NARRATIVE_POLICY.get("sentence_terminal_suffix") or "")
        if narrative_sentence and terminal_pattern and not re.search(terminal_pattern, narrative_sentence):
            narrative_sentence = f"{narrative_sentence}{terminal_suffix}"
        narrative_sentences = [narrative_sentence] if narrative_sentence else []
        selected_claim_ids = list(selected_claim_ids or [])
        composed_context = _normalise_spaces(f"{numeric_sentence} {' '.join(narrative_sentences)}").lower()
        max_driver_sentences = int(CALCULATION_NARRATIVE_POLICY.get("max_growth_driver_sentences") or 4)
        max_narrative_sentences = max(1, min(max_driver_sentences, max(1, len(supported_driver_groups))))
        for group in supported_driver_groups:
            variants = [
                _normalise_spaces(str(variant or ""))
                for variant in (group.get("variants") or [])
                if _normalise_spaces(str(variant or ""))
            ]
            phrase = _normalise_spaces(str(group.get("phrase") or ""))
            if not variants or not phrase:
                continue
            if any(variant.lower() in composed_context for variant in variants):
                continue
            for candidate in narrative_candidates:
                candidate_sentence = _normalise_spaces(candidate[1])
                candidate_context = candidate_sentence.lower()
                if not candidate_sentence or candidate_sentence == _normalise_spaces(narrative_sentence):
                    continue
                if not any(variant.lower() in candidate_context for variant in variants):
                    continue
                narrative_sentences.append(candidate_sentence)
                selected_claim_ids.extend(candidate[2] or [])
                composed_context = _normalise_spaces(f"{numeric_sentence} {' '.join(narrative_sentences)}").lower()
                break
            if len(narrative_sentences) >= max_narrative_sentences:
                break
        return {
            "compressed_answer": _normalise_spaces(f"{numeric_sentence} {' '.join(narrative_sentences)}"),
            "selected_claim_ids": list(dict.fromkeys(selected_claim_ids)),
        }

    def _answer_satisfies_growth_narrative_intent(
        self,
        *,
        query: str,
        answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        query_text = _normalise_spaces(str(query or ""))
        answer_text = _normalise_spaces(str(answer or ""))
        if not query_text or not answer_text or not _query_requests_narrative_context(query_text):
            return False
        if not re.search(str(CALCULATION_NARRATIVE_POLICY.get("growth_query_pattern") or r"$^"), query_text):
            return False
        missing_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ()))
        if any(marker in answer_text for marker in missing_markers):
            return False
        if not re.search(str(CALCULATION_NARRATIVE_POLICY.get("percent_display_pattern") or r"$^"), answer_text):
            return False
        for row in ordered_results or []:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            required_displays = self._growth_required_display_values(row, ordered_results)
            if required_displays and not all(value in answer_text for value in required_displays):
                return False
            break
        impact_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("growth_impact_markers") or ()))
        if not any(marker in answer_text for marker in impact_markers):
            return False

        generic_terms = {
            str(item)
            for item in (CALCULATION_NARRATIVE_POLICY.get("growth_generic_focus_terms") or ())
            if str(item)
        }
        focus_terms = [
            term
            for term in self._narrative_context_terms(query_text)
            if term not in generic_terms and len(term) >= 2
        ]
        parenthetical_focus_terms = self._parenthetical_focus_variants(query_text)
        required_focus_terms = parenthetical_focus_terms or focus_terms
        if required_focus_terms and not any(term.lower() in answer_text.lower() for term in required_focus_terms):
            return False
        narrative_candidates = self._growth_narrative_sentence_candidates(
            query=query_text,
            ordered_results=ordered_results,
            evidence_items=list(evidence_items or []),
        )
        for group in self._supported_growth_driver_groups(
            query=query_text,
            narrative_candidates=narrative_candidates,
        ):
            variants = [
                _normalise_spaces(str(variant or ""))
                for variant in (group.get("variants") or [])
                if _normalise_spaces(str(variant or ""))
            ]
            phrase = _normalise_spaces(str(group.get("phrase") or ""))
            if not variants:
                continue
            coverage_terms = variants + ([phrase] if phrase else [])
            if not any(term.lower() in answer_text.lower() for term in coverage_terms):
                return False
        row_focus_context = self._narrative_row_focus_context(
            query=query_text,
            ordered_results=ordered_results,
            focus_variants=required_focus_terms,
        )
        if row_focus_context and not self._answer_covers_narrative_context(answer_text, row_focus_context[1]):
            return False

        has_growth_row = any(
            self._aggregate_result_operation_family(row) == "growth_rate"
            or "growth" in _normalise_spaces(str(row.get("metric_family") or "")).lower()
            or any(
                str(term) in _normalise_spaces(str(row.get("metric_label") or ""))
                for term in (CALCULATION_NARRATIVE_POLICY.get("growth_metric_label_terms") or ())
            )
            for row in ordered_results or []
        )
        has_narrative_material = any(
            self._aggregate_result_operation_family(row) == "narrative_summary"
            or _normalise_spaces(str(row.get("metric_family") or "")).lower() == "narrative_summary"
            for row in ordered_results or []
        )
        return has_growth_row and has_narrative_material

    def _prune_irrelevant_growth_narrative_sentences(
        self,
        *,
        query: str,
        answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        sentences = _split_narrative_sentences(answer_text)
        if len(sentences) < 2 or not _query_requests_narrative_context(query):
            return answer_text
        if not self._answer_satisfies_growth_narrative_intent(
            query=query,
            answer=answer_text,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        ):
            return answer_text

        has_growth_row = any(
            self._aggregate_result_operation_family(row) == "growth_rate"
            for row in ordered_results or []
        )
        has_narrative_row = any(self._row_is_narrative_summary(row) for row in ordered_results or [])
        if not has_growth_row or not has_narrative_row:
            return answer_text

        required_values: List[str] = []
        for row in ordered_results or []:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            required_values.extend(
                value
                for value in self._growth_required_display_values(
                    row,
                    ordered_results,
                    evidence_items=evidence_items,
                )
                if value
            )
        required_values = list(dict.fromkeys(required_values))

        candidate_sentences: List[str] = []
        for _score, candidate, _claim_ids in self._growth_narrative_sentence_candidates(
            query=query,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        ):
            candidate_sentences.extend(_split_narrative_sentences(candidate))
        candidate_sentences = list(dict.fromkeys(_normalise_spaces(item) for item in candidate_sentences if item))

        focus_variants = [_normalise_spaces(str(item)) for item in self._narrative_focus_variants(query) if item]
        impact_markers = [
            _normalise_spaces(str(item))
            for item in (CALCULATION_NARRATIVE_POLICY.get("growth_impact_markers") or ())
            if _normalise_spaces(str(item))
        ]
        narrative_markers = [
            _normalise_spaces(str(item))
            for item in (CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ())
            if _normalise_spaces(str(item))
        ]
        allowed_narrative_numeric_surface = _normalise_spaces(" ".join([*candidate_sentences, *required_values]))

        def _token_overlap_supported(sentence: str, candidate: str) -> bool:
            sentence_terms = {
                term.lower()
                for term in self._narrative_context_terms(sentence)
                if len(term) >= 3
            }
            candidate_terms = {
                term.lower()
                for term in self._narrative_context_terms(candidate)
                if len(term) >= 3
            }
            if not sentence_terms or not candidate_terms:
                return False
            overlap = sentence_terms & candidate_terms
            return len(overlap) >= max(2, min(len(sentence_terms), len(candidate_terms)) // 2)

        def _is_supported_sentence(sentence: str) -> bool:
            cleaned = _normalise_spaces(sentence)
            if not cleaned:
                return False
            if self._growth_sentence_has_untraced_material_numeric(
                cleaned,
                allowed_narrative_numeric_surface,
                required_values,
            ):
                return False
            if any(value and value in cleaned for value in required_values):
                return True
            cleaned_lower = cleaned.lower()
            for candidate in candidate_sentences:
                candidate_lower = candidate.lower()
                if candidate_lower and (candidate_lower in cleaned_lower or cleaned_lower in candidate_lower):
                    return True
                if _token_overlap_supported(cleaned, candidate):
                    return True
            if any(marker and marker in cleaned for marker in impact_markers + narrative_markers):
                return any(variant and variant.lower() in cleaned_lower for variant in focus_variants)
            return False

        kept_sentences = [sentence for sentence in sentences if _is_supported_sentence(sentence)]
        if len(kept_sentences) == len(sentences) or not kept_sentences:
            return answer_text
        pruned_answer = _normalise_spaces(" ".join(kept_sentences))
        if not self._answer_satisfies_growth_narrative_intent(
            query=query,
            answer=pruned_answer,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        ):
            return answer_text
        if self._growth_answer_has_untraced_numeric_material(
            pruned_answer,
            ordered_results,
            evidence_items,
        ):
            return answer_text
        return pruned_answer

    def _coerce_operand_unit_from_evidence(
        self,
        *,
        raw_value: str,
        raw_unit: str,
        evidence_item: Optional[Dict[str, Any]],
    ) -> str:
        metadata = dict((evidence_item or {}).get("metadata") or {})
        unit_hint = str(metadata.get("unit_hint") or "").strip()
        current_unit = str(raw_unit or "").strip()
        surface_unit = self._infer_operand_unit_from_value_surface(
            raw_value=raw_value,
            evidence_item=evidence_item,
        )
        if surface_unit:
            surface_value, surface_family = _normalise_operand_value(raw_value or "1", surface_unit)
            current_value, current_family = _normalise_operand_value(raw_value or "1", current_unit)
            hint_value, hint_family = _normalise_operand_value(raw_value or "1", unit_hint)
            surface_family = _normalise_spaces(str(surface_family or "")).upper()
            current_family = _normalise_spaces(str(current_family or "")).upper()
            hint_family = _normalise_spaces(str(hint_family or "")).upper()
            known_current_family = current_unit and current_family and current_family != "UNKNOWN"
            known_hint_family = unit_hint and hint_family and hint_family != "UNKNOWN"
            known_surface_family = surface_family and surface_family != "UNKNOWN" and surface_value is not None
            if self._evidence_core_surface_contains_value_unit(
                raw_value=raw_value,
                raw_unit=surface_unit,
                evidence_item=evidence_item,
            ):
                if known_hint_family and known_current_family and hint_family == current_family:
                    return current_unit
                return surface_unit
            if known_surface_family and (
                (known_current_family and current_value is not None and surface_family != current_family)
                or (known_hint_family and hint_value is not None and surface_family != hint_family)
            ):
                return current_unit or unit_hint
            return surface_unit
        if not unit_hint:
            return current_unit
        if not current_unit:
            return unit_hint
        normalized_current = _normalise_spaces(current_unit).lower()
        normalized_hint = _normalise_spaces(unit_hint).lower()
        if normalized_current == normalized_hint:
            return current_unit
        render_policy = dict(CALCULATION_RENDER_POLICY)
        bare_numeric_pattern = str(render_policy.get("operand_unit_bare_numeric_pattern") or "")
        bare_numeric = bool(bare_numeric_pattern and re.fullmatch(bare_numeric_pattern, str(raw_value or "").strip()))
        ambiguous_krw_units = {
            _normalise_spaces(str(item)).lower()
            for item in (render_policy.get("operand_unit_ambiguous_krw_units") or ())
            if str(item).strip()
        }
        krw_display_units = {
            _normalise_spaces(str(item)).lower()
            for item in (render_policy.get("krw_display_units") or ())
            if str(item).strip()
        }
        if bare_numeric and normalized_current in ambiguous_krw_units and normalized_hint in krw_display_units:
            return unit_hint
        return current_unit

    def _evidence_core_surface(
        self,
        evidence_item: Optional[Dict[str, Any]],
    ) -> str:
        return _normalise_spaces(
            " ".join(
                str((evidence_item or {}).get(key) or "")
                for key in ("claim", "quote_span", "raw_row_text")
            )
        )

    def _evidence_core_surface_contains_value_unit(
        self,
        *,
        raw_value: str,
        raw_unit: str,
        evidence_item: Optional[Dict[str, Any]],
    ) -> bool:
        value = _normalise_spaces(str(raw_value or ""))
        unit = _normalise_spaces(str(raw_unit or ""))
        surface = self._evidence_core_surface(evidence_item)
        if not value or not unit or not surface:
            return False
        compact_value = re.sub(r"[,\s()]", "", value)
        compact_unit = re.sub(r"\s+", "", unit)
        unit_policy = dict(NUMERIC_UNIT_NORMALIZATION_POLICY)
        aliases = dict(unit_policy.get("inline_unit_aliases") or {})
        unit_pattern = str(unit_policy.get("inline_value_unit_pattern") or "")
        for match in re.finditer(unit_pattern, surface):
            matched_value = re.sub(r"[,\s()]", "", str(match.group("value") or ""))
            matched_unit = re.sub(r"\s+", "", str(match.group("unit") or ""))
            matched_unit = str(aliases.get(matched_unit) or matched_unit)
            if matched_value == compact_value and matched_unit == compact_unit:
                return True
        return False

    def _coerce_operand_period_from_evidence_surface(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        surface = self._evidence_core_surface(evidence_item)
        if not surface:
            return row
        explicit_years = list(dict.fromkeys(re.findall(r"20\d{2}", surface)))
        if len(explicit_years) != 1:
            return row
        evidence_year = explicit_years[0]
        period_years = set(re.findall(r"20\d{2}", str(row.get("period") or "")))
        if period_years and evidence_year in period_years:
            return row
        if period_years and evidence_year not in period_years:
            updated = dict(row)
            updated["period"] = evidence_year
            updated["period_source"] = "evidence_surface"
            return updated
        row_years = set(
            re.findall(
                r"20\d{2}",
                " ".join(
                    str(row.get(key) or "")
                    for key in ("period", "label", "matched_operand_label")
                ),
            )
        )
        if row_years and evidence_year in row_years:
            return row
        updated = dict(row)
        updated["period"] = evidence_year
        updated["period_source"] = "evidence_surface"
        return updated

    def _evidence_item_for_operand_row(
        self,
        row: Dict[str, Any],
        evidence_by_id: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        candidate_ids = _clean_source_row_ids([
            row.get("evidence_id"),
            row.get("source_row_id"),
            row.get("source_row_ids"),
        ])
        for candidate_id in [item for item in candidate_ids if item]:
            evidence_item = evidence_by_id.get(candidate_id)
            if evidence_item:
                return evidence_item
            evidence_item = evidence_by_id.get(f"recon::{candidate_id}")
            if evidence_item:
                return evidence_item
            if candidate_id.startswith("recon::"):
                evidence_item = evidence_by_id.get(candidate_id.removeprefix("recon::"))
                if evidence_item:
                    return evidence_item
        return None

    def _coerce_operand_row_from_evidence(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        updated = dict(row)
        raw_value = str(updated.get("raw_value") or "")
        coerced_unit = self._coerce_operand_unit_from_evidence(
            raw_value=raw_value,
            raw_unit=str(updated.get("raw_unit") or ""),
            evidence_item=evidence_item,
        )
        if coerced_unit != str(updated.get("raw_unit") or "") or updated.get("normalized_value") is None:
            normalized_value, normalized_unit = _normalise_operand_value(raw_value, coerced_unit)
            if normalized_value is not None:
                updated["raw_unit"] = coerced_unit
                updated["normalized_value"] = normalized_value
                updated["normalized_unit"] = normalized_unit
        if evidence_item:
            metadata = dict(evidence_item.get("metadata") or {})
            if updated.get("statement_type") is None:
                updated["statement_type"] = metadata.get("statement_type")
            if updated.get("consolidation_scope") is None:
                updated["consolidation_scope"] = metadata.get("consolidation_scope")
            if updated.get("table_source_id") is None:
                updated["table_source_id"] = metadata.get("table_source_id")
            updated = self._coerce_operand_period_from_evidence_surface(updated, evidence_item)
        updated = _coerce_lookup_magnitude_record(updated, evidence_item)
        if (
            updated.get("dependency_resolved")
            and str(updated.get("source_row_id") or "").startswith("task_output:")
            and updated.get("normalized_value") is not None
        ):
            return updated
        return self._refine_operand_precision_from_evidence_table(updated, evidence_item)

    def _infer_operand_unit_from_value_surface(
        self,
        *,
        raw_value: str,
        evidence_item: Optional[Dict[str, Any]],
    ) -> str:
        value = _normalise_spaces(str(raw_value or ""))
        if not value or not re.search(r"\d", value):
            return ""
        surfaces = [
            str((evidence_item or {}).get("claim") or ""),
            str((evidence_item or {}).get("quote_span") or ""),
            str((evidence_item or {}).get("raw_row_text") or ""),
            str((evidence_item or {}).get("source_context") or ""),
        ]
        surface = _normalise_spaces(" ".join(part for part in surfaces if part))
        if not surface:
            return ""
        aliases = dict(NUMERIC_UNIT_NORMALIZATION_POLICY.get("inline_unit_aliases") or {})
        render_policy = dict(CALCULATION_RENDER_POLICY)
        unit_candidates = [
            _normalise_spaces(str(item))
            for item in (
                tuple(render_policy.get("krw_display_units") or ())
                + tuple(render_policy.get("percent_display_units") or ())
                + tuple(render_policy.get("count_or_percent_normalized_units") or ())
            )
            if str(item).strip()
        ]
        value_pattern = re.escape(value)
        parenthetical_unit_pattern = (
            rf"{value_pattern}\s*\(?\s*"
            rf"(?P<surface_unit>{'|'.join(re.escape(unit) for unit in sorted(set(unit_candidates), key=len, reverse=True))})"
            rf"\s*\)?"
        )
        for match in re.finditer(parenthetical_unit_pattern, surface, flags=re.IGNORECASE):
            unit_text = _normalise_spaces(str(match.group("surface_unit") or ""))
            if unit_text:
                return str(aliases.get(unit_text, unit_text))
        unit_pattern = str(
            NUMERIC_UNIT_NORMALIZATION_POLICY.get("inline_value_unit_pattern") or ""
        )
        if not unit_pattern:
            return ""
        compact_value = re.sub(r"[,\s()]", "", value)
        if not compact_value:
            return ""
        for match in re.finditer(unit_pattern, surface):
            matched_value = str(match.group("value") or "")
            matched_compact = re.sub(r"[,\s()]", "", matched_value)
            if matched_compact != compact_value:
                continue
            unit_text = _normalise_spaces(str(match.group("unit") or ""))
            return str(aliases.get(unit_text, unit_text))
        return ""

    def _refine_operand_precision_from_evidence_table(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Prefer a finer structured-table cell when an LLM returned a rounded KRW surface."""
        normalized_value = row.get("normalized_value")
        normalized_unit = _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
        raw_unit = _normalise_spaces(str(row.get("raw_unit") or ""))
        raw_value = _normalise_spaces(str(row.get("raw_value") or ""))
        if normalized_value is None or normalized_unit != "KRW":
            return row

        metadata = dict((evidence_item or {}).get("metadata") or {})
        records: List[Dict[str, Any]] = []
        for key in ("table_row_records_json", "table_value_records_json"):
            payload = str(metadata.get(key) or "").strip()
            if not payload:
                continue
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                records.extend(dict(item) for item in parsed if isinstance(item, dict))

        if not records:
            return row

        target_values: List[float] = []
        render_policy = dict(CALCULATION_RENDER_POLICY)
        if raw_unit in set(render_policy.get("converted_display_units") or ()) or any(
            unit in raw_value for unit in tuple(render_policy.get("krw_value_magnitude_markers") or ())
        ):
            target_values.append(float(normalized_value))

        operand_aliases = [
            str(row.get("label") or "").strip(),
            str(row.get("matched_operand_label") or "").strip(),
        ]
        slot_policy = dict(CALCULATION_SLOT_POLICY)
        parenthetical_alias_pattern = str(slot_policy.get("parenthetical_alias_pattern") or "")
        parenthetical_strip_pattern = str(slot_policy.get("parenthetical_strip_pattern") or "")
        leading_period_strip_pattern = str(slot_policy.get("leading_period_strip_pattern") or "")
        for label_surface in list(operand_aliases):
            if parenthetical_alias_pattern:
                for match in re.finditer(parenthetical_alias_pattern, label_surface):
                    operand_aliases.append(_normalise_spaces(match.group(1)))
            without_parenthetical = (
                _normalise_spaces(re.sub(parenthetical_strip_pattern, " ", label_surface))
                if parenthetical_strip_pattern
                else _normalise_spaces(label_surface)
            )
            if without_parenthetical:
                operand_aliases.append(without_parenthetical)
                stripped_period = _normalise_spaces(
                    re.sub(leading_period_strip_pattern, " ", without_parenthetical)
                    if leading_period_strip_pattern
                    else without_parenthetical
                )
                if stripped_period:
                    operand_aliases.append(stripped_period)
        operand_spec = {
            "label": str(row.get("matched_operand_label") or row.get("label") or "").strip(),
            "aliases": [item for item in dict.fromkeys(operand_aliases) if item],
        }

        def _cell_from_contextual_note_row() -> Optional[Dict[str, Any]]:
            row_labels = [
                _normalise_spaces(line)
                for line in str(metadata.get("table_row_labels_text") or "").splitlines()
                if _normalise_spaces(line)
            ]
            if not row_labels:
                return None
            records_by_label: Dict[str, Dict[str, Any]] = {}
            for record in records:
                label = _normalise_spaces(str(record.get("row_label") or ""))
                if not label:
                    continue
                existing = records_by_label.get(label)
                if existing is None or (not existing.get("cells") and record.get("cells")):
                    records_by_label[label] = record

            def _select_period_aware_cell(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                cells = [dict(cell or {}) for cell in list(record.get("cells") or []) if isinstance(cell, dict)]
                if not cells:
                    return None
                query_years: List[int] = []
                for raw_year in (
                    row.get("period"),
                    metadata.get("year"),
                ):
                    try:
                        if raw_year not in (None, ""):
                            year = int(raw_year)
                            if year not in query_years:
                                query_years.append(year)
                    except (TypeError, ValueError):
                        continue
                period_operand = dict(operand_spec)
                role = _normalise_spaces(str(row.get("matched_operand_role") or ""))
                period_hint = _normalise_spaces(str(row.get("period") or ""))
                if role:
                    period_operand["role"] = role
                if period_hint:
                    period_operand["period_hint"] = period_hint
                cells = [{**cell, "_report_year": metadata.get("year")} for cell in cells]
                selected = _select_structured_cell(
                    cells,
                    operand=period_operand,
                    query_years=query_years,
                    period_focus=_operand_period_focus(period_operand, "unknown"),
                )
                return dict(selected) if selected else None

            def _is_krw_cell(cell_data: Dict[str, Any]) -> bool:
                value_text = _normalise_spaces(str(cell_data.get("value_text") or ""))
                unit_hint = _normalise_spaces(str(cell_data.get("unit_hint") or ""))
                if not re.search(r"\d", value_text):
                    return False
                cell_value, cell_unit = _normalise_operand_value(value_text, unit_hint)
                return cell_value is not None and cell_unit == "KRW"

            for index, label_text in enumerate(row_labels):
                if not _operand_text_match(label_text, operand_spec):
                    continue
                current_record = records_by_label.get(label_text)
                if current_record:
                    cell_data = _select_period_aware_cell(current_record)
                    if cell_data and _is_krw_cell(cell_data):
                        return cell_data
                for previous_label in reversed(row_labels[:index]):
                    record = records_by_label.get(previous_label)
                    if not record:
                        continue
                    cell_data = _select_period_aware_cell(record)
                    if cell_data and _is_krw_cell(cell_data):
                        return cell_data
                break
            return None

        surface = _normalise_spaces(
            " ".join(
                part
                for part in [
                    str((evidence_item or {}).get("claim") or ""),
                    str((evidence_item or {}).get("quote_span") or ""),
                    str((evidence_item or {}).get("raw_row_text") or ""),
                    str((evidence_item or {}).get("source_context") or ""),
                ]
                if part
            )
        )
        surface_value = _extract_numeric_value_after_operand_text(surface, operand_spec)
        if surface_value:
            surface_normalized, surface_unit = _normalise_operand_value(surface_value, "")
            if surface_normalized is not None and surface_unit == "KRW":
                target_values.append(float(surface_normalized))

        contextual_cell = _cell_from_contextual_note_row()
        best_cell: Optional[Dict[str, Any]] = None
        best_normalized: Optional[float] = None
        best_diff: Optional[float] = None
        best_target: Optional[float] = None
        if contextual_cell:
            contextual_value, contextual_unit = _normalise_operand_value(
                _normalise_spaces(str(contextual_cell.get("value_text") or "")),
                _normalise_spaces(str(contextual_cell.get("unit_hint") or "")),
            )
            if contextual_value is not None and contextual_unit == "KRW":
                best_cell = contextual_cell
                best_normalized = float(contextual_value)

        if target_values and best_cell is None:
            for record in records:
                for cell in list(record.get("cells") or []):
                    cell_data = dict(cell or {})
                    value_text = _normalise_spaces(str(cell_data.get("value_text") or ""))
                    unit_hint = _normalise_spaces(str(cell_data.get("unit_hint") or ""))
                    if unit_hint not in {"천원", "백만원"} or not re.search(r"\d", value_text):
                        continue
                    cell_value, cell_unit = _normalise_operand_value(value_text, unit_hint)
                    if cell_value is None or cell_unit != "KRW":
                        continue
                    for target_value in target_values:
                        diff = abs(float(cell_value) - target_value)
                        tolerance = max(abs(target_value) * 0.005, 100_000_000.0)
                        if diff > tolerance:
                            continue
                        if best_diff is None or diff < best_diff:
                            best_cell = cell_data
                            best_normalized = float(cell_value)
                            best_diff = diff
                            best_target = target_value

        if not best_cell or best_normalized is None:
            return row
        if best_target is None and not contextual_cell:
            try:
                current_float = float(normalized_value)
                candidate_float = float(best_normalized)
            except (TypeError, ValueError):
                return row
            current_abs = abs(current_float)
            candidate_abs = abs(candidate_float)
            if current_abs == 0:
                return row
            relative_delta = abs(candidate_abs - current_abs) / max(current_abs, candidate_abs, 1.0)
            current_digits = len(re.sub(r"\D", "", raw_value))
            candidate_digits = len(re.sub(r"\D", "", str(best_cell.get("value_text") or "")))
            if relative_delta > 0.005 or candidate_digits <= current_digits:
                return row
        refined = dict(row)
        refined["raw_value"] = _normalise_spaces(str(best_cell.get("value_text") or ""))
        refined["raw_unit"] = _normalise_spaces(str(best_cell.get("unit_hint") or ""))
        refined["normalized_value"] = best_normalized
        refined["normalized_unit"] = "KRW"
        refined["precision_source"] = "structured_table_cell"
        if best_target is not None and abs(float(normalized_value) - best_target) > 100_000_000.0:
            refined["precision_source"] = "surface_anchored_structured_table_cell"
        if contextual_cell:
            refined["precision_source"] = "contextual_note_structured_table_cell"
        return refined

    def _surface_contract_numeric_evidence_items(
        self,
        evidence_items: List[Dict[str, Any]],
        required_operands: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Keep prose evidence that directly names an ontology surface and a nearby number."""
        if not evidence_items or not required_operands:
            return []

        preserved: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in evidence_items:
            evidence = dict(item or {})
            surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        evidence.get("claim"),
                        evidence.get("quote_span"),
                        evidence.get("raw_row_text"),
                    )
                )
            )
            if not surface or not re.search(r"\d", surface):
                continue
            for operand in required_operands:
                operand_dict = dict(operand or {})
                if not _text_has_positive_surface(surface, operand_dict):
                    continue
                if _text_has_negative_surface(surface, operand_dict):
                    continue
                if not _extract_numeric_value_after_operand_text(surface, operand_dict):
                    continue
                key = str(evidence.get("evidence_id") or evidence.get("source_anchor") or surface[:120])
                if key in seen:
                    continue
                seen.add(key)
                preserved.append(evidence)
                break
        return preserved

    def _ratio_components_have_suspicious_scale(
        self,
        calculation_result: Dict[str, Any],
    ) -> bool:
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        components_by_role = dict(answer_slots.get("components_by_role") or {})
        for entries in components_by_role.values():
            for entry in entries or []:
                raw_unit = _normalise_spaces(str((entry or {}).get("raw_unit") or "")).lower()
                raw_value = str((entry or {}).get("raw_value") or "").strip()
                if raw_unit not in {"원", "krw"}:
                    continue
                if not re.fullmatch(r"[\(\)\-]?\d[\d,]*(?:\.\d+)?", raw_value):
                    continue
                digit_count = len(re.sub(r"\D", "", raw_value))
                if digit_count >= 8:
                    return True
        return False

    def _align_ratio_operand_units_with_shared_table_context(
        self,
        ordered_operands: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if len(ordered_operands) < 2:
            return ordered_operands
        render_policy = dict(CALCULATION_RENDER_POLICY)
        krw_unit = str(render_policy.get("krw_normalized_unit") or "").strip().upper()
        if not krw_unit:
            return ordered_operands
        source_units = {
            _normalise_spaces(str(item or ""))
            for item in (render_policy.get("source_display_units") or ())
            if _normalise_spaces(str(item or ""))
        }
        scale_by_unit = {
            _normalise_spaces(str(unit or "")): float(scale)
            for unit, scale in dict(render_policy.get("krw_display_unit_scales") or {}).items()
            if _normalise_spaces(str(unit or ""))
        }
        eligible_units = {unit for unit in source_units if unit in scale_by_unit}
        if len(eligible_units) < 2:
            return ordered_operands

        def _context_key(row: Dict[str, Any]) -> tuple[str, ...]:
            table_id = _normalise_spaces(str(row.get("table_source_id") or row.get("source_table_id") or ""))
            if table_id:
                return ("table", table_id)
            source_section = _normalise_spaces(str(row.get("source_section") or ""))
            statement_type = _normalise_spaces(str(row.get("statement_type") or ""))
            consolidation_scope = _normalise_spaces(str(row.get("consolidation_scope") or ""))
            if source_section and statement_type and consolidation_scope:
                return ("section", source_section, statement_type, consolidation_scope)
            return ()

        grouped_indexes: Dict[tuple[str, ...], List[int]] = {}
        for index, row in enumerate(ordered_operands):
            if _normalise_spaces(str(row.get("normalized_unit") or "")).upper() != krw_unit:
                continue
            raw_unit = _normalise_spaces(str(row.get("raw_unit") or ""))
            if raw_unit not in eligible_units:
                continue
            key = _context_key(row)
            if not key:
                continue
            grouped_indexes.setdefault(key, []).append(index)

        aligned = [dict(row) for row in ordered_operands]
        changed = False
        for indexes in grouped_indexes.values():
            if len(indexes) < 2:
                continue
            group_units = {
                _normalise_spaces(str(aligned[index].get("raw_unit") or ""))
                for index in indexes
                if _normalise_spaces(str(aligned[index].get("raw_unit") or "")) in eligible_units
            }
            if len(group_units) < 2:
                continue
            target_unit = max(group_units, key=lambda unit: scale_by_unit.get(unit, 0.0))
            for index in indexes:
                row = aligned[index]
                raw_value = str(row.get("raw_value") or "").strip()
                current_unit = _normalise_spaces(str(row.get("raw_unit") or ""))
                if not raw_value or current_unit == target_unit:
                    continue
                normalized_value, normalized_unit = _normalise_operand_value(raw_value, target_unit)
                if normalized_value is None or _normalise_spaces(str(normalized_unit or "")).upper() != krw_unit:
                    continue
                row["original_raw_unit"] = row.get("original_raw_unit") or current_unit
                row["raw_unit"] = target_unit
                row["normalized_value"] = normalized_value
                row["normalized_unit"] = normalized_unit
                row["rendered_value"] = f"{raw_value}{target_unit}"
                row["ratio_unit_aligned_from_sibling_table"] = True
                changed = True
        return aligned if changed else ordered_operands

    def _align_ratio_operands_with_sibling_table_context(
        self,
        ordered_operands: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        if len(ordered_operands) < 2:
            return ordered_operands
        evidence_pool = [dict(item) for item in (evidence_items or []) if isinstance(item, dict)]
        if not evidence_pool:
            return self._align_ratio_operand_units_with_shared_table_context(ordered_operands)
        evidence_by_id = {
            str(item.get("evidence_id") or "").strip(): dict(item)
            for item in evidence_pool
            if str(item.get("evidence_id") or "").strip()
        }

        def _row_as_operand(row: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "label": _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or "")),
                "concept": _normalise_spaces(str(row.get("matched_operand_concept") or "")),
                "role": _normalise_spaces(str(row.get("matched_operand_role") or "")),
                "period": _normalise_spaces(str(row.get("period") or "")),
                "required": True,
            }

        def _row_surfaces(row: Dict[str, Any]) -> List[str]:
            return [
                surface
                for surface in (
                    _normalise_spaces(str(row.get("matched_operand_label") or "")),
                    _normalise_spaces(str(row.get("label") or "")),
                )
                if surface
            ]

        def _candidate_has_other_operand_context(slot: Dict[str, Any], current_row: Dict[str, Any]) -> bool:
            candidate_evidence = self._evidence_item_for_operand_row(slot, evidence_by_id)
            if not candidate_evidence:
                return False
            metadata = dict(candidate_evidence.get("metadata") or {})
            table_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        metadata.get("table_value_labels_text"),
                        metadata.get("table_row_labels_text"),
                        candidate_evidence.get("claim"),
                        candidate_evidence.get("quote_span"),
                        candidate_evidence.get("raw_row_text"),
                    )
                )
            )
            if not table_surface:
                return False
            table_surface_compact = re.sub(r"\s+", "", table_surface)
            current_id = str(current_row.get("operand_id") or "")
            for other_row in ordered_operands:
                if str(other_row.get("operand_id") or "") == current_id:
                    continue
                for surface in _row_surfaces(other_row):
                    if surface in table_surface or re.sub(r"\s+", "", surface) in table_surface_compact:
                        return True
            return False

        aligned: List[Dict[str, Any]] = []
        changed = False
        for row in ordered_operands:
            current_row = dict(row)
            operand = _row_as_operand(current_row)
            if not _normalise_spaces(str(operand.get("label") or operand.get("concept") or "")):
                aligned.append(current_row)
                continue
            candidate_slot, candidate_score = self._best_direct_lookup_slot_from_evidence_pool(
                operand,
                evidence_pool,
            )
            if not candidate_slot or candidate_score <= 0:
                aligned.append(current_row)
                continue
            if not _candidate_has_other_operand_context(candidate_slot, current_row):
                aligned.append(current_row)
                continue
            current_value = current_row.get("normalized_value")
            candidate_value = candidate_slot.get("normalized_value")
            try:
                differs = (
                    current_value is not None
                    and candidate_value is not None
                    and abs(float(current_value) - float(candidate_value)) > 1e-6
                )
            except (TypeError, ValueError):
                differs = current_value != candidate_value
            if not differs:
                aligned.append(current_row)
                continue
            candidate_source_ids = _clean_source_row_ids([
                candidate_slot.get("source_row_id"),
                candidate_slot.get("source_row_ids"),
            ])
            aligned.append(
                {
                    **current_row,
                    "evidence_id": candidate_source_ids[0] if candidate_source_ids else current_row.get("evidence_id"),
                    "source_row_id": candidate_source_ids[0] if candidate_source_ids else current_row.get("source_row_id"),
                    "source_row_ids": candidate_source_ids or list(current_row.get("source_row_ids") or []),
                    "source_anchor": candidate_slot.get("source_anchor") or current_row.get("source_anchor"),
                    "label": candidate_slot.get("label") or current_row.get("label"),
                    "raw_value": candidate_slot.get("raw_value"),
                    "raw_unit": candidate_slot.get("raw_unit"),
                    "normalized_value": candidate_slot.get("normalized_value"),
                    "normalized_unit": candidate_slot.get("normalized_unit"),
                    "period": candidate_slot.get("period") or current_row.get("period"),
                    "sibling_table_context_realigned": True,
                }
            )
            changed = True
        if changed:
            unit_aligned = self._align_ratio_operand_units_with_shared_table_context(aligned)
            return unit_aligned
        return self._align_ratio_operand_units_with_shared_table_context(ordered_operands)

    def _align_dependency_rows_with_sibling_direct_context(
        self,
        dependency_rows: List[Dict[str, Any]],
        direct_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not dependency_rows or len(direct_rows) < 2:
            return dependency_rows

        def _row_binding_key(row: Dict[str, Any]) -> tuple[str, str]:
            return (
                _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or "")),
                _normalise_spaces(str(row.get("matched_operand_role") or "")),
            )

        def _context_key(row: Dict[str, Any]) -> str:
            return _normalise_spaces(
                str(row.get("table_source_id") or row.get("evidence_id") or row.get("source_row_id") or "")
            )

        context_roles: Dict[str, set[str]] = {}
        for row in direct_rows:
            key = _context_key(row)
            role = _normalise_spaces(str(row.get("matched_operand_role") or ""))
            if not key or not role:
                continue
            context_roles.setdefault(key, set()).add(role)

        aligned: List[Dict[str, Any]] = []
        changed = False
        for dependency_row in dependency_rows:
            dep_key = _row_binding_key(dependency_row)
            if not any(dep_key):
                aligned.append(dependency_row)
                continue
            candidates = [
                dict(row)
                for row in direct_rows
                if _row_binding_key(row) == dep_key
                and _context_key(row)
                and len(context_roles.get(_context_key(row), set())) >= 2
            ]
            if not candidates:
                aligned.append(dependency_row)
                continue
            candidate = candidates[0]
            dep_value = dependency_row.get("normalized_value")
            candidate_value = candidate.get("normalized_value")
            try:
                value_differs = (
                    dep_value is not None
                    and candidate_value is not None
                    and abs(float(dep_value) - float(candidate_value)) > 1e-6
                )
            except (TypeError, ValueError):
                value_differs = dep_value != candidate_value
            if not value_differs:
                aligned.append(dependency_row)
                continue
            aligned.append(
                {
                    **dependency_row,
                    "evidence_id": candidate.get("evidence_id") or dependency_row.get("evidence_id"),
                    "source_row_id": candidate.get("source_row_id") or candidate.get("evidence_id") or dependency_row.get("source_row_id"),
                    "source_row_ids": _clean_source_row_ids([
                        candidate.get("source_row_id"),
                        candidate.get("source_row_ids"),
                    ]),
                    "source_anchor": candidate.get("source_anchor") or dependency_row.get("source_anchor"),
                    "label": candidate.get("label") or dependency_row.get("label"),
                    "raw_value": candidate.get("raw_value"),
                    "raw_unit": candidate.get("raw_unit"),
                    "normalized_value": candidate.get("normalized_value"),
                    "normalized_unit": candidate.get("normalized_unit"),
                    "period": candidate.get("period") or dependency_row.get("period"),
                    "statement_type": candidate.get("statement_type") or dependency_row.get("statement_type"),
                    "consolidation_scope": candidate.get("consolidation_scope") or dependency_row.get("consolidation_scope"),
                    "table_source_id": candidate.get("table_source_id") or dependency_row.get("table_source_id"),
                    "sibling_table_context_realigned": True,
                }
            )
            changed = True
        return aligned if changed else dependency_rows

    def _align_growth_operand_units_when_raw_scale_matches(
        self,
        ordered_operands: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if len(ordered_operands) != 2:
            return ordered_operands
        current_index = next(
            (
                index
                for index, row in enumerate(ordered_operands)
                if str(row.get("matched_operand_role") or "").strip() == "current_period"
            ),
            None,
        )
        prior_index = next(
            (
                index
                for index, row in enumerate(ordered_operands)
                if str(row.get("matched_operand_role") or "").strip() == "prior_period"
            ),
            None,
        )
        if current_index is None and prior_index is None:
            current_index, prior_index = 0, 1
        elif current_index is None and prior_index is not None:
            current_index = next((index for index in range(len(ordered_operands)) if index != prior_index), None)
        elif prior_index is None and current_index is not None:
            prior_index = next((index for index in range(len(ordered_operands)) if index != current_index), None)
        if current_index is None or prior_index is None or current_index == prior_index:
            return ordered_operands
        current_row = dict(ordered_operands[current_index])
        prior_row = dict(ordered_operands[prior_index])
        current_concept = _normalise_spaces(str(current_row.get("matched_operand_concept") or ""))
        prior_concept = _normalise_spaces(str(prior_row.get("matched_operand_concept") or ""))
        if current_concept and prior_concept and current_concept != prior_concept:
            return ordered_operands

        current_unit = _normalise_spaces(str(current_row.get("raw_unit") or ""))
        prior_unit = _normalise_spaces(str(prior_row.get("raw_unit") or ""))
        if not current_unit or not prior_unit or current_unit == prior_unit:
            return ordered_operands
        if str(current_row.get("normalized_unit") or "").upper() != "KRW":
            return ordered_operands
        if str(prior_row.get("normalized_unit") or "").upper() != "KRW":
            return ordered_operands

        current_raw_number = _parse_number_text(str(current_row.get("raw_value") or ""))
        prior_raw_number = _parse_number_text(str(prior_row.get("raw_value") or ""))
        current_normalized = current_row.get("normalized_value")
        prior_normalized = prior_row.get("normalized_value")
        if (
            current_raw_number is None
            or prior_raw_number is None
            or not current_raw_number
            or not prior_raw_number
            or current_normalized is None
            or prior_normalized is None
        ):
            return ordered_operands
        try:
            raw_ratio = abs(float(current_raw_number) / float(prior_raw_number))
            normalized_ratio = abs(float(current_normalized) / float(prior_normalized))
        except (TypeError, ValueError, ZeroDivisionError):
            return ordered_operands
        if raw_ratio <= 0 or normalized_ratio <= 0:
            return ordered_operands
        scale_distortion = max(raw_ratio, normalized_ratio) / min(raw_ratio, normalized_ratio)
        if not (0.01 <= raw_ratio <= 100.0 and scale_distortion >= 100.0):
            return ordered_operands

        aligned_prior_value, aligned_prior_unit = _normalise_operand_value(
            str(prior_row.get("raw_value") or ""),
            current_unit,
        )
        if aligned_prior_value is None or aligned_prior_unit != "KRW":
            return ordered_operands
        updated_prior = {
            **prior_row,
            "raw_unit": current_unit,
            "normalized_value": aligned_prior_value,
            "normalized_unit": aligned_prior_unit,
            "unit_alignment_source": "growth_raw_scale_match",
        }
        updated_rows = []
        for index, row in enumerate(ordered_operands):
            if index == prior_index:
                updated_rows.append(updated_prior)
            else:
                updated_rows.append(row)
        return updated_rows

    def _recover_duplicate_growth_prior_operand(
        self,
        ordered_operands: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        if len(ordered_operands) != 2:
            return ordered_operands
        current_row = next(
            (dict(row) for row in ordered_operands if str(row.get("matched_operand_role") or "").strip() == "current_period"),
            None,
        )
        prior_row = next(
            (dict(row) for row in ordered_operands if str(row.get("matched_operand_role") or "").strip() == "prior_period"),
            None,
        )
        if not current_row or not prior_row:
            return ordered_operands
        if not self._growth_slots_share_material(current_row, prior_row, []):
            return ordered_operands

        recovered = self._recover_growth_prior_material_from_evidence(
            current_slot=current_row,
            prior_slot=prior_row,
            evidence_items=evidence_items,
        )
        display = _normalise_spaces(str(recovered.get("display") or ""))
        raw_value = _normalise_spaces(str(recovered.get("raw_value") or ""))
        if not display or not raw_value:
            return ordered_operands

        raw_unit = _normalise_spaces(str(prior_row.get("raw_unit") or current_row.get("raw_unit") or ""))
        normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
        if normalized_value is None:
            return ordered_operands

        updated_prior = {
            **prior_row,
            "period": recovered.get("period") or prior_row.get("period") or "",
            "raw_value": raw_value,
            "raw_unit": raw_unit,
            "normalized_value": normalized_value,
            "normalized_unit": normalized_unit or prior_row.get("normalized_unit") or "",
            "rendered_value": display,
            "source_quote": recovered.get("source_quote") or prior_row.get("source_quote") or "",
            "prior_recovery_source": "evidence_period_display",
        }
        updated_rows = []
        for row in ordered_operands:
            if str(row.get("operand_id") or "") == str(updated_prior.get("operand_id") or ""):
                updated_rows.append(updated_prior)
            else:
                updated_rows.append(row)
        return updated_rows

    def _late_runtime_numeric_answer(
        self,
        state: FinancialAgentState,
        final_answer: str,
    ) -> str:
        trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        calculation_plan = dict(trace.get("calculation_plan") or {})
        calculation_result = dict(trace.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        operation_family = _normalise_spaces(
            str(
                answer_slots.get("operation_family")
                or calculation_result.get("operation_family")
                or calculation_plan.get("operation")
                or ""
            )
        ).lower()
        if operation_family not in {"ratio", "growth_rate", "difference", "sum"}:
            return ""
        status = _normalise_spaces(str(calculation_result.get("status") or "")).lower()
        if status != "ok":
            return ""
        rendered_value = _normalise_spaces(
            str(
                (answer_slots.get("primary_value") or {}).get("rendered_value")
                or calculation_result.get("rendered_value")
                or ""
            )
        )
        if not rendered_value:
            return ""
        answer_text = _normalise_spaces(str(final_answer or ""))
        if rendered_value in answer_text:
            return ""
        if answer_text and not re.search(r"\d", answer_text):
            return ""
        if operation_family == "ratio":
            return self._compact_ratio_answer(
                {
                    **dict(state),
                    "active_subtask": {
                        **dict(state.get("active_subtask") or {}),
                        "metric_label": answer_slots.get("metric_label")
                        or (state.get("active_subtask") or {}).get("metric_label")
                        or "",
                    },
                },
                calculation_result,
            )
        formatted_result = _normalise_spaces(
            str(calculation_result.get("formatted_result") or calculation_result.get("rendered_value") or "")
        )
        if formatted_result and rendered_value in formatted_result:
            return formatted_result
        return rendered_value

    def _compact_ratio_answer(
        self,
        state: FinancialAgentState,
        calculation_result: Dict[str, Any],
    ) -> str:
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        metric_label = _normalise_spaces(
            str(
                answer_slots.get("metric_label")
                or (state.get("active_subtask") or {}).get("metric_label")
                or (state.get("active_subtask") or {}).get("task_id")
                or CALCULATION_RENDER_POLICY.get("ratio_default_metric_label")
                or ""
            )
        )
        primary_value = dict(answer_slots.get("primary_value") or {})
        rendered_value = _normalise_spaces(
            str(primary_value.get("rendered_value") or calculation_result.get("rendered_value") or "")
        )
        periods: List[str] = []
        for entries in dict(answer_slots.get("components_by_group") or {}).values():
            for entry in entries or []:
                period = _normalise_spaces(str((entry or {}).get("period") or ""))
                if period and period not in periods:
                    periods.append(period)
        period_prefix = ""
        render_policy = dict(CALCULATION_RENDER_POLICY)
        period_pattern = str(render_policy.get("ratio_year_period_pattern") or "")
        if len(periods) == 1 and period_pattern and re.fullmatch(period_pattern, periods[0]):
            period_prefix = str(render_policy.get("ratio_period_prefix_template") or "").format(period=periods[0])
        trace = _resolve_runtime_calculation_trace(dict(state), allow_legacy_top_level=False)
        scope = self._ratio_component_consolidation_scope(
            calculation_result,
            list(trace.get("calculation_operands") or []),
        )
        scope_prefixes = dict(render_policy.get("consolidation_scope_answer_prefixes") or {})
        if scope and str(scope_prefixes.get(scope) or ""):
            period_prefix = f"{period_prefix}{scope_prefixes[scope]}"
        if metric_label and rendered_value:
            return str(render_policy.get("ratio_answer_template") or "").format(
                period_prefix=period_prefix,
                metric_label=metric_label,
                rendered_value=rendered_value,
            )
        return rendered_value or metric_label

    def _ratio_component_consolidation_scope(
        self,
        calculation_result: Dict[str, Any],
        operands: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        scopes: List[str] = []
        for entries in dict(answer_slots.get("components_by_group") or {}).values():
            for entry in entries or []:
                scope = _normalise_spaces(str((entry or {}).get("consolidation_scope") or ""))
                if scope in {"consolidated", "separate"} and scope not in scopes:
                    scopes.append(scope)
        for operand in operands or []:
            scope = _normalise_spaces(str((operand or {}).get("consolidation_scope") or ""))
            if scope in {"consolidated", "separate"} and scope not in scopes:
                scopes.append(scope)
        return scopes[0] if len(scopes) == 1 else ""

    def _build_deterministic_lookup_plan(
        self,
        state: FinancialAgentState,
        operands: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        if operation_family not in {"lookup", "single_value"}:
            return None

        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        if required_operands:
            matched_rows = [
                row
                for row in operands
                if any(_operand_row_matches_requirement(row, operand) for operand in required_operands)
            ]
            if len(required_operands) != 1 or len(matched_rows) != 1:
                missing_info = self._infer_missing_info(state, matched_rows)
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
                    "explanation": "direct lookup requires exactly one grounded operand row.",
                    "missing_info": missing_info,
                }
            target_rows = matched_rows
        else:
            if len(operands) != 1:
                return None
            target_rows = operands

        row = dict(target_rows[0])
        operand_id = str(row.get("operand_id") or "").strip()
        if not operand_id:
            return None
        result_unit = str(row.get("raw_unit") or "").strip()
        operation_text = _display_operand_label(str(row.get("label") or active_subtask.get("metric_label") or "조회값"))
        return {
            "status": "ok",
            "mode": "single_value",
            "operation": "lookup",
            "ordered_operand_ids": [operand_id],
            "variable_bindings": [{"variable": "A", "operand_id": operand_id}],
            "formula": "A",
            "pairwise_formula": "",
            "result_unit": result_unit,
            "operation_text": operation_text,
            "explanation": "lookup tasks use a directly grounded value row when available.",
            "missing_info": [],
        }

    def _llm_lookup_operand_has_direct_support(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
        required_operands: List[Dict[str, Any]],
    ) -> bool:
        """Reject lookup operands that are inferred from aggregate prose, not directly stated."""
        if not required_operands:
            return True

        raw_value = _normalise_spaces(str(row.get("raw_value") or ""))
        if not raw_value:
            return False

        matching_operand = next(
            (
                operand
                for operand in required_operands
                if _operand_row_matches_requirement(row, operand)
            ),
            None,
        )
        if matching_operand is None:
            return False

        binding_policy = dict(matching_operand.get("binding_policy") or {})
        requires_surface_contract = bool(
            binding_policy.get("require_surface_contract_for_direct_match")
            or binding_policy.get("require_surface_contract_for_direct_lookup")
        )
        if not evidence_item:
            return False if requires_surface_contract else bool(str(row.get("source_anchor") or "").strip())

        support_raw_value = raw_value
        unit_policy = dict(NUMERIC_UNIT_NORMALIZATION_POLICY)
        inline_unit_match = re.fullmatch(
            str(unit_policy.get("inline_value_unit_pattern") or ""),
            raw_value,
        )
        if inline_unit_match:
            support_raw_value = _normalise_spaces(str(inline_unit_match.group("value") or raw_value))
        raw_compact = re.sub(r"[\s,]", "", support_raw_value)
        if not raw_compact:
            return False

        def _text_supports_operand(text: str) -> bool:
            evidence_text = _normalise_spaces(text)
            if not evidence_text:
                return False
            surface_operand = matching_operand
            positive_surface_match = _text_has_positive_surface(evidence_text, surface_operand)
            if requires_surface_contract and not positive_surface_match:
                return False
            if not (positive_surface_match or _operand_text_match(evidence_text, surface_operand)):
                periodless_label = _normalise_spaces(
                    re.sub(
                        rf"^{KOREAN_PERIOD_PREFIX_RE_FRAGMENT}\s+",
                        "",
                        str(matching_operand.get("label") or ""),
                    )
                )
                if periodless_label and periodless_label != str(matching_operand.get("label") or ""):
                    surface_operand = dict(matching_operand)
                    surface_operand["label"] = periodless_label
                    positive_surface_match = _text_has_positive_surface(evidence_text, surface_operand)
            if requires_surface_contract and not positive_surface_match:
                return False
            if not (positive_surface_match or _operand_text_match(evidence_text, surface_operand)):
                return False
            if _text_has_negative_surface(evidence_text, surface_operand):
                return False
            for match in re.finditer(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", evidence_text):
                if re.sub(r"[\s,]", "", match.group(0)) == raw_compact:
                    return True
            return False

        direct_text = _normalise_spaces(
            " ".join(
                str(value or "")
                for value in (
                    evidence_item.get("claim"),
                    evidence_item.get("quote_span"),
                    evidence_item.get("raw_row_text"),
                )
            )
        )
        if direct_text:
            return _text_supports_operand(direct_text)

        source_context = _normalise_spaces(str(evidence_item.get("source_context") or ""))
        if source_context:
            return _text_supports_operand(source_context)
        return False

    def _operand_row_satisfies_required_surface_contract(
        self,
        row: Dict[str, Any],
        evidence_by_id: Dict[str, Dict[str, Any]],
        required_operands: List[Dict[str, Any]],
    ) -> bool:
        matching_operand = next(
            (
                operand
                for operand in required_operands
                if _operand_row_matches_requirement(row, operand)
            ),
            None,
        )
        if matching_operand is None:
            return False
        binding_policy = dict(matching_operand.get("binding_policy") or {})
        requires_surface_contract = bool(
            binding_policy.get("require_surface_contract_for_direct_match")
            or binding_policy.get("require_surface_contract_for_direct_lookup")
        )
        if not requires_surface_contract:
            return True
        evidence_item = self._evidence_item_for_operand_row(row, evidence_by_id)
        return self._llm_lookup_operand_has_direct_support(row, evidence_item, [matching_operand])

    def _lookup_task_requests_context_dependent_scope(
        self,
        state: FinancialAgentState,
        required_operands: List[Dict[str, Any]],
    ) -> bool:
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        markers = tuple(
            _normalise_spaces(str(item)).lower()
            for item in (scoring_policy.get("context_dependent_lookup_scope_markers") or ())
            if _normalise_spaces(str(item))
        )
        if not markers:
            return False
        active_subtask = dict(state.get("active_subtask") or {})
        text_parts: List[str] = [
            str(state.get("query") or ""),
            str(active_subtask.get("query") or ""),
            str(active_subtask.get("metric_label") or ""),
        ]
        for operand in required_operands:
            operand_data = dict(operand or {})
            binding_policy = dict(operand_data.get("binding_policy") or {})
            constraints = dict(operand_data.get("constraints") or {})
            text_parts.extend(
                str(value or "")
                for value in (
                    operand_data.get("label"),
                    operand_data.get("concept"),
                    binding_policy.get("segment_label"),
                    binding_policy.get("entity_label"),
                    constraints.get("segment_scope"),
                )
            )
            text_parts.extend(str(alias or "") for alias in (operand_data.get("aliases") or []))
        task_text = _normalise_spaces(" ".join(text_parts)).lower()
        return any(marker in task_text for marker in markers)

    def _lookup_direct_row_is_ambiguous_context_table(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
        *,
        state: FinancialAgentState,
        required_operands: List[Dict[str, Any]],
    ) -> bool:
        if self._lookup_task_requests_context_dependent_scope(state, required_operands):
            return False
        if not evidence_item:
            return False
        metadata = dict(evidence_item.get("metadata") or {})
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        context_table_views = {
            _normalise_spaces(str(item)).lower()
            for item in (scoring_policy.get("context_dependent_table_views") or ())
            if _normalise_spaces(str(item))
        }
        table_view = _normalise_spaces(str(metadata.get("table_view") or "")).lower()
        if context_table_views and table_view not in context_table_views:
            return False
        try:
            min_cell_count = int(scoring_policy.get("ambiguous_lookup_min_structured_cells") or 4)
        except (TypeError, ValueError):
            min_cell_count = 4
        try:
            min_header_count = int(scoring_policy.get("ambiguous_lookup_min_distinct_column_headers") or 3)
        except (TypeError, ValueError):
            min_header_count = 3
        structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if isinstance(cell, dict)]
        if len(structured_cells) < min_cell_count:
            return False
        scope_markers = tuple(
            _normalise_spaces(str(item)).lower()
            for item in (scoring_policy.get("context_dependent_lookup_scope_markers") or ())
            if _normalise_spaces(str(item))
        )
        distinct_context_headers: set[str] = set()
        for cell in structured_cells:
            headers = [
                _normalise_spaces(str(header)).lower()
                for header in (cell.get("column_headers") or [])
                if _normalise_spaces(str(header))
            ]
            header_text = " ".join(headers)
            if not header_text:
                continue
            if scope_markers and not any(marker in header_text for marker in scope_markers):
                continue
            distinct_context_headers.add(header_text)
        if len(distinct_context_headers) >= min_header_count:
            return True
        raw_surface = _normalise_spaces(
            " ".join(
                str(value or "")
                for value in (
                    row.get("source_context"),
                    evidence_item.get("source_context"),
                    evidence_item.get("claim"),
                    evidence_item.get("quote_span"),
                    metadata.get("table_header_context"),
                )
            )
        ).lower()
        return bool(scope_markers and any(marker in raw_surface for marker in scope_markers))

    def _build_deterministic_ontology_plan(
        self,
        state: FinancialAgentState,
        operands: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        active_subtask = dict(state.get("active_subtask") or {})
        metric_key = self._calc_metric_family(state)

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
        for operand in required_operands:
            matched_row = next((row for row in operands if _operand_row_matches_requirement(row, operand)), None)
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
            result_unit = str(active_subtask.get("result_unit") or metric_info.get("result_unit") or "").strip()
            if not result_unit:
                result_unit = "%"
            if result_unit.upper() == "PERCENT":
                result_unit = "%"
            percent_result = result_unit in {"%", "퍼센트"} or result_unit.upper() == "PERCENT"
            formula = f"(({numerator_expr}) / ({denominator_expr}))"
            operation_suffix = ""
            if percent_result:
                formula = f"{formula} * 100"
                operation_suffix = " * 100"

            numerator_labels = [str(operand.get("label") or "").strip() for operand, _row in numerator_pairs]
            denominator_labels = [str(operand.get("label") or "").strip() for operand, _row in denominator_pairs]

            return {
                "status": "ok",
                "mode": "single_value",
                "operation": "ratio",
                "ordered_operand_ids": ordered_operand_ids,
                "variable_bindings": variable_bindings,
                "formula": formula,
                "pairwise_formula": "",
                "result_unit": result_unit,
                "operation_text": f"({' + '.join(numerator_labels)}) / ({' + '.join(denominator_labels)}){operation_suffix}",
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

    def _build_deterministic_operation_plan(
        self,
        state: FinancialAgentState,
        operands: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        if operation_family not in {"difference", "growth_rate"}:
            return None

        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        if not required_operands:
            return None

        matched_rows: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
        for operand in required_operands:
            matched_row = next((row for row in operands if _operand_row_matches_requirement(row, operand)), None)
            if matched_row is None:
                return None
            matched_rows.append((operand, matched_row))

        def _first_pair(role: str) -> Optional[tuple[Dict[str, Any], Dict[str, Any]]]:
            for operand, row in matched_rows:
                if str(operand.get("role") or "").strip() == role:
                    return operand, row
            return None

        ordered_pairs: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
        if operation_family == "difference":
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
            variable_bindings.append({"variable": chr(ord("A") + index), "operand_id": operand_id})
            ordered_operand_ids.append(operand_id)
            ordered_labels.append(str(operand.get("label") or row.get("label") or "").strip())

        metric_label = str(active_subtask.get("metric_label") or active_subtask.get("task_id") or "").strip()
        if operation_family == "difference":
            result_unit = ""
            if _should_coerce_percent_point_unit(self._calc_query(state), operands, {"operation": "subtract"}):
                result_unit = "%p"
            right_role = str(ordered_pairs[1][0].get("role") or "").strip()
            right_value = ordered_pairs[1][1].get("normalized_value")
            formula = "A - B"
            operation_text = f"{ordered_labels[0]} - {ordered_labels[1]}"
            explanation = f"{metric_label or 'difference'} is computed as A - B."
            if right_role in {"subtrahend", "denominator"} and right_value is not None and float(right_value) < 0:
                formula = "A + B"
                operation_text = f"{ordered_labels[0]} + {ordered_labels[1]}"
                explanation = f"{metric_label or 'difference'} uses sign-aware subtraction because B is already negative."
            return {
                "status": "ok",
                "mode": "single_value",
                "operation": "subtract",
                "ordered_operand_ids": ordered_operand_ids,
                "variable_bindings": variable_bindings,
                "formula": formula,
                "pairwise_formula": "",
                "result_unit": result_unit,
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
            "explanation": f"{metric_label or 'growth rate'} is computed as ((A - B) / B) * 100.",
            "missing_info": [],
        }

    def _extract_calculation_operands(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Build the operand set for the current calculation subtask.

        The flow is intentionally layered:
        1. direct structured-row extraction from reconciliation
        2. evidence-based fallback extraction
        3. merge partial direct hits with fallback rows
        """
        evidence_items = list(state.get("evidence_items", []) or [])
        evidence_bullets = list(state.get("evidence_bullets", []) or [])
        retrieved_docs = state.get("retrieved_docs", []) or []
        seed_retrieved_docs = state.get("seed_retrieved_docs", []) or []
        evidence_status = str(state.get("evidence_status") or "")
        intent = state.get("intent") or state.get("query_type", "qa")
        query = self._calc_query(state)
        topic = self._calc_topic(state)
        report_scope = dict(state.get("report_scope") or {})
        desired_consolidation_scope = _desired_consolidation_scope(query, report_scope)

        def evidence_conflicts_requested_scope(item: Dict[str, Any]) -> bool:
            if desired_consolidation_scope == "unknown":
                return False
            scope_policy = dict(CONSOLIDATION_SCOPE_POLICY.get("context_markers") or {})
            consolidated_markers = tuple(
                str(marker).lower() for marker in (scope_policy.get("consolidated") or ()) if str(marker)
            )
            metadata = dict((item or {}).get("metadata") or {})
            scope = _normalise_spaces(str(metadata.get("consolidation_scope") or "unknown"))
            section_path = _normalise_spaces(str(metadata.get("section_path") or metadata.get("section") or ""))
            section_path_lower = section_path.lower()
            if scope == desired_consolidation_scope:
                return False
            if desired_consolidation_scope == "consolidated":
                if scope == "separate":
                    return True
                return bool(
                    section_path
                    and consolidated_markers
                    and not any(marker in section_path_lower for marker in consolidated_markers)
                )
            if desired_consolidation_scope == "separate":
                if scope == "consolidated":
                    return True
                return any(marker in section_path_lower for marker in consolidated_markers)
            return False

        def operand_conflicts_requested_scope(row: Dict[str, Any]) -> bool:
            if desired_consolidation_scope == "unknown":
                return False
            scope = _normalise_spaces(str(row.get("consolidation_scope") or "unknown"))
            if scope == desired_consolidation_scope:
                return False
            if desired_consolidation_scope == "consolidated":
                return scope == "separate"
            if desired_consolidation_scope == "separate":
                return scope == "consolidated"
            return False

        empty_result: Dict[str, Any] = {
            "calculation_debug_trace": {"coverage": "missing"},
            "answer": "",
            "evidence_items": evidence_items,
            "evidence_bullets": evidence_bullets,
            **_runtime_trace_state_update(
                state,
                calculation_operands=[],
                calculation_plan={},
                calculation_result={},
                include_compatibility_mirrors=False,
            ),
        }
        direct_structured_rows = self._extract_structured_operands_from_reconciliation(state)
        reconciliation_evidence = self._evidence_items_from_reconciliation_matches(state)
        if reconciliation_evidence:
            existing_ids = {str(item.get("evidence_id") or "").strip() for item in evidence_items}
            appended = 0
            for item in reconciliation_evidence:
                evidence_id = str(item.get("evidence_id") or "").strip()
                if evidence_id and evidence_id in existing_ids:
                    continue
                if evidence_id:
                    existing_ids.add(evidence_id)
                evidence_items.append(item)
                raw_row = _normalise_spaces(str(item.get("raw_row_text") or item.get("claim") or ""))
                evidence_bullets.append(f"- {item.get('source_anchor')} {raw_row[:180]} (reconciled)")
                appended += 1
            if appended:
                logger.info("[calc_operands] appended reconciled evidence items=%s", appended)
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        metric_family = str(active_subtask.get("metric_family") or "").strip().lower()
        if operation_family == "concept_lookup" or (not operation_family and metric_family == "concept_lookup"):
            operation_family = "lookup"
        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        direct_numeric_grounding = _requires_direct_numeric_grounding(active_subtask)
        surface_contract_evidence = self._surface_contract_numeric_evidence_items(
            evidence_items,
            required_operands,
        )
        preserve_narrative_context = (
            direct_numeric_grounding
            and _query_requests_narrative_context(str(state.get("query") or ""))
        )
        if direct_numeric_grounding and reconciliation_evidence:
            if preserve_narrative_context:
                evidence_items = self._restrict_direct_numeric_evidence_items(
                    evidence_items,
                    preserve_narrative_context=True,
                )
                evidence_bullets = [
                    f"- {item.get('source_anchor')} {str(item.get('raw_row_text') or item.get('quote_span') or item.get('claim') or '')[:180]} ({'reconciled' if self._is_direct_numeric_table_backed_evidence_item(item) else 'narrative'})"
                    for item in evidence_items
                ]
                logger.info(
                    "[calc_operands] direct numeric task preserves hybrid evidence structured=%s total=%s",
                    len(reconciliation_evidence),
                    len(evidence_items),
                )
            else:
                evidence_items = list(reconciliation_evidence)
                existing_surface_keys = {
                    (
                        str(existing.get("evidence_id") or "").strip(),
                        str(existing.get("source_anchor") or "").strip(),
                        _normalise_spaces(
                            str(
                                existing.get("raw_row_text")
                                or existing.get("quote_span")
                                or existing.get("claim")
                                or ""
                            )
                        ),
                    )
                    for existing in evidence_items
                }
                for item in surface_contract_evidence:
                    evidence_id = str(item.get("evidence_id") or "").strip()
                    source_anchor = str(item.get("source_anchor") or "").strip()
                    row_text = _normalise_spaces(
                        str(item.get("raw_row_text") or item.get("quote_span") or item.get("claim") or "")
                    )
                    surface_key = (evidence_id, source_anchor, row_text)
                    if surface_key in existing_surface_keys:
                        continue
                    existing_surface_keys.add(surface_key)
                    evidence_items.append(item)
                evidence_bullets = [
                    f"- {item.get('source_anchor')} {str(item.get('raw_row_text') or item.get('quote_span') or item.get('claim') or '')[:180]} ({'reconciled' if item in reconciliation_evidence else 'surface-contract'})"
                    for item in evidence_items
                ]
                logger.info(
                    "[calc_operands] direct numeric task restricts evidence to reconciled structured candidates=%s surface_contract=%s total=%s",
                    len(reconciliation_evidence),
                    len(surface_contract_evidence),
                    len(evidence_items),
                )
        if direct_structured_rows:
            evidence_by_id = {
                str(item.get("evidence_id") or "").strip(): dict(item)
                for item in evidence_items
                if str(item.get("evidence_id") or "").strip()
            }
            direct_structured_rows = [
                self._coerce_operand_row_from_evidence(
                    row,
                    self._evidence_item_for_operand_row(row, evidence_by_id),
                )
                for row in direct_structured_rows
            ]
            direct_structured_rows = [
                row
                for row in direct_structured_rows
                if not operand_conflicts_requested_scope(row)
            ]
        if direct_structured_rows and required_operands:
            evidence_by_id = {
                str(item.get("evidence_id") or "").strip(): dict(item)
                for item in evidence_items
                if str(item.get("evidence_id") or "").strip()
            }
            direct_structured_rows = [
                row
                for row in direct_structured_rows
                if any(_operand_row_matches_requirement(row, operand) for operand in required_operands)
                and self._operand_row_satisfies_required_surface_contract(row, evidence_by_id, required_operands)
            ]
            direct_structured_rows = [
                row
                for row in direct_structured_rows
                if not self._lookup_direct_row_is_ambiguous_context_table(
                    row,
                    self._evidence_item_for_operand_row(row, evidence_by_id),
                    state=state,
                    required_operands=required_operands,
                )
            ]
        if direct_structured_rows and operation_family in {"lookup", "single_value"}:
            evidence_by_id = {
                str(item.get("evidence_id") or "").strip(): dict(item)
                for item in evidence_items
                if str(item.get("evidence_id") or "").strip()
            }
            if required_operands:
                direct_structured_rows = [
                    row
                    for row in direct_structured_rows
                    if self._llm_lookup_operand_has_direct_support(
                        row,
                        self._evidence_item_for_operand_row(row, evidence_by_id),
                        required_operands,
                    )
                ]
            direct_structured_rows = [
                row
                for row in direct_structured_rows
                if not self._lookup_direct_row_is_ambiguous_context_table(
                    row,
                    self._evidence_item_for_operand_row(row, evidence_by_id),
                    state=state,
                    required_operands=required_operands,
                )
            ]
        if direct_structured_rows and required_operands and operation_family in {"lookup", "single_value"}:
            evidence_by_id = {
                str(item.get("evidence_id") or "").strip(): dict(item)
                for item in evidence_items
                if str(item.get("evidence_id") or "").strip()
            }
            lookup_preference_evidence = list(evidence_items)
            existing_preference_ids = {
                str(item.get("evidence_id") or "").strip()
                for item in lookup_preference_evidence
                if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
            }
            for item in state.get("runtime_evidence") or []:
                if not isinstance(item, dict):
                    continue
                evidence_id = str(item.get("evidence_id") or "").strip()
                if evidence_id and evidence_id in existing_preference_ids:
                    continue
                if evidence_id:
                    existing_preference_ids.add(evidence_id)
                lookup_preference_evidence.append(dict(item))
            direct_structured_rows = self._prefer_direct_structured_lookup_evidence_rows(
                direct_structured_rows,
                evidence_items=lookup_preference_evidence,
                required_operands=required_operands,
                operation_family=operation_family,
            )
        dependency_state = self._dependency_binding_resolution_state(state)
        dependency_rows = list(dependency_state.get("rows") or [])
        dependency_bindings = list(dependency_state.get("bindings") or [])
        dependency_resolved_keys = set(dependency_state.get("resolved_keys") or set())
        missing_dependency_bindings = list(dependency_state.get("missing_bindings") or [])
        rejected_dependency_scope_rows: List[Dict[str, Any]] = []
        retry_strategy = self._active_retry_strategy(state)
        synthesis_only_retry = (
            retry_strategy == "synthesize_from_task_outputs"
            and self._task_prefers_sibling_output_synthesis(state)
        )
        direct_rows_cover_required_operands = bool(
            required_operands
            and direct_structured_rows
            and not _missing_required_operands(required_operands, direct_structured_rows)
        )
        prefer_direct_rows_over_dependency = bool(
            operation_family == "ratio"
            and direct_rows_cover_required_operands
            and reconciliation_evidence
        )
        if dependency_rows:
            if operation_family == "ratio":
                dependency_rows = self._align_dependency_rows_with_sibling_direct_context(
                    dependency_rows,
                    direct_structured_rows,
                )
            if prefer_direct_rows_over_dependency:
                direct_structured_rows = _merge_operand_rows(
                    direct_structured_rows,
                    dependency_rows,
                    required_operands=required_operands,
                )
            else:
                direct_structured_rows = _merge_operand_rows(
                    dependency_rows,
                    direct_structured_rows,
                    required_operands=required_operands,
                )
            direct_structured_rows = [
                row
                for row in direct_structured_rows
                if not operand_conflicts_requested_scope(row)
            ]
            logger.info("[calc_operands] dependency task-output operands=%s", len(dependency_rows))
        if dependency_bindings and direct_structured_rows:
            direct_structured_rows, rejected_resolved_dependency_scope_rows = self._filter_direct_rows_by_dependency_producer_scope(
                state,
                bindings=dependency_bindings,
                operand_rows=direct_structured_rows,
            )
            rejected_dependency_scope_rows.extend(rejected_resolved_dependency_scope_rows)
        if missing_dependency_bindings and direct_structured_rows:
            direct_structured_rows, rejected_missing_dependency_scope_rows = self._filter_direct_rows_by_dependency_producer_scope(
                state,
                bindings=missing_dependency_bindings,
                operand_rows=direct_structured_rows,
            )
            rejected_dependency_scope_rows.extend(rejected_missing_dependency_scope_rows)
        dependency_binding_keys = set(dependency_state.get("binding_keys") or set())
        direct_dependency_fill_allowed = operation_family in {"difference", "growth_rate"} or prefer_direct_rows_over_dependency
        if dependency_binding_keys and direct_structured_rows:
            duplicate_guard_keys = dependency_resolved_keys
            if prefer_direct_rows_over_dependency:
                duplicate_guard_keys = set()
            if not direct_dependency_fill_allowed:
                duplicate_guard_keys = dependency_binding_keys
            filtered_rows: List[Dict[str, Any]] = []
            for row in direct_structured_rows:
                if bool(row.get("dependency_resolved")):
                    filtered_rows.append(row)
                    continue
                row_key = (
                    _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or "")),
                    _normalise_spaces(str(row.get("matched_operand_role") or "")),
                )
                if row_key in duplicate_guard_keys:
                    continue
                filtered_rows.append(row)
            direct_structured_rows = filtered_rows
        if direct_dependency_fill_allowed and missing_dependency_bindings and direct_structured_rows:
            direct_resolved_keys = self._direct_rows_resolved_dependency_keys(
                missing_dependency_bindings,
                direct_structured_rows,
            )
            if direct_resolved_keys:
                missing_dependency_bindings = [
                    dict(binding)
                    for binding in missing_dependency_bindings
                    if self._dependency_binding_identity(binding) not in direct_resolved_keys
                ]
        has_retrieved_docs_for_dependency_fallback = bool(retrieved_docs or seed_retrieved_docs)
        has_active_reconciliation_fallback = bool(reconciliation_evidence)
        allow_dependency_retry_fallback = (
            operation_family in {"ratio", "difference"}
            and bool(missing_dependency_bindings)
            and (
                has_active_reconciliation_fallback
                or (
                    not bool(rejected_dependency_scope_rows)
                    and (
                        int(state.get("reconciliation_retry_count") or 0) > 0
                        or has_retrieved_docs_for_dependency_fallback
                    )
                )
            )
        )
        if allow_dependency_retry_fallback:
            direct_numeric_grounding = False
        dependency_guard_active = (
            bool(dependency_bindings)
            and bool(missing_dependency_bindings)
            and not allow_dependency_retry_fallback
        )
        if dependency_guard_active:
            coverage = "partial" if direct_structured_rows else "missing"
            logger.info(
                "[calc_operands] dependency binding guard blocks fallback missing_bindings=%s operands=%s",
                len(missing_dependency_bindings),
                len(direct_structured_rows),
            )
            return {
                "calculation_debug_trace": {
                    "coverage": coverage,
                    "source": "dependency_binding_guard",
                    "retry_strategy": retry_strategy,
                    "dependency_operands": dependency_rows,
                    "missing_dependency_bindings": missing_dependency_bindings,
                    "rejected_dependency_scope_rows": rejected_dependency_scope_rows,
                    "operands": direct_structured_rows,
                },
                "evidence_items": evidence_items,
                "evidence_bullets": evidence_bullets,
                "evidence_status": coverage,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=direct_structured_rows,
                    calculation_plan={},
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }
        # If reconciliation already found every required operand as clean
        # structured rows, skip the broader fallback path entirely.
        if direct_structured_rows and (
            not required_operands or len(direct_structured_rows) >= len(required_operands)
        ):
            logger.info("[calc_operands] structured-row direct operands=%s", len(direct_structured_rows))
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str(active_subtask.get("task_id") or "calc")
            artifacts = self._enrich_reconciliation_artifact_refs(
                artifacts,
                task_id=task_id,
                operand_rows=direct_structured_rows,
            )
            artifact_id = f"operands:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.OPERAND_SET,
                status="ok",
                summary=f"{len(direct_structured_rows)} structured operand(s)",
                payload={"calculation_operands": direct_structured_rows, "source": "structured_row_direct"},
                evidence_refs=[str(row.get("evidence_id") or "") for row in direct_structured_rows if str(row.get("evidence_id") or "").strip()],
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str(active_subtask.get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
            return {
                "calculation_debug_trace": {
                    "coverage": "sufficient",
                    "source": "structured_row_direct",
                    "dependency_operands": dependency_rows,
                    "operands": direct_structured_rows,
                },
                "evidence_items": evidence_items,
                "evidence_bullets": evidence_bullets,
                "evidence_status": "sufficient",
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=direct_structured_rows,
                    calculation_plan={},
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }
        if synthesis_only_retry:
            coverage = "missing"
            if direct_structured_rows:
                coverage = (
                    "sufficient"
                    if not _missing_required_operands(required_operands, direct_structured_rows)
                    else "partial"
                )
            logger.info(
                "[calc_operands] synthesis-only retry blocks broad fallback coverage=%s operands=%s",
                coverage,
                len(direct_structured_rows),
            )
            return {
                "calculation_debug_trace": {
                    "coverage": coverage,
                    "source": "dependency_synthesis_only",
                    "retry_strategy": retry_strategy,
                    "dependency_operands": dependency_rows,
                    "operands": direct_structured_rows,
                },
                "evidence_items": evidence_items,
                "evidence_bullets": evidence_bullets,
                "evidence_status": coverage,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=direct_structured_rows,
                    calculation_plan={},
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }
        should_augment_with_docs = (
            not direct_numeric_grounding
            and
            bool(retrieved_docs or seed_retrieved_docs)
            and intent in {"comparison", "trend"}
            and (not evidence_items or evidence_status != "sufficient")
        )
        if should_augment_with_docs:
            candidate_docs = list(retrieved_docs)
            seen_candidate_doc_ids = {
                str((getattr(doc, "metadata", {}) or {}).get("chunk_uid") or (getattr(doc, "metadata", {}) or {}).get("chunk_id") or "")
                for doc, _score in candidate_docs
            }
            for doc, score in seed_retrieved_docs:
                metadata = dict(getattr(doc, "metadata", {}) or {})
                doc_id = str(metadata.get("chunk_uid") or metadata.get("chunk_id") or "")
                if doc_id and doc_id in seen_candidate_doc_ids:
                    continue
                if doc_id:
                    seen_candidate_doc_ids.add(doc_id)
                candidate_docs.append((doc, score))
            synthesized_items: List[Dict[str, Any]] = []
            synthesized_bullets: List[str] = []
            seen_anchors = {str(item.get("source_anchor") or "") for item in evidence_items}

            def _required_operand_context_terms() -> List[str]:
                terms: List[str] = []
                for operand in required_operands:
                    for needle in _operand_needles(operand):
                        normalized = _normalise_spaces(re.sub(rf"^{KOREAN_PERIOD_PREFIX_RE_FRAGMENT}\s+", "", needle))
                        if not normalized:
                            continue
                        terms.append(normalized)
                        tokens = normalized.split()
                        if len(tokens) >= 2:
                            terms.append(" ".join(tokens[:-1]))
                expanded: List[str] = []
                for term in terms:
                    expanded.append(term)
                    if re.search(r"[가-힣]", term) and " " in term:
                        expanded.append(re.sub(r"\s+", "", term))
                return list(dict.fromkeys(item for item in expanded if item))

            def _text_has_any_context_term(text: str, terms: List[str]) -> bool:
                normalized = _normalise_spaces(text)
                compact = re.sub(r"\s+", "", normalized)
                return any(
                    term in normalized or re.sub(r"\s+", "", term) in compact
                    for term in terms
                    if term
                )

            def _synthesized_doc_item(
                doc: Any,
                *,
                index: int,
                evidence_id: str,
            ) -> Optional[Dict[str, Any]]:
                metadata = dict(getattr(doc, "metadata", {}) or {})
                anchor = self._build_source_anchor(metadata)
                text = _normalise_spaces(str(getattr(doc, "page_content", "") or ""))
                if not text:
                    return None
                display_text = _strip_rerank_metadata(text) or text
                provisional_item = {"metadata": metadata, "source_anchor": anchor, "claim": text}
                if evidence_conflicts_requested_scope(provisional_item):
                    return None
                claim = display_text[:1200]
                return {
                    "evidence_id": evidence_id,
                    "source_anchor": anchor,
                    "claim": claim,
                    "quote_span": claim[:240],
                    "support_level": "direct",
                    "question_relevance": "high",
                    "allowed_terms": [],
                    "metadata": metadata,
                    "_candidate_index": index,
                }

            if required_operands:
                operand_probe_items: List[Dict[str, Any]] = []
                for candidate_index, (doc, _score) in enumerate(candidate_docs, start=1):
                    full_text = _normalise_spaces(str(getattr(doc, "page_content", "") or ""))
                    full_text = _strip_rerank_metadata(full_text) or full_text
                    item = _synthesized_doc_item(
                        doc,
                        index=candidate_index,
                        evidence_id=f"ev_operand_doc_{candidate_index:03d}",
                    )
                    if item:
                        probe_item = dict(item)
                        probe_item["claim"] = full_text
                        probe_item["raw_row_text"] = full_text
                        operand_probe_items.append(probe_item)
                operand_probe_rows = self._build_required_operands_from_candidates(
                    operand_probe_items,
                    required_operands=required_operands,
                    query=query,
                    topic=topic,
                    report_scope=report_scope,
                )
                operand_evidence_ids = {
                    str(row.get("evidence_id") or "")
                    for row in operand_probe_rows
                    if row.get("evidence_id")
                }
                if operand_evidence_ids:
                    max_operand_docs = max(4, len(required_operands) * 2)
                    for item in operand_probe_items:
                        if str(item.get("evidence_id") or "") not in operand_evidence_ids:
                            continue
                        anchor = str(item.get("source_anchor") or "")
                        claim = str(item.get("claim") or "")
                        missing_terms: List[str] = []
                        for binding in missing_dependency_bindings:
                            missing_terms.extend(_operand_needles(dict(binding)))
                            label = _normalise_spaces(str(binding.get("label") or ""))
                            if label:
                                missing_terms.append(label)
                        missing_terms.extend(_required_operand_context_terms())
                        missing_terms = [term for term in dict.fromkeys(missing_terms) if term]
                        duplicate_anchor_has_missing_term = bool(
                            anchor in seen_anchors
                            and missing_terms
                            and _text_has_any_context_term(claim, missing_terms)
                        )
                        if anchor in seen_anchors and not duplicate_anchor_has_missing_term:
                            continue
                        evidence_item = dict(item)
                        evidence_item.pop("raw_row_text", None)
                        evidence_item.pop("_candidate_index", None)
                        evidence_item["claim"] = claim[:1200]
                        evidence_item["quote_span"] = claim[:240]
                        evidence_item["raw_row_text"] = claim
                        synthesized_items.append(evidence_item)
                        synthesized_bullets.append(f"- {anchor} {claim[:180]} (direct)")
                        seen_anchors.add(anchor)
                        if len(
                            [
                                existing
                                for existing in synthesized_items
                                if str(existing.get("evidence_id") or "").startswith("ev_operand_doc_")
                            ]
                        ) >= max_operand_docs:
                            break

            percent_point_query = _is_percent_point_difference_query(query)
            ratio_row_candidates = self._extract_ratio_row_candidates(candidate_docs, query, topic)
            if ratio_row_candidates:
                logger.info("[calc_operands] ratio row fallback candidates=%s", len(ratio_row_candidates))
                synthesized_items.extend(ratio_row_candidates)
                synthesized_bullets.extend(
                    f"- {item['source_anchor']} {item.get('source_context', '')} {str(item.get('raw_row_text') or '')[:180]} (direct)"
                    for item in ratio_row_candidates
                )
                seen_anchors.update(str(item.get("source_anchor") or "") for item in ratio_row_candidates)
            if not percent_point_query:
                component_candidates = self._extract_ratio_component_candidates(candidate_docs, query, topic)
                if component_candidates:
                    logger.info("[calc_operands] ratio component fallback candidates=%s", len(component_candidates))
                    synthesized_items.extend(component_candidates)
                    synthesized_bullets.extend(
                        f"- {item['source_anchor']} {item.get('source_context', '')} {str(item.get('raw_row_text') or '')[:180]} (direct)"
                        for item in component_candidates
                    )
                    seen_anchors.update(str(item.get("source_anchor") or "") for item in component_candidates)
            doc_fallback_limit = 16 if missing_dependency_bindings else 8
            for index, (doc, _score) in enumerate(candidate_docs[: min(doc_fallback_limit, len(candidate_docs))], start=1):
                item = _synthesized_doc_item(doc, index=index, evidence_id=f"ev_doc_{index:03d}")
                if not item:
                    continue
                metadata = dict(item.get("metadata") or {})
                anchor = str(item.get("source_anchor") or "")
                text = str(item.get("claim") or "")
                missing_terms: List[str] = []
                for binding in missing_dependency_bindings:
                    missing_terms.extend(_operand_needles(dict(binding)))
                    label = _normalise_spaces(str(binding.get("label") or ""))
                    if label:
                        missing_terms.append(label)
                missing_terms.extend(_required_operand_context_terms())
                missing_terms = [term for term in dict.fromkeys(missing_terms) if term]
                duplicate_anchor_has_missing_term = bool(
                    anchor in seen_anchors
                    and missing_terms
                    and _text_has_any_context_term(text, missing_terms)
                )
                if anchor in seen_anchors and not duplicate_anchor_has_missing_term:
                    continue
                item.pop("_candidate_index", None)
                synthesized_items.append(item)
                synthesized_bullets.append(f"- {anchor} {text[:180]} (direct)")
            if synthesized_items:
                evidence_items = evidence_items + synthesized_items
                evidence_bullets = evidence_bullets + synthesized_bullets
                logger.info(
                    "[calc_operands] augmenting evidence with synthesized retrieved_docs=%s existing=%s",
                    len(synthesized_items),
                    len(state.get("evidence_items", []) or []),
                )
        elif direct_numeric_grounding and (retrieved_docs or seed_retrieved_docs) and (not evidence_items or evidence_status != "sufficient"):
            logger.info("[calc_operands] direct numeric task skips generic retrieved-doc augmentation")
        if not evidence_items:
            return empty_result

        deterministic_required_rows: List[Dict[str, Any]] = []
        if required_operands and not direct_numeric_grounding:
            deterministic_required_rows = self._build_required_operands_from_candidates(
                evidence_items,
                required_operands=required_operands,
                query=query,
                topic=topic,
                report_scope=report_scope,
            )
            if missing_dependency_bindings and deterministic_required_rows:
                deterministic_required_rows, rejected_rows = self._filter_direct_rows_by_dependency_producer_scope(
                    state,
                    bindings=missing_dependency_bindings,
                    operand_rows=deterministic_required_rows,
                )
                rejected_dependency_scope_rows.extend(rejected_rows)
            if deterministic_required_rows:
                direct_structured_rows = _merge_operand_rows(
                    direct_structured_rows,
                    deterministic_required_rows,
                    required_operands=required_operands,
                )
                logger.info(
                    "[calc_operands] deterministic required-operand rows=%s",
                    len(deterministic_required_rows),
                )

        structured_llm = self._llm_for_phase("operand_extraction").with_structured_output(OperandExtraction)
        evidence_text = self._format_evidence_for_prompt(evidence_items, evidence_bullets)
        prompt = ChatPromptTemplate.from_template(
            str(CALCULATION_PROMPT_POLICY.get("operand_extraction_prompt_template") or "")
        )
        try:
            extracted: OperandExtraction = (prompt | structured_llm).invoke(
                {"query": query, "evidence": evidence_text}
            )
            operand_rows: List[Dict[str, Any]] = []
            evidence_by_id = {
                str(item.get("evidence_id") or "").strip(): dict(item)
                for item in evidence_items
                if str(item.get("evidence_id") or "").strip()
            }
            for index, item in enumerate(extracted.operands, start=1):
                row = item.model_dump()
                evidence_item = evidence_by_id.get(str(row.get("evidence_id") or "").strip())
                if evidence_item and evidence_conflicts_requested_scope(evidence_item):
                    continue
                row["operand_id"] = f"op_{index:03d}"
                row = self._coerce_operand_row_from_evidence(row, evidence_item)
                if operation_family in {"lookup", "single_value"} and required_operands:
                    if not self._llm_lookup_operand_has_direct_support(row, evidence_item, required_operands):
                        continue
                operand_rows.append(row)
            if required_operands:
                operand_rows = [
                    row
                    for row in operand_rows
                    if any(_operand_row_matches_requirement(row, operand) for operand in required_operands)
                    and self._operand_row_satisfies_required_surface_contract(row, evidence_by_id, required_operands)
                ]
            if operation_family in {"lookup", "single_value"} and required_operands:
                operand_rows = [
                    row
                    for row in operand_rows
                    if any(_operand_row_matches_requirement(row, operand) for operand in required_operands)
                ]
            if direct_structured_rows and required_operands:
                operand_rows = _merge_operand_rows(
                    direct_structured_rows,
                    operand_rows,
                    required_operands=required_operands,
                )

            missing_required = _missing_required_operands(required_operands, operand_rows) if required_operands else []
            if missing_required and surface_contract_evidence:
                surface_fallback_rows = self._build_required_operands_from_candidates(
                    surface_contract_evidence,
                    required_operands=missing_required,
                    query=query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
                if surface_fallback_rows:
                    logger.info("[calc_operands] surface-contract operand fallback rows=%s", len(surface_fallback_rows))
                    operand_rows = _merge_operand_rows(
                        operand_rows,
                        surface_fallback_rows,
                        required_operands=required_operands,
                    )
                    missing_required = _missing_required_operands(required_operands, operand_rows) if required_operands else []
            if missing_required and not direct_numeric_grounding:
                generic_fallback_rows = self._build_required_operands_from_candidates(
                    evidence_items,
                    required_operands=missing_required,
                    query=query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
                if generic_fallback_rows:
                    logger.info("[calc_operands] generic operand fallback rows=%s", len(generic_fallback_rows))
                    operand_rows = _merge_operand_rows(
                        operand_rows,
                        generic_fallback_rows,
                        required_operands=required_operands,
                    )
            missing_required = _missing_required_operands(required_operands, operand_rows) if required_operands else []
            if missing_required and not direct_numeric_grounding and _is_ratio_percent_query(query):
                fallback_rows = self._build_ratio_operands_from_candidates(
                    [item for item in evidence_items if item.get("raw_row_text")],
                    query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
                if fallback_rows:
                    logger.info("[calc_operands] python ratio fallback operands=%s", len(fallback_rows))
                    operand_rows = _merge_operand_rows(
                        operand_rows,
                        fallback_rows,
                        required_operands=required_operands,
                    )
            if operation_family == "ratio" and required_operands and operand_rows:
                sibling_context_rows = self._build_required_operands_from_candidates(
                    evidence_items,
                    required_operands=required_operands,
                    query=query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
                if sibling_context_rows:
                    operand_rows = self._align_dependency_rows_with_sibling_direct_context(
                        operand_rows,
                        sibling_context_rows,
                    )
            if _is_percent_point_difference_query(query):
                operand_rows = [
                    row for row in operand_rows
                    if str(row.get("normalized_unit") or "") == "PERCENT" and row.get("normalized_value") is not None
                ]
                logger.info("[calc_operands] percent-diff operand filtering retained=%s", len(operand_rows))
            merged_coverage = extracted.coverage
            if direct_structured_rows and operand_rows and required_operands:
                merged_coverage = (
                    "sufficient"
                    if not _missing_required_operands(required_operands, operand_rows)
                    else "partial"
                )
            logger.info("[calc_operands] coverage=%s operands=%s", merged_coverage, len(operand_rows))
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str(active_subtask.get("task_id") or "calc")
            artifacts = self._enrich_reconciliation_artifact_refs(
                artifacts,
                task_id=task_id,
                operand_rows=operand_rows,
            )
            artifact_id = f"operands:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.OPERAND_SET,
                status=str(merged_coverage),
                summary=f"{len(operand_rows)} operand(s) from llm/fallback extraction",
                payload={"calculation_operands": operand_rows, "coverage": merged_coverage},
                evidence_refs=[str(row.get("evidence_id") or "") for row in operand_rows if str(row.get("evidence_id") or "").strip()],
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str(active_subtask.get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
            return {
                "calculation_debug_trace": {
                    "coverage": merged_coverage,
                    "direct_structured_rows": direct_structured_rows,
                    "operands": operand_rows,
                },
                "evidence_items": evidence_items,
                "evidence_bullets": evidence_bullets,
                "evidence_status": str(merged_coverage),
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operand_rows,
                    calculation_plan={},
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }
        except Exception as exc:
            logger.warning("[calc_operands] structured output failed: %s", exc)
            return {
                "calculation_debug_trace": {"coverage": "missing", "error": str(exc)},
                "evidence_items": evidence_items,
                "evidence_bullets": evidence_bullets,
                "evidence_status": "missing",
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=[],
                    calculation_plan={},
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }

    def _operation_plan_guard(
        self,
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
            missing_required = _missing_required_operands(required_operands, selected_rows)
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
                        if _operand_row_matches_requirement(row, requirement):
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

    def _plan_formula_calculation(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Translate normalized operands into an executable calculation plan."""
        runtime_trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        operands = list(runtime_trace.get("calculation_operands") or [])
        query = self._calc_query(state)
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        if not operands:
            empty_plan = {
                "status": "incomplete",
                "mode": "none",
                "operation": "none",
                "ordered_operand_ids": [],
                "variable_bindings": [],
                "formula": "",
                "pairwise_formula": "",
                "result_unit": "",
                "operation_text": "",
                "explanation": "no operands",
                "missing_info": self._infer_missing_info(state, []),
            }
            missing_info = self._infer_missing_info(state, [])
            return {
                "missing_info": missing_info,
                "planner_debug_trace": {
                    "llm_invoked": False,
                    "guard_applied": False,
                    "reason": "no operands",
                    "missing_info": missing_info,
                },
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=empty_plan,
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }

        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if isinstance(item, dict) and bool(item.get("required", True))
        ]
        if required_operands and operation_family in {"ratio", "difference", "growth_rate", "sum"}:
            missing_required = _missing_required_operands(required_operands, operands)
            if missing_required:
                missing_labels = [
                    _normalise_spaces(str(item.get("label") or item.get("role") or item.get("concept") or "operand"))
                    for item in missing_required
                ]
                incomplete_plan = {
                    "status": "incomplete",
                    "mode": "none",
                    "operation": "none",
                    "ordered_operand_ids": [],
                    "variable_bindings": [],
                    "formula": "",
                    "pairwise_formula": "",
                    "result_unit": "",
                    "operation_text": "",
                    "explanation": "missing required operands",
                    "missing_info": missing_labels,
                }
                return {
                    "missing_info": missing_labels,
                    "planner_debug_trace": {
                        "llm_invoked": False,
                        "guard_applied": True,
                        "reason": "missing_required_operands",
                        "missing_info": missing_labels,
                    },
                    **_runtime_trace_state_update(
                        state,
                        calculation_operands=operands,
                        calculation_plan=incomplete_plan,
                        calculation_result={},
                        include_compatibility_mirrors=False,
                    ),
                }

        query_text = _normalise_spaces(query)
        ontology = get_financial_ontology()
        metric_key = self._calc_metric_family(state)
        metric_info = ontology.metric_family(metric_key) if metric_key else None
        deterministic_lookup_plan = self._build_deterministic_lookup_plan(state, operands)
        if deterministic_lookup_plan:
            logger.info(
                "[formula_plan] deterministic lookup mode=%s op=%s vars=%s",
                deterministic_lookup_plan.get("mode"),
                deterministic_lookup_plan.get("operation"),
                len(deterministic_lookup_plan.get("variable_bindings") or []),
            )
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str(active_subtask.get("task_id") or "calc")
            artifact_id = f"plan:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.CALCULATION_PLAN,
                status=str(deterministic_lookup_plan.get("status") or "ok"),
                summary=f"mode={deterministic_lookup_plan.get('mode')} op={deterministic_lookup_plan.get('operation')}",
                payload={"calculation_plan": deterministic_lookup_plan},
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str(active_subtask.get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
            return {
                "missing_info": [str(item).strip() for item in (deterministic_lookup_plan.get("missing_info") or []) if str(item).strip()],
                "planner_debug_trace": {
                    "active_metric_family": metric_key,
                    "ontology_context": "deterministic_lookup_plan",
                    "operands_text": "\n".join(
                        f"- operand_id={row.get('operand_id')} | label={row.get('label')} | raw={row.get('raw_value')} {row.get('raw_unit')}"
                        for row in operands
                    ),
                    "llm_invoked": False,
                    "guard_applied": True,
                    "raw_plan": deterministic_lookup_plan,
                },
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=deterministic_lookup_plan,
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }

        deterministic_operation_plan = self._build_deterministic_operation_plan(state, operands)
        if deterministic_operation_plan:
            guarded_plan = self._operation_plan_guard(
                plan=deterministic_operation_plan,
                operands=operands,
                required_operands=required_operands,
                operation_family=operation_family,
            )
            if guarded_plan:
                return {
                    "missing_info": list(guarded_plan.get("missing_info") or []),
                    "planner_debug_trace": {
                        "active_metric_family": metric_key,
                        "ontology_context": "deterministic_operation_plan_guard",
                        "llm_invoked": False,
                        "guard_applied": True,
                        "reason": "invalid_required_operand_bindings",
                        "raw_plan": deterministic_operation_plan,
                        "missing_info": list(guarded_plan.get("missing_info") or []),
                    },
                    **_runtime_trace_state_update(
                        state,
                        calculation_operands=operands,
                        calculation_plan=guarded_plan,
                        calculation_result={},
                        include_compatibility_mirrors=False,
                    ),
                }
            logger.info(
                "[formula_plan] deterministic op-family mode=%s op=%s vars=%s",
                deterministic_operation_plan.get("mode"),
                deterministic_operation_plan.get("operation"),
                len(deterministic_operation_plan.get("variable_bindings") or []),
            )
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str((state.get("active_subtask") or {}).get("task_id") or "calc")
            artifact_id = f"plan:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.CALCULATION_PLAN,
                status=str(deterministic_operation_plan.get("status") or "ok"),
                summary=f"mode={deterministic_operation_plan.get('mode')} op={deterministic_operation_plan.get('operation')}",
                payload={"calculation_plan": deterministic_operation_plan},
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str((state.get("active_subtask") or {}).get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
            return {
                "missing_info": [],
                "planner_debug_trace": {
                    "active_metric_family": metric_key,
                    "ontology_context": "deterministic_operation_plan",
                    "operands_text": "\n".join(
                        f"- operand_id={row.get('operand_id')} | label={row.get('label')} | raw={row.get('raw_value')} {row.get('raw_unit')}"
                        for row in operands
                    ),
                    "llm_invoked": False,
                    "guard_applied": True,
                    "raw_plan": deterministic_operation_plan,
                },
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=deterministic_operation_plan,
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }

        if operation_family in {"lookup", "single_value"}:
            missing_info = self._infer_missing_info(state, operands)
            guard_plan = {
                "status": "incomplete",
                "mode": "none",
                "operation": "none",
                "ordered_operand_ids": [],
                "variable_bindings": [],
                "formula": "",
                "pairwise_formula": "",
                "result_unit": "",
                "operation_text": "",
                "explanation": "lookup tasks require a single directly grounded operand row.",
                "missing_info": missing_info,
            }
            return {
                "missing_info": missing_info,
                "planner_debug_trace": {
                    "active_metric_family": metric_key,
                    "ontology_context": "lookup_guard_reject_non_direct",
                    "operands_text": "\n".join(
                        f"- operand_id={row.get('operand_id')} | label={row.get('label')} | raw={row.get('raw_value')} {row.get('raw_unit')}"
                        for row in operands
                    ),
                    "llm_invoked": False,
                    "guard_applied": True,
                    "reason": "lookup_non_direct_or_ambiguous",
                    "missing_info": missing_info,
                },
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=guard_plan,
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }

        deterministic_plan = self._build_deterministic_ontology_plan(state, operands)
        if deterministic_plan:
            guarded_plan = self._operation_plan_guard(
                plan=deterministic_plan,
                operands=operands,
                required_operands=required_operands,
                operation_family=operation_family,
            )
            if guarded_plan:
                return {
                    "missing_info": list(guarded_plan.get("missing_info") or []),
                    "planner_debug_trace": {
                        "active_metric_family": metric_key,
                        "ontology_context": "deterministic_ontology_plan_guard",
                        "llm_invoked": False,
                        "guard_applied": True,
                        "reason": "invalid_required_operand_bindings",
                        "raw_plan": deterministic_plan,
                        "missing_info": list(guarded_plan.get("missing_info") or []),
                    },
                    **_runtime_trace_state_update(
                        state,
                        calculation_operands=operands,
                        calculation_plan=guarded_plan,
                        calculation_result={},
                        include_compatibility_mirrors=False,
                    ),
                }
            logger.info(
                "[formula_plan] deterministic mode=%s op=%s vars=%s",
                deterministic_plan.get("mode"),
                deterministic_plan.get("operation"),
                len(deterministic_plan.get("variable_bindings") or []),
            )
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str((state.get("active_subtask") or {}).get("task_id") or "calc")
            artifact_id = f"plan:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.CALCULATION_PLAN,
                status=str(deterministic_plan.get("status") or "ok"),
                summary=f"mode={deterministic_plan.get('mode')} op={deterministic_plan.get('operation')}",
                payload={"calculation_plan": deterministic_plan},
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str((state.get("active_subtask") or {}).get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
            return {
                "missing_info": [],
                "planner_debug_trace": {
                    "active_metric_family": metric_key,
                    "ontology_context": "deterministic_ontology_plan",
                    "operands_text": "\n".join(
                        f"- operand_id={row.get('operand_id')} | label={row.get('label')} | raw={row.get('raw_value')} {row.get('raw_unit')}"
                        for row in operands
                    ),
                    "llm_invoked": False,
                    "guard_applied": False,
                    "raw_plan": deterministic_plan,
                },
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=deterministic_plan,
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }
        structured_llm = self._llm_for_phase("formula_planning").with_structured_output(CalculationPlan)
        ontology_context = ""
        if metric_info:
            components = dict(metric_info.get("components") or {})
            component_lines: List[str] = []
            for role, component in components.items():
                name = str(component.get("name") or "").strip()
                keywords = ", ".join(
                    str(keyword).strip()
                    for keyword in component.get("keywords", [])
                    if str(keyword).strip()
                )
                preferred_sections = ", ".join(
                    str(section).strip()
                    for section in component.get("preferred_sections", [])
                    if str(section).strip()
                )
                bits = [f"{role}={name or '-'}"]
                if keywords:
                    bits.append(f"keywords={keywords}")
                if preferred_sections:
                    bits.append(f"preferred_sections={preferred_sections}")
                component_lines.append(" | ".join(bits))
            preferred_sections = ", ".join(
                str(section).strip()
                for section in metric_info.get("preferred_sections", [])
                if str(section).strip()
            )
            ontology_lines = [
                f"- key={metric_info.get('key', '')}",
                f"- display_name={metric_info.get('display_name', '')}",
                f"- formula_template={metric_info.get('formula_template', '')}",
                f"- result_unit={metric_info.get('result_unit', '')}",
            ]
            if preferred_sections:
                ontology_lines.append(f"- preferred_sections={preferred_sections}")
            if component_lines:
                ontology_lines.append("- components:")
                ontology_lines.extend(f"  - {line}" for line in component_lines)
            ontology_context = "\n".join(ontology_lines)
        operands_text = "\n".join(
            f"- operand_id={row.get('operand_id')} | evidence_id={row.get('evidence_id')} | label={row.get('label')} | raw={row.get('raw_value')} {row.get('raw_unit')} | normalized={row.get('normalized_value')} {row.get('normalized_unit')} | period={row.get('period', '')}"
            for row in operands
        )
        planner_trace_base = {
            "active_metric_family": metric_key,
            "ontology_context": ontology_context or "-",
            "operands_text": operands_text,
        }
        prompt = ChatPromptTemplate.from_template(
            str(CALCULATION_PROMPT_POLICY.get("formula_plan_prompt_template") or "")
        )
        try:
            plan: CalculationPlan = (prompt | structured_llm).invoke(
                {
                    "query": query,
                    "operands": operands_text,
                    "ontology_context": ontology_context or "-",
                }
            )
            plan_data = plan.model_dump()
            plan_data.setdefault("status", "ok")
            bindings = plan_data.get("variable_bindings") or []
            if not plan_data.get("ordered_operand_ids") and bindings:
                plan_data["ordered_operand_ids"] = [str(binding.get("operand_id") or "") for binding in bindings if str(binding.get("operand_id") or "").strip()]
            if not bindings and plan_data.get("ordered_operand_ids"):
                plan_data["variable_bindings"] = [
                    {"variable": chr(ord("A") + index), "operand_id": operand_id}
                    for index, operand_id in enumerate(plan_data.get("ordered_operand_ids") or [])
                ]
            if (
                str(plan_data.get("mode") or "").lower() == "none"
                and not (plan_data.get("variable_bindings") or [])
            ):
                plan_data["status"] = "incomplete"
                if not plan_data.get("missing_info"):
                    plan_data["missing_info"] = self._infer_missing_info(state, operands)
            if _should_coerce_percent_point_unit(query_text, operands, plan_data):
                plan_data["result_unit"] = "%p"
            guarded_plan = self._operation_plan_guard(
                plan=plan_data,
                operands=operands,
                required_operands=required_operands,
                operation_family=operation_family,
            )
            guard_applied = False
            raw_plan_data = dict(plan_data)
            if guarded_plan:
                plan_data = guarded_plan
                guard_applied = True
            logger.info("[formula_plan] mode=%s op=%s vars=%s", plan_data.get("mode"), plan_data.get("operation"), len(plan_data.get("variable_bindings") or []))
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str((state.get("active_subtask") or {}).get("task_id") or "calc")
            artifact_id = f"plan:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.CALCULATION_PLAN,
                status=str(plan_data.get("status") or "ok"),
                summary=f"mode={plan_data.get('mode')} op={plan_data.get('operation')}",
                payload={"calculation_plan": plan_data},
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str((state.get("active_subtask") or {}).get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
            return {
                "missing_info": [str(item).strip() for item in (plan_data.get("missing_info") or []) if str(item).strip()],
                "planner_debug_trace": {
                    **planner_trace_base,
                    "llm_invoked": True,
                    "guard_applied": guard_applied,
                    "reason": "invalid_required_operand_bindings" if guard_applied else "",
                    "raw_plan": raw_plan_data if guard_applied else plan_data,
                    "guarded_plan": plan_data if guard_applied else {},
                },
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=plan_data,
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }
        except Exception as exc:
            logger.warning("[formula_plan] structured output failed: %s", exc)
            failed_plan = {
                "status": "incomplete",
                "mode": "none",
                "operation": "none",
                "ordered_operand_ids": [],
                "variable_bindings": [],
                "formula": "",
                "pairwise_formula": "",
                "result_unit": "",
                "operation_text": "",
                "explanation": str(exc),
                "missing_info": self._infer_missing_info(state, operands),
            }
            return {
                "missing_info": self._infer_missing_info(state, operands),
                "planner_debug_trace": {
                    **planner_trace_base,
                    "llm_invoked": True,
                    "guard_applied": False,
                    "error": str(exc),
                },
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=failed_plan,
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }

    def _format_calculation_value(self, value: float, result_unit: str, normalized_unit: str) -> str:
        if normalized_unit == "KRW":
            # normalized_value is always in full KRW — always render as 조/억원 regardless of result_unit hint
            return _format_korean_won_compact(value)
        if (normalized_unit or "").upper() in {"PERCENT", "%", "퍼센트"}:
            if str(result_unit or "").strip() == "%p":
                return f"{value:.2f}"
            if value and abs(value) < 0.01:
                return f"{value:.4f}".rstrip("0").rstrip(".")
            return f"{value:.2f}".rstrip("0").rstrip(".")
        if normalized_unit in {"COUNT", "USD"}:
            return f"{value:,.4f}".rstrip("0").rstrip(".")
        return f"{value}"

    def _format_calculation_value_in_display_unit(self, value: float, display_unit: str) -> str:
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

    def _adjusted_difference_source_display_unit(
        self,
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

    def _render_value_with_unit(self, value: float, display_unit: str, normalized_unit: str) -> str:
        rendered = self._format_calculation_value(value, display_unit, normalized_unit)
        if normalized_unit == "KRW":
            return rendered
        if (normalized_unit or "").upper() in {"PERCENT", "%", "퍼센트"}:
            return f"{rendered}{display_unit or '%'}"
        if display_unit:
            return f"{rendered}{display_unit}"
        return rendered

    def _render_grounded_operand_display(self, row: Dict[str, Any]) -> str:
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

    def _absolute_display_value(self, value: str) -> str:
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

    def _collect_negative_subtrahend_slots(
        self,
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
                    positive = self._absolute_display_value(rendered)
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

    def _coerce_sign_aware_subtraction_answer(
        self,
        answer: str,
        *,
        calculation_result: Optional[Dict[str, Any]] = None,
        subtask_results: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        rewritten = str(answer or "")
        for row in self._collect_negative_subtrahend_slots(
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

    def _first_material_slot_for_role(self, answer_slots: Dict[str, Any], role: str) -> Dict[str, Any]:
        components_by_role = dict(answer_slots.get("components_by_role") or {})
        for slot in list(components_by_role.get(role) or []):
            slot_row = dict(slot or {})
            if self._answer_slot_has_material(slot_row):
                return slot_row
        fallback_key = {
            "minuend": "current_value",
            "subtrahend": "prior_value",
        }.get(role, "")
        if fallback_key:
            fallback = dict(answer_slots.get(fallback_key) or {})
            if self._answer_slot_has_material(fallback):
                return fallback
        return {}

    def _infer_company_from_answer_slots(self, answer_slots: Dict[str, Any]) -> str:
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

    def _compose_slot_based_difference_answer(
        self,
        *,
        query: str,
        report_scope: Dict[str, Any],
        calculation_result: Dict[str, Any],
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
                answer = self._compose_slot_based_difference_answer(
                    query=query,
                    report_scope=report_scope,
                    calculation_result=candidate,
                )
                if answer:
                    return answer
            return ""

        minuend = self._first_material_slot_for_role(answer_slots, "minuend")
        subtrahend = self._first_material_slot_for_role(answer_slots, "subtrahend")
        result_slot = dict(answer_slots.get("primary_value") or answer_slots.get("delta_value") or {})
        if not all(self._answer_slot_has_material(slot) for slot in (minuend, subtrahend, result_slot)):
            return ""

        minuend_value = _normalise_spaces(str(minuend.get("rendered_value") or ""))
        subtrahend_value = _normalise_spaces(str(subtrahend.get("rendered_value") or ""))
        result_value = _normalise_spaces(str(result_slot.get("rendered_value") or calculation_result.get("rendered_value") or ""))
        if not (minuend_value and subtrahend_value and result_value):
            return ""

        company = _normalise_spaces(str((report_scope or {}).get("company") or ""))
        if not company:
            company = self._infer_company_from_answer_slots(answer_slots)
        period = _normalise_spaces(
            str(result_slot.get("period") or minuend.get("period") or subtrahend.get("period") or "")
        )
        scope = _desired_consolidation_scope(query, report_scope or {})
        scope_text = dict(CALCULATION_RENDER_POLICY.get("scope_labels") or {}).get(scope, "")
        prefix_parts = [part for part in (company, f"{period}년" if period and not period.endswith("년") else period, scope_text) if part]
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

    def _slot_status(
        self,
        *,
        normalized_value: Optional[float],
        rendered_value: str,
        raw_value: str,
    ) -> str:
        if normalized_value is not None:
            return "ok"
        if str(rendered_value or raw_value or "").strip():
            return "derived"
        return "missing"

    def _coerce_slot_numeric(self, value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _build_missing_value_slot(
        self,
        *,
        role: str,
        label: str,
        concept: str = "",
        period: str = "",
        raw_unit: str = "",
        normalized_unit: str = "UNKNOWN",
        source_row_ids: Optional[List[str]] = None,
        source_anchor: str = "",
    ) -> Dict[str, Any]:
        row_ids = _clean_source_row_ids(source_row_ids or [])
        return {
            "status": "missing",
            "role": role,
            "label": _display_operand_label(label),
            "concept": concept,
            "period": str(period or ""),
            "raw_value": "",
            "raw_unit": str(raw_unit or ""),
            "normalized_value": None,
            "normalized_unit": str(normalized_unit or "UNKNOWN"),
            "rendered_value": "",
            "source_row_id": row_ids[0] if row_ids else "",
            "source_row_ids": row_ids,
            "source_anchor": str(source_anchor or ""),
        }

    def _build_operand_value_slot(
        self,
        row: Dict[str, Any],
        *,
        default_role: str = "operand",
        preserve_source_display: bool = False,
    ) -> Dict[str, Any]:
        raw_unit = str(row.get("raw_unit") or row.get("result_unit") or "")
        normalized_unit = str(row.get("normalized_unit") or "")
        normalized_value = row.get("normalized_value")
        rendered_value = self._render_grounded_operand_display(row) if preserve_source_display else ""
        if normalized_value is not None:
            try:
                if not rendered_value:
                    rendered_value = self._render_value_with_unit(float(normalized_value), raw_unit, normalized_unit)
            except (TypeError, ValueError):
                rendered_value = str(row.get("raw_value") or "")
        source_row_ids = _clean_source_row_ids([
            row.get("evidence_id"),
            row.get("row_id"),
            row.get("source_row_id"),
            row.get("source_row_ids"),
        ])
        return {
            "status": self._slot_status(
                normalized_value=self._coerce_slot_numeric(normalized_value),
                rendered_value=rendered_value,
                raw_value=str(row.get("raw_value") or ""),
            ),
            "role": str(row.get("matched_operand_role") or default_role),
            "label": _display_operand_label(str(row.get("label") or row.get("matched_operand_label") or "")),
            "concept": str(row.get("matched_operand_concept") or ""),
            "period": str(row.get("period") or ""),
            "raw_value": str(row.get("raw_value") or ""),
            "raw_unit": raw_unit,
            "normalized_value": normalized_value,
            "normalized_unit": normalized_unit,
            "rendered_value": rendered_value,
            "source_row_id": source_row_ids[0] if source_row_ids else "",
            "source_row_ids": source_row_ids,
            "source_anchor": str(row.get("source_anchor") or ""),
            "consolidation_scope": str(row.get("consolidation_scope") or ""),
            "stated_change_raw_value": str(row.get("stated_change_raw_value") or ""),
            "stated_change_raw_unit": str(row.get("stated_change_raw_unit") or ""),
        }

    def _build_calculated_value_slot(
        self,
        *,
        label: str,
        normalized_value: Optional[float],
        normalized_unit: str,
        display_unit: str,
        period: str = "",
        source_row_ids: Optional[List[str]] = None,
        role: str = "primary_value",
        source_anchor: str = "",
    ) -> Dict[str, Any]:
        rendered_value = ""
        if normalized_value is not None:
            if str(normalized_unit or "").upper() == "KRW" and display_unit in {"천원", "백만원"}:
                rendered_value = self._format_calculation_value_in_display_unit(float(normalized_value), display_unit)
            else:
                rendered_value = self._render_value_with_unit(float(normalized_value), display_unit, normalized_unit)
        row_ids = _clean_source_row_ids(source_row_ids or [])
        return {
            "status": self._slot_status(
                normalized_value=self._coerce_slot_numeric(normalized_value),
                rendered_value=rendered_value,
                raw_value="",
            ),
            "role": role,
            "label": _display_operand_label(label),
            "concept": "",
            "period": str(period or ""),
            "raw_value": "",
            "raw_unit": str(display_unit or ""),
            "normalized_value": normalized_value,
            "normalized_unit": normalized_unit,
            "rendered_value": rendered_value,
            "source_row_id": row_ids[0] if row_ids else "",
            "source_row_ids": row_ids,
            "source_anchor": str(source_anchor or ""),
        }

    def _build_answer_slots(
        self,
        *,
        active_subtask: Dict[str, Any],
        operation_family: str,
        ordered_operands: List[Dict[str, Any]],
        result_value: Optional[float],
        result_unit: str,
        normalized_unit: str,
        source_normalized_unit: str,
        current_value: Optional[float],
        prior_value: Optional[float],
        delta_value: Optional[float],
        current_period: str,
        prior_period: str,
        source_row_ids: List[str],
        current_row: Optional[Dict[str, Any]] = None,
        prior_row: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        family = str(
            operation_family or active_subtask.get("operation_family") or "single_value"
        ).strip().lower()
        metric_label = str(
            active_subtask.get("metric_label")
            or active_subtask.get("query")
            or active_subtask.get("task_id")
            or ""
        )
        required_operands = [dict(item) for item in (active_subtask.get("required_operands") or [])]

        def _seed_for_roles(*roles: str) -> Dict[str, Any]:
            role_set = {str(role).strip().lower() for role in roles if str(role).strip()}
            for requirement in required_operands:
                req_role = str(requirement.get("role") or "").strip().lower()
                if req_role and req_role in role_set:
                    return requirement
            for row in ordered_operands:
                row_role = str(row.get("matched_operand_role") or "").strip().lower()
                if row_role and row_role in role_set:
                    return row
            return {}

        components_by_role: Dict[str, List[Dict[str, Any]]] = {}
        components_by_group: Dict[str, List[Dict[str, Any]]] = {}
        preserve_difference_source_display = bool(
            family == "difference"
            and self._adjusted_difference_source_display_unit(
                active_subtask=active_subtask,
                ordered_operands=ordered_operands,
            )
        )
        for row in ordered_operands:
            row_normalized_unit = str(row.get("normalized_unit") or "").strip().upper()
            preserve_ratio_source_display = family == "ratio"
            preserve_growth_source_display = family == "growth_rate" and row_normalized_unit not in {"", "KRW"}
            slot = self._build_operand_value_slot(
                row,
                preserve_source_display=(
                    family in {"lookup", "single_value"}
                    or preserve_ratio_source_display
                    or preserve_difference_source_display
                    or preserve_growth_source_display
                ),
            )
            role = str(slot.get("role") or "operand")
            components_by_role.setdefault(role, []).append(slot)
            role_group = role.split("_", 1)[0] if "_" in role else role
            components_by_group.setdefault(role_group, []).append(slot)

        answer_slots: Dict[str, Any] = {
            "operation_family": family,
            "metric_label": metric_label,
            "components_by_role": components_by_role,
            "components_by_group": components_by_group,
            "source_row_ids": list(source_row_ids or []),
        }

        if family in {"lookup", "single_value"}:
            if ordered_operands:
                primary_slot = self._build_operand_value_slot(
                    ordered_operands[0],
                    default_role="primary_value",
                    preserve_source_display=True,
                )
                primary_slot["role"] = "primary_value"
                answer_slots["primary_value"] = primary_slot
            else:
                seed = _seed_for_roles("operand", "current_period", "primary_value")
                answer_slots["primary_value"] = self._build_missing_value_slot(
                    role="primary_value",
                    label=str(seed.get("label") or metric_label),
                    concept=str(seed.get("concept") or seed.get("matched_operand_concept") or ""),
                    period=str(seed.get("period") or seed.get("period_hint") or current_period or ""),
                    raw_unit=str(seed.get("raw_unit") or result_unit or ""),
                    normalized_unit=str(seed.get("normalized_unit") or source_normalized_unit or "UNKNOWN"),
                    source_anchor=str(seed.get("source_anchor") or ""),
                )
            return validate_answer_slots_payload(answer_slots)

        operand_roles = {
            str(spec.get("role") or "").strip()
            for spec in required_operands
            if str(spec.get("role") or "").strip()
        }
        row_roles = {
            str(row.get("matched_operand_role") or "").strip()
            for row in ordered_operands
            if str(row.get("matched_operand_role") or "").strip()
        }
        period_difference = family in {"difference", "growth_rate"} and bool(
            {"current_period", "prior_period"} & (operand_roles | row_roles)
        )

        primary_role = "delta_value" if family == "difference" and period_difference else "primary_value"
        answer_slots["primary_value"] = self._build_calculated_value_slot(
            label=metric_label,
            normalized_value=result_value,
            normalized_unit=normalized_unit,
            display_unit=result_unit,
            period=current_period,
            source_row_ids=source_row_ids,
            role=primary_role,
        )

        if family in {"difference", "growth_rate"}:
            current_seed = current_row or _seed_for_roles("current_period")
            if current_row:
                current_preserve_display = str(current_row.get("normalized_unit") or "").strip().upper() != "KRW"
                current_slot = self._build_operand_value_slot(
                    current_row,
                    default_role="current_value",
                    preserve_source_display=current_preserve_display,
                )
                current_slot["role"] = "current_value"
                answer_slots["current_value"] = current_slot
            elif current_value is not None:
                answer_slots["current_value"] = self._build_calculated_value_slot(
                    label=str(current_seed.get("label") or metric_label),
                    normalized_value=current_value,
                    normalized_unit=source_normalized_unit or normalized_unit,
                    display_unit="",
                    period=current_period,
                    source_row_ids=source_row_ids[:1],
                    role="current_value",
                    source_anchor=str(current_seed.get("source_anchor") or ""),
                )
            else:
                answer_slots["current_value"] = self._build_missing_value_slot(
                    role="current_value",
                    label=str(current_seed.get("label") or metric_label),
                    concept=str(current_seed.get("concept") or current_seed.get("matched_operand_concept") or ""),
                    period=str(current_seed.get("period") or current_seed.get("period_hint") or current_period or ""),
                    raw_unit=str(current_seed.get("raw_unit") or result_unit or ""),
                    normalized_unit=str(current_seed.get("normalized_unit") or source_normalized_unit or normalized_unit or "UNKNOWN"),
                    source_anchor=str(current_seed.get("source_anchor") or ""),
                )

            prior_seed = prior_row or _seed_for_roles("prior_period")
            if prior_row:
                prior_preserve_display = str(prior_row.get("normalized_unit") or "").strip().upper() != "KRW"
                prior_slot = self._build_operand_value_slot(
                    prior_row,
                    default_role="prior_value",
                    preserve_source_display=prior_preserve_display,
                )
                prior_slot["role"] = "prior_value"
                answer_slots["prior_value"] = prior_slot
            elif prior_value is not None:
                answer_slots["prior_value"] = self._build_calculated_value_slot(
                    label=str(prior_seed.get("label") or metric_label),
                    normalized_value=prior_value,
                    normalized_unit=source_normalized_unit or normalized_unit,
                    display_unit="",
                    period=prior_period,
                    source_row_ids=source_row_ids[1:2],
                    role="prior_value",
                    source_anchor=str(prior_seed.get("source_anchor") or ""),
                )
            else:
                answer_slots["prior_value"] = self._build_missing_value_slot(
                    role="prior_value",
                    label=str(prior_seed.get("label") or metric_label),
                    concept=str(prior_seed.get("concept") or prior_seed.get("matched_operand_concept") or ""),
                    period=str(prior_seed.get("period") or prior_seed.get("period_hint") or prior_period or ""),
                    raw_unit=str(prior_seed.get("raw_unit") or result_unit or ""),
                    normalized_unit=str(prior_seed.get("normalized_unit") or source_normalized_unit or normalized_unit or "UNKNOWN"),
                    source_anchor=str(prior_seed.get("source_anchor") or ""),
                )

            if family == "difference":
                answer_slots["delta_value"] = self._build_calculated_value_slot(
                    label=metric_label,
                    normalized_value=delta_value,
                    normalized_unit=normalized_unit,
                    display_unit=result_unit,
                    period=current_period,
                    source_row_ids=source_row_ids,
                    role="delta_value",
                )
                if current_value is not None and prior_value is not None:
                    if delta_value > 0:
                        direction = "increase"
                    elif delta_value < 0:
                        direction = "decrease"
                    else:
                        direction = "flat"
                    answer_slots["direction"] = direction
                else:
                    answer_slots["direction"] = None

        return validate_answer_slots_payload(answer_slots)

    def _binding_policy_for_operand_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row_policy = dict(row.get("binding_policy") or {})
        concept_key = str(row.get("matched_operand_concept") or row.get("concept") or "").strip()
        if not concept_key:
            return row_policy
        ontology_policy = get_financial_ontology().binding_policy_for_concept(concept_key)
        merged = dict(ontology_policy or {})
        merged.update(row_policy)
        return merged

    def _apply_operation_sign_policy(
        self,
        operands: List[Dict[str, Any]],
        *,
        operation: str,
        operation_family: str,
    ) -> List[Dict[str, Any]]:
        if _normalise_spaces(operation) != "ratio" and _normalise_spaces(operation_family) != "ratio":
            return operands
        updated: List[Dict[str, Any]] = []
        changed = False
        for row in operands:
            next_row = dict(row)
            role = _normalise_spaces(str(next_row.get("matched_operand_role") or next_row.get("role") or ""))
            if not role.startswith("denominator"):
                updated.append(next_row)
                continue
            policy = self._binding_policy_for_operand_row(next_row)
            denominator_sign = _normalise_spaces(str(policy.get("ratio_denominator_sign") or ""))
            if denominator_sign != "magnitude":
                updated.append(next_row)
                continue
            value = next_row.get("normalized_value")
            if value is None:
                updated.append(next_row)
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                updated.append(next_row)
                continue
            if numeric_value < 0:
                next_row["normalized_value"] = abs(numeric_value)
                next_row["sign_policy_applied"] = "ratio_denominator_magnitude"
                next_row["source_normalized_value"] = numeric_value
                next_row["binding_policy"] = policy
                changed = True
            updated.append(next_row)
        return updated if changed else operands

    def _execute_calculation(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Execute the planned numeric operation and normalize the result."""
        runtime_trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        runtime_operands = [dict(row) for row in (runtime_trace.get("calculation_operands") or [])]
        operands = {row.get("operand_id"): row for row in runtime_operands}
        plan = dict(runtime_trace.get("calculation_plan") or {})
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        operation = str(plan.get("operation") or "none")
        mode = str(plan.get("mode") or "none")
        ordered_ids = [operand_id for operand_id in (plan.get("ordered_operand_ids") or []) if operand_id in operands]
        variable_bindings = [
            binding for binding in (plan.get("variable_bindings") or [])
            if str(binding.get("operand_id") or "") in operands and str(binding.get("variable") or "").strip()
        ]
        formula = str(plan.get("formula") or "").strip()
        pairwise_formula = str(plan.get("pairwise_formula") or "").strip()
        result_unit = str(plan.get("result_unit") or "")
        explanation = str(plan.get("explanation") or "")
        selected_evidence_ids: List[str] = []
        source_normalized_unit = ""

        def _fail(status: str, reason: str, calculation_plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            fallback = "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다."
            failure_slots = self._build_answer_slots(
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
                "answer": fallback,
                "compressed_answer": fallback,
                "selected_claim_ids": selected_evidence_ids,
                "draft_points": [],
                "kept_claim_ids": selected_evidence_ids,
                "dropped_claim_ids": [],
                "unsupported_sentences": [],
                "sentence_checks": [],
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=runtime_operands,
                    calculation_plan=calculation_plan if calculation_plan is not None else plan,
                    calculation_result={
                        "status": status,
                        "result_value": None,
                        "result_unit": result_unit,
                        "rendered_value": "",
                        "formatted_result": "",
                        "series": [],
                        "answer_slots": failure_slots,
                        "derived_metrics": {},
                        "explanation": reason,
                    },
                    include_compatibility_mirrors=False,
                ),
            }

        if mode == "none" or not variable_bindings:
            return _fail("insufficient_operands", explanation or "no operation or operands")

        if not ordered_ids:
            ordered_ids = [str(binding.get("operand_id") or "") for binding in variable_bindings]

        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if isinstance(item, dict) and bool(item.get("required", True))
        ]
        guarded_plan = self._operation_plan_guard(
            plan={
                **plan,
                "ordered_operand_ids": ordered_ids,
                "variable_bindings": variable_bindings,
            },
            operands=runtime_operands,
            required_operands=required_operands,
            operation_family=operation_family,
        )
        if guarded_plan:
            return _fail(
                "insufficient_operands",
                "operation plan does not satisfy required operand bindings",
                calculation_plan=guarded_plan,
            )

        ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        if operation_family == "ratio":
            aligned_ratio_operands = self._align_ratio_operands_with_sibling_table_context(
                ordered_operands,
                list(state.get("evidence_items") or []) + list(state.get("runtime_evidence") or []),
            )
            if aligned_ratio_operands != ordered_operands:
                for aligned_row in aligned_ratio_operands:
                    aligned_id = str(aligned_row.get("operand_id") or "").strip()
                    if aligned_id:
                        operands[aligned_id] = aligned_row
                runtime_operands = [
                    dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                    for row in runtime_operands
                ]
                ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        if operation_family in {"difference", "growth_rate"} and len(ordered_operands) == 2:
            concept_keys = {
                str(row.get("matched_operand_concept") or "").strip()
                for row in ordered_operands
                if str(row.get("matched_operand_concept") or "").strip()
            }
            if len(concept_keys) <= 1:
                known_rows = [
                    row
                    for row in ordered_operands
                    if str(row.get("normalized_unit") or "").strip().upper() not in {"", "UNKNOWN"}
                ]
                unknown_rows = [
                    row
                    for row in ordered_operands
                    if str(row.get("normalized_unit") or "").strip().upper() in {"", "UNKNOWN"}
                ]
                if len(known_rows) == 1 and len(unknown_rows) == 1:
                    donor = known_rows[0]
                    target = dict(unknown_rows[0])
                    donor_display_unit = str(donor.get("raw_unit") or donor.get("result_unit") or "").strip()
                    if donor_display_unit:
                        target["raw_unit"] = donor_display_unit
                    normalized_value, normalized_unit = _normalise_operand_value(
                        str(target.get("raw_value") or ""),
                        str(target.get("raw_unit") or ""),
                    )
                    if normalized_value is not None and str(normalized_unit or "").strip().upper() not in {"", "UNKNOWN"}:
                        target["normalized_value"] = normalized_value
                        target["normalized_unit"] = normalized_unit
                        target_id = str(target.get("operand_id") or "").strip()
                        if target_id:
                            operands[target_id] = target
                        runtime_operands = [
                            dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                            for row in runtime_operands
                        ]
                        ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

                if operation_family == "growth_rate":
                    aligned_operands = self._align_growth_operand_units_when_raw_scale_matches(ordered_operands)
                    if aligned_operands != ordered_operands:
                        for aligned_row in aligned_operands:
                            aligned_id = str(aligned_row.get("operand_id") or "").strip()
                            if aligned_id:
                                operands[aligned_id] = aligned_row
                        runtime_operands = [
                            dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                            for row in runtime_operands
                        ]
                        ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        if operation_family == "growth_rate":
            recovered_operands = self._recover_duplicate_growth_prior_operand(
                ordered_operands,
                list(state.get("evidence_items") or []),
            )
            if recovered_operands != ordered_operands:
                for recovered_row in recovered_operands:
                    recovered_id = str(recovered_row.get("operand_id") or "").strip()
                    if recovered_id:
                        operands[recovered_id] = recovered_row
                runtime_operands = [
                    dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                    for row in runtime_operands
                ]
                ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        sign_normalized_operands = self._apply_operation_sign_policy(
            ordered_operands,
            operation=operation,
            operation_family=operation_family,
        )
        if sign_normalized_operands != ordered_operands:
            for sign_normalized_row in sign_normalized_operands:
                sign_normalized_id = str(sign_normalized_row.get("operand_id") or "").strip()
                if sign_normalized_id:
                    operands[sign_normalized_id] = sign_normalized_row
            runtime_operands = [
                dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                for row in runtime_operands
            ]
            ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        coerced_lookup_operands: List[Dict[str, Any]] = []
        lookup_magnitude_changed = False
        for row in ordered_operands:
            coerced_row = _coerce_lookup_magnitude_record(dict(row), None)
            coerced_lookup_operands.append(coerced_row)
            if coerced_row != row:
                lookup_magnitude_changed = True
        if lookup_magnitude_changed:
            for coerced_row in coerced_lookup_operands:
                coerced_id = str(coerced_row.get("operand_id") or "").strip()
                if coerced_id:
                    operands[coerced_id] = coerced_row
            runtime_operands = [
                dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                for row in runtime_operands
            ]
            ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        selected_evidence_ids = list(
            dict.fromkeys(str(row.get("evidence_id")) for row in ordered_operands if row.get("evidence_id"))
        )
        units = {row.get("normalized_unit") for row in ordered_operands}
        if len(units) != 1:
            return _fail("unit_mismatch", f"unit families differ: {sorted(str(unit) for unit in units)}")
        normalized_unit = str(next(iter(units)))
        source_normalized_unit = normalized_unit
        values = [row.get("normalized_value") for row in ordered_operands]
        if any(value is None for value in values):
            return _fail("parse_error", "one or more operands could not be normalized")

        try:
            result_value: Optional[float]
            derived_metrics: Dict[str, Any] = {}
            result_series: List[Dict[str, Any]] = []
            env: Dict[str, float] = {}
            for binding in variable_bindings:
                variable = str(binding.get("variable") or "").strip()
                operand_id = str(binding.get("operand_id") or "").strip()
                operand = operands.get(operand_id)
                if not variable or operand is None or operand.get("normalized_value") is None:
                    return _fail("parse_error", f"invalid variable binding: {binding}")
                env[variable] = float(operand.get("normalized_value"))

            if mode == "time_series":
                if len(variable_bindings) < 2:
                    return _fail("insufficient_operands", "time_series needs at least 2 operands")
                ordered_operands = sorted(
                    [operands[str(binding.get("operand_id"))] for binding in variable_bindings],
                    key=lambda row: _extract_period_sort_key(str(row.get("period") or "")),
                )
                selected_evidence_ids = list(
                    dict.fromkeys(str(row.get("evidence_id")) for row in ordered_operands if row.get("evidence_id"))
                )
                labels = [_display_operand_label(str(row.get("label") or row.get("evidence_id") or "")) for row in ordered_operands]
                metric_names = [re.sub(r"^\d{4}년\s*", "", label).strip() for label in labels]
                metric_name = metric_names[0] if metric_names else "지표"
                for row in ordered_operands:
                    point_value = float(row.get("normalized_value"))
                    point_rendered = self._format_calculation_value(point_value, str(row.get("raw_unit") or row.get("result_unit") or ""), normalized_unit)
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
                yoy_growth_rates: List[Optional[float]] = [None]
                if pairwise_formula:
                    for previous_row, current_row in zip(ordered_operands, ordered_operands[1:]):
                        prev_value = float(previous_row.get("normalized_value"))
                        curr_value = float(current_row.get("normalized_value"))
                        try:
                            yoy_growth_rates.append(_safe_eval_formula(pairwise_formula, {"PREV": prev_value, "CURR": curr_value}))
                        except ZeroDivisionError:
                            yoy_growth_rates.append(None)
                if not formula:
                    return _fail("parse_error", "missing trend formula")
                result_value = _safe_eval_formula(formula, env)
                if result_unit == "%":
                    normalized_unit = "PERCENT"
                _is_percent = (normalized_unit or "").upper() in {"PERCENT", "%", "퍼센트"}
                if _is_percent:
                    rendered_value = f"{result_value:.1f}%"
                else:
                    rendered_value = f"{result_value:,.4f}".rstrip("0").rstrip(".")
                logger.info("[calculator] mode=%s op=%s result=%s", mode, operation, rendered_value)
                calc_result = {
                    "status": "ok",
                    "result_value": result_value,
                    "result_unit": result_unit,
                    "rendered_value": rendered_value,
                    "formatted_result": "",
                    "series": result_series,
                    "answer_slots": {
                        "operation_family": operation_family or operation,
                        "metric_label": metric_name,
                        "primary_value": self._build_calculated_value_slot(
                            label=metric_name,
                            normalized_value=result_value,
                            normalized_unit=normalized_unit,
                            display_unit=result_unit,
                            role="primary_value",
                        ),
                    },
                    "derived_metrics": {
                        "metric_name": metric_name,
                        "yoy_growth_rates": yoy_growth_rates,
                        "formula": formula,
                        "pairwise_formula": pairwise_formula,
                    },
                    "explanation": explanation or str(plan.get("operation_text") or operation or mode),
                }
                return {
                    "answer": "",
                    "compressed_answer": "",
                    "selected_claim_ids": selected_evidence_ids,
                    "draft_points": [],
                    "kept_claim_ids": selected_evidence_ids,
                    "dropped_claim_ids": [],
                    "unsupported_sentences": [],
                    "sentence_checks": [],
                    **_runtime_trace_state_update(
                        state,
                        calculation_operands=runtime_operands,
                        calculation_plan=plan,
                        calculation_result=calc_result,
                        include_compatibility_mirrors=False,
                    ),
                }

            if not formula:
                return _fail("parse_error", "missing scalar formula")
            result_value = _safe_eval_formula(formula, env)
            if result_unit == "%":
                normalized_unit = "PERCENT"
            elif operation == "ratio":
                normalized_unit = "COUNT"
        except Exception as exc:
            if isinstance(exc, ZeroDivisionError):
                return _fail("zero_division", str(exc))
            return _fail("parse_error", str(exc))

        formula_result_value = result_value
        source_stated_result_used = False
        result_display_unit = ""
        if operation_family == "difference" and normalized_unit == "KRW":
            result_display_unit = self._adjusted_difference_source_display_unit(
                active_subtask=active_subtask,
                ordered_operands=ordered_operands,
            )
        if result_display_unit:
            rendered_value = self._format_calculation_value_in_display_unit(result_value, result_display_unit)
        else:
            rendered_value = self._format_calculation_value(result_value, result_unit or "", normalized_unit)
        if normalized_unit == "KRW":
            rendered_with_unit = rendered_value
        elif result_unit:
            rendered_with_unit = f"{rendered_value}{result_unit}"
        else:
            rendered_with_unit = rendered_value
        if operation_family in {"lookup", "single_value"} and ordered_operands:
            grounded_display = self._render_grounded_operand_display(ordered_operands[0])
            if grounded_display:
                rendered_value = grounded_display
                rendered_with_unit = grounded_display
        labels = [_display_operand_label(str(row.get("label") or row.get("evidence_id") or "")) for row in ordered_operands]
        result_series = []
        for row in ordered_operands:
            point_value = float(row.get("normalized_value"))
            point_rendered = self._render_grounded_operand_display(row)
            if not point_rendered:
                point_rendered = self._format_calculation_value(
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
        current_value: Optional[float] = None
        prior_value: Optional[float] = None
        delta_value: Optional[float] = None
        current_period = ""
        prior_period = ""
        current_row: Optional[Dict[str, Any]] = None
        prior_row: Optional[Dict[str, Any]] = None
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
                (row for row in ordered_operands if str(row.get("matched_operand_role") or "").strip() == "current_period"),
                None,
            )
            prior_row = next(
                (row for row in ordered_operands if str(row.get("matched_operand_role") or "").strip() == "prior_period"),
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
        answer_slots = self._build_answer_slots(
            active_subtask=active_subtask,
            operation_family=operation_family,
            ordered_operands=ordered_operands,
            result_value=result_value,
            result_unit=result_display_unit or result_unit,
            normalized_unit=normalized_unit,
            source_normalized_unit=source_normalized_unit,
            current_value=current_value,
            prior_value=prior_value,
            delta_value=delta_value,
            current_period=current_period,
            prior_period=prior_period,
            source_row_ids=source_row_ids,
            current_row=current_row,
            prior_row=prior_row,
        )
        logger.info("[calculator] op=%s result=%s", operation, rendered_with_unit)
        calc_result = {
            "status": "ok",
            "result_value": result_value,
            "result_unit": result_display_unit or result_unit,
            "rendered_value": rendered_with_unit,
            "formatted_result": "",
            "series": result_series,
            "current_value": current_value,
            "prior_value": prior_value,
            "delta_value": delta_value,
            "current_period": current_period,
            "prior_period": prior_period,
            "source_row_ids": source_row_ids,
            "answer_slots": answer_slots,
            "derived_metrics": {
                "operand_labels": labels,
                "formula": formula,
                "operation_family": operation_family or operation,
                "formula_result_value": formula_result_value,
                "source_stated_result_used": source_stated_result_used,
            },
            "explanation": explanation or str(plan.get("operation_text") or operation or mode),
        }
        result_payload = {
            "answer": "",
            "compressed_answer": "",
            "selected_claim_ids": selected_evidence_ids,
            "draft_points": [],
            "kept_claim_ids": selected_evidence_ids,
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
        }
        artifacts = list(state.get("artifacts") or [])
        tasks = list(state.get("tasks") or [])
        task_id = str((state.get("active_subtask") or {}).get("task_id") or "calc")
        artifact_id = f"result:{task_id}:{len(artifacts) + 1:03d}"
        artifacts = _append_artifact(
            artifacts,
            artifact_id=artifact_id,
            task_id=task_id,
            kind=ArtifactKind.CALCULATION_RESULT,
            status=str(calc_result.get("status") or "ok"),
            summary=str(calc_result.get("rendered_value") or calc_result.get("formatted_result") or ""),
            payload={"calculation_result": calc_result},
            evidence_refs=selected_evidence_ids,
        )
        tasks = _upsert_task(
            tasks,
            task_id=task_id,
            kind=TaskKind.CALCULATION,
            label=str((state.get("active_subtask") or {}).get("metric_label") or task_id),
            status=TaskStatus.COMPLETED if str(calc_result.get("status") or "") == "ok" else TaskStatus.FAILED,
            query=self._calc_query(state),
            metric_family=self._calc_metric_family(state),
            artifact_id=artifact_id,
        )
        result_payload["tasks"] = tasks
        result_payload["artifacts"] = artifacts
        result_payload.update(
            _runtime_trace_state_update(
                state,
                calculation_operands=runtime_operands,
                calculation_plan=plan,
                calculation_result=calc_result,
                include_compatibility_mirrors=False,
            )
        )
        return result_payload

    def _render_calculation_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        runtime_trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        calculation_result = dict(runtime_trace.get("calculation_result") or {})
        plan = dict(runtime_trace.get("calculation_plan") or {})
        operands = list(runtime_trace.get("calculation_operands") or [])
        if not calculation_result:
            return {"answer": "", "compressed_answer": "", "draft_points": []}

        # direction_hint: Python에서 결정론적으로 계산 — LLM에게 부호 판단 위임하지 않음
        operation = str(plan.get("operation") or "")
        operation_family = _normalise_spaces(
            str(
                (calculation_result.get("answer_slots") or {}).get("operation_family")
                or calculation_result.get("operation_family")
                or operation
            )
        ).lower()
        result_val = float(calculation_result.get("result_value") or 0)
        direction_hints = dict(CALCULATION_RENDER_POLICY.get("direction_hints") or {})
        direction_hint_set = dict(direction_hints.get(operation) or {})
        if direction_hint_set:
            direction_hint = str(
                direction_hint_set.get("positive")
                if result_val > 0
                else direction_hint_set.get("negative")
                if result_val < 0
                else direction_hint_set.get("zero")
                or ""
            )
        else:
            direction_hint = ""

        # direction_hint가 방향을 표현할 때 rendered_value의 부호는 중복 — 제거
        if direction_hint and result_val < 0:
            rv = str(calculation_result.get("rendered_value") or "")
            calculation_result["rendered_value"] = rv.lstrip("-")

        if str(calculation_result.get("status") or "") != "ok":
            fallback = str(CALCULATION_RENDER_POLICY.get("insufficient_evidence_fallback") or "")
            return {
                "answer": fallback,
                "compressed_answer": fallback,
                "draft_points": [fallback],
            }

        slot_based_difference_answer = self._compose_slot_based_difference_answer(
            query=self._calc_query(state),
            report_scope=dict(state.get("report_scope") or {}),
            calculation_result=calculation_result,
        )
        if slot_based_difference_answer:
            calculation_result["formatted_result"] = slot_based_difference_answer
            return {
                "answer": slot_based_difference_answer,
                "compressed_answer": slot_based_difference_answer,
                "draft_points": [slot_based_difference_answer],
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=plan,
                    calculation_result=calculation_result,
                    include_compatibility_mirrors=False,
                ),
            }

        structured_llm = self._llm_for_phase("calculation_render").with_structured_output(CalculationRenderOutput)
        prompt = ChatPromptTemplate.from_template(
            str(CALCULATION_RENDER_POLICY.get("renderer_prompt_template") or "")
        )
        try:
            rendered: CalculationRenderOutput = (prompt | structured_llm).invoke(
                {
                    "query": self._calc_query(state),
                    "direction_hint": direction_hint,
                    "plan_json": json.dumps(plan, ensure_ascii=False, indent=2),
                    "result_json": json.dumps(calculation_result, ensure_ascii=False, indent=2),
                    "operands_json": json.dumps(operands, ensure_ascii=False, indent=2),
                }
            )
            answer = _normalise_spaces(rendered.final_answer)
        except Exception as exc:
            logger.warning("[calc_renderer] structured output failed, using deterministic fallback: %s", exc)
            answer = str(calculation_result.get("rendered_value") or calculation_result.get("formatted_result") or "").strip()
            if not answer:
                answer = str(CALCULATION_RENDER_POLICY.get("render_generation_failed_fallback") or "")

        answer = self._coerce_sign_aware_subtraction_answer(
            answer,
            calculation_result=calculation_result,
        )
        if operation_family == "ratio" and self._ratio_component_consolidation_scope(calculation_result, operands):
            answer = self._compact_ratio_answer(state, calculation_result)
        elif operation_family == "ratio" and self._ratio_components_have_suspicious_scale(calculation_result):
            answer = self._compact_ratio_answer(state, calculation_result)

        calculation_result["formatted_result"] = answer
        return {
            "answer": answer,
            "compressed_answer": answer,
            "draft_points": [answer] if answer else [],
            **_runtime_trace_state_update(
                state,
                calculation_operands=operands,
                calculation_plan=plan,
                calculation_result=calculation_result,
                include_compatibility_mirrors=False,
            ),
        }

    def _verify_calculation_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Sanity-check that the rendered answer still matches the result."""
        answer = _normalise_spaces(str(state.get("answer") or state.get("compressed_answer") or ""))
        runtime_trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        calculation_result = dict(runtime_trace.get("calculation_result") or {})
        plan = dict(runtime_trace.get("calculation_plan") or {})
        operands = list(runtime_trace.get("calculation_operands") or [])

        if not answer:
            return {
                "answer": answer,
                "compressed_answer": answer,
            }

        if str(calculation_result.get("status") or "") != "ok":
            debug_trace = dict(state.get("calculation_debug_trace") or {})
            debug_trace["verification"] = {
                "verdict": "skip",
                "reason": "calculation_status_not_ok",
            }
            return {
                "answer": answer,
                "compressed_answer": answer,
                "calculation_debug_trace": debug_trace,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=plan,
                    calculation_result=calculation_result,
                    include_compatibility_mirrors=False,
                ),
            }

        deterministic_fallback = str(
            calculation_result.get("formatted_result")
            or calculation_result.get("rendered_value")
            or answer
        ).strip()
        rendered_value = str(calculation_result.get("rendered_value") or "").strip()
        operation = str(plan.get("operation") or "")
        operation_family = _normalise_spaces(
            str(
                (calculation_result.get("answer_slots") or {}).get("operation_family")
                or calculation_result.get("operation_family")
                or operation
            )
        ).lower()
        result_val = float(calculation_result.get("result_value") or 0)
        render_policy = dict(CALCULATION_RENDER_POLICY)
        direction_policy = dict((render_policy.get("direction_hints") or {}).get(operation) or {})
        if direction_policy:
            direction_hint = (
                str(direction_policy.get("positive") or "")
                if result_val > 0
                else str(direction_policy.get("negative") or "")
                if result_val < 0
                else str(direction_policy.get("zero") or "")
            )
        else:
            direction_hint = ""
        structured_llm = self._llm_for_phase("calculation_verification").with_structured_output(CalculationVerificationOutput)
        prompt = ChatPromptTemplate.from_template(
            str(render_policy.get("verification_prompt_template") or "")
        )
        try:
            verified: CalculationVerificationOutput = (prompt | structured_llm).invoke(
                {
                    "query": self._calc_query(state),
                    "answer": answer,
                    "fallback": deterministic_fallback,
                    "direction_hint": direction_hint,
                    "plan_json": json.dumps(plan, ensure_ascii=False, indent=2),
                    "result_json": json.dumps(calculation_result, ensure_ascii=False, indent=2),
                    "operands_json": json.dumps(operands, ensure_ascii=False, indent=2),
                }
            )
            verdict = str(verified.verdict or "keep")
            final_answer = _normalise_spaces(verified.final_answer)
            if verdict == "fallback" or not final_answer:
                final_answer = deterministic_fallback or answer
            final_answer = self._coerce_sign_aware_subtraction_answer(
                final_answer,
                calculation_result=calculation_result,
            )
            if operation_family == "ratio" and self._ratio_component_consolidation_scope(calculation_result, operands):
                final_answer = self._compact_ratio_answer(state, calculation_result)
            elif operation_family == "ratio" and self._ratio_components_have_suspicious_scale(calculation_result):
                final_answer = self._compact_ratio_answer(state, calculation_result)
            calculation_result["formatted_result"] = final_answer
            debug_trace = dict(state.get("calculation_debug_trace") or {})
            debug_trace["verification"] = {
                "verdict": verdict,
                "issues": list(verified.issues or []),
                "input_answer": answer,
                "final_answer": final_answer,
                "rendered_value": rendered_value,
                "direction_hint": direction_hint,
            }
            return {
                "answer": final_answer,
                "compressed_answer": final_answer,
                "draft_points": [final_answer] if final_answer else [],
                "unsupported_sentences": [] if verdict == "keep" else [answer],
                "sentence_checks": [
                    {
                        "sentence": answer,
                        "verdict": "keep" if verdict == "keep" else "drop_overextended",
                        "reason": ",".join(verified.issues or []) or verdict,
                        "supporting_claim_ids": state.get("selected_claim_ids", []),
                    }
                ] if answer else [],
                "calculation_debug_trace": debug_trace,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=plan,
                    calculation_result=calculation_result,
                    include_compatibility_mirrors=False,
                ),
            }
        except Exception as exc:
            logger.warning("[calc_verify] structured output failed, keeping rendered answer: %s", exc)
            debug_trace = dict(state.get("calculation_debug_trace") or {})
            debug_trace["verification"] = {
                "verdict": "error_keep",
                "error": str(exc),
                "input_answer": answer,
                "rendered_value": rendered_value,
            }
            return {
                "answer": answer,
                "compressed_answer": answer,
                "calculation_debug_trace": debug_trace,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=plan,
                    calculation_result=calculation_result,
                    include_compatibility_mirrors=False,
                ),
            }

    def _advance_calculation_subtask(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Persist the finished subtask and move to the next one, if any."""
        current_result = self._capture_current_subtask_result(state)
        subtask_results = self._upsert_subtask_result(
            list(state.get("subtask_results") or []),
            current_result,
        )
        tasks = [dict(task) for task in (state.get("calc_subtasks") or [])]
        active_index = int(state.get("active_subtask_index") or 0)
        next_index = active_index + 1
        if next_index < len(tasks):
            next_task = dict(tasks[next_index])
            return {
                "subtask_results": subtask_results,
                "active_subtask_index": next_index,
                "active_subtask": next_task,
                "subtask_loop_complete": False,
                "subtask_debug_trace": {
                    **dict(state.get("subtask_debug_trace") or {}),
                    "last_completed_task_id": str(current_result.get("task_id") or ""),
                    "next_task_id": str(next_task.get("task_id") or ""),
                },
                "selected_claim_ids": [],
                "draft_points": [],
                "compressed_answer": "",
                "kept_claim_ids": [],
                "dropped_claim_ids": [],
                "unsupported_sentences": [],
                "sentence_checks": [],
                "answer": "",
                "citations": [],
                "calculation_debug_trace": {},
                "planner_debug_trace": {},
                "missing_info": [],
                "reflection_count": 0,
                "retry_reason": "",
                "retry_queries": [],
                "reconciliation_retry_count": 0,
                "reflection_plan": {},
                "reconciliation_result": {},
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=[],
                    calculation_plan={},
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }
        return {
            "subtask_results": subtask_results,
            "subtask_loop_complete": True,
            "subtask_debug_trace": {
                **dict(state.get("subtask_debug_trace") or {}),
                "last_completed_task_id": str(current_result.get("task_id") or ""),
                "next_task_id": "",
            },
        }

    def _aggregate_calculation_subtasks(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Combine completed subtask outputs into a single caller-facing view."""
        current_result = self._capture_current_subtask_result(state)
        subtask_results = self._upsert_subtask_result(
            list(state.get("subtask_results") or []),
            current_result,
        )
        order_map = {
            str(task.get("task_id") or ""): index
            for index, task in enumerate(state.get("calc_subtasks") or [])
        }
        ordered_results = sorted(
            subtask_results,
            key=lambda row: (order_map.get(str(row.get("task_id") or ""), 10_000), str(row.get("task_id") or "")),
        )
        ordered_results = self._dedupe_aggregate_subtask_results(ordered_results)
        ordered_results = self._recover_lookup_results_from_sibling_table_evidence(ordered_results, state)
        ordered_results = self._promote_stronger_nested_aggregate_results(ordered_results)
        ordered_results = self._dedupe_aggregate_subtask_results(ordered_results)
        has_growth_rate_result = any(
            self._aggregate_result_operation_family(row) == "growth_rate"
            for row in ordered_results
        )
        answer_parts = [
            _normalise_spaces(str(row.get("answer") or ""))
            for row in ordered_results
            if _normalise_spaces(str(row.get("answer") or ""))
        ]
        fallback_answer = " ".join(answer_parts).strip() or _normalise_spaces(
            str(state.get("answer") or state.get("compressed_answer") or "")
        )
        fallback_answer = self._preferred_aggregate_fallback_answer(ordered_results, fallback_answer)
        supported_aggregate_answer = self._supported_aggregate_subtask_answer(ordered_results)
        complete_numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
        has_narrative_summary = any(self._row_is_narrative_summary(row) for row in ordered_results)
        lookup_list_answer = self._compose_lookup_list_numeric_answer(ordered_results)
        if lookup_list_answer:
            fallback_answer = lookup_list_answer
        numeric_answer_locked = bool(
            has_narrative_summary
            and
            complete_numeric_answer
            and not self._query_requests_explanatory_context(str(state.get("query") or ""))
        )
        final_answer = fallback_answer
        planner_feedback = ""
        deterministic_feedback = self._infer_planner_feedback_from_answer_slots(ordered_results)
        aggregate_evidence_items: List[Dict[str, Any]] = []
        seen_evidence_ids: set[str] = set()

        def _append_aggregate_evidence(items: List[Dict[str, Any]]) -> None:
            for item in list(items or []):
                evidence = dict(item or {})
                evidence_id = str(evidence.get("evidence_id") or "").strip()
                dedupe_key = evidence_id or "|".join(
                    [
                        str(evidence.get("source_anchor") or ""),
                        str(evidence.get("claim") or evidence.get("quote_span") or evidence.get("raw_row_text") or ""),
                    ]
                )
                if dedupe_key in seen_evidence_ids:
                    continue
                seen_evidence_ids.add(dedupe_key)
                aggregate_evidence_items.append(evidence)

        for row in ordered_results:
            _append_aggregate_evidence(list(row.get("runtime_evidence") or []))
        _append_aggregate_evidence(list(state.get("evidence_items") or []))
        preliminary_projection = self._build_aggregate_calculation_projection(ordered_results, fallback_answer)
        narrative_context = self._narrative_context_sentence_from_evidence(
            str(state.get("query") or ""),
            aggregate_evidence_items,
        )
        plan_loop_count = int(state.get("plan_loop_count") or 0)
        max_plan_loops = 2
        if hasattr(self, "llm") and getattr(self, "llm", None) is not None:
            structured_llm = self._llm_for_phase("aggregate_synthesis").with_structured_output(AggregateSynthesisOutput)
            prompt = ChatPromptTemplate.from_template(
                str(CALCULATION_PROMPT_POLICY.get("aggregate_synthesis_prompt_template") or "")
            )
            try:
                prompt_value = prompt.invoke(
                    {
                        "query": state["query"],
                        "fallback_answer": fallback_answer,
                        "deterministic_feedback": deterministic_feedback or "-",
                        "narrative_context": narrative_context or "-",
                        "subtask_results_json": json.dumps(ordered_results, ensure_ascii=False, indent=2),
                    }
                )
                synthesized: AggregateSynthesisOutput = structured_llm.invoke(prompt_value)
                final_answer = _normalise_spaces(str(synthesized.final_answer or "")) or fallback_answer
                planner_feedback = _normalise_spaces(str(synthesized.planner_feedback or ""))
            except Exception as exc:
                logger.warning("[aggregate_synth] structured output failed, using fallback join: %s", exc)
        if (
            deterministic_feedback
            and self._unresolved_structured_numeric_gap(ordered_results)
            and self._answer_reuses_narrative_summary_text(final_answer, ordered_results)
        ):
            safe_partial_answer = self._safe_partial_answer_for_numeric_gap(ordered_results)
            final_answer = safe_partial_answer or ""
        final_answer = self._coerce_sign_aware_subtraction_answer(
            final_answer,
            calculation_result=dict(preliminary_projection.get("calculation_result") or {}),
            subtask_results=ordered_results,
        )
        slot_based_difference_answer = self._compose_slot_based_difference_answer(
            query=str(state.get("query") or ""),
            report_scope=dict(state.get("report_scope") or {}),
            calculation_result=dict(preliminary_projection.get("calculation_result") or {}),
        )
        if slot_based_difference_answer:
            final_answer = slot_based_difference_answer
            complete_numeric_answer = slot_based_difference_answer
            planner_feedback = ""
            deterministic_feedback = ""
        if has_narrative_summary and not self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results):
            final_answer = self._ensure_complete_growth_numeric_answer(
                final_answer,
                ordered_results,
                evidence_items=aggregate_evidence_items,
            )
        if not deterministic_feedback:
            final_answer = self._include_narrative_context_if_needed(
                final_answer,
                query=str(state.get("query") or ""),
                narrative_context=narrative_context,
            )
        growth_narrative_answer = self._compose_growth_narrative_answer(
            query=str(state.get("query") or ""),
            ordered_results=ordered_results,
            existing_answer=final_answer,
            evidence_items=aggregate_evidence_items,
        )
        entity_table_answer = self._compose_entity_table_summary_answer(
            query=str(state.get("query") or ""),
            docs=list(state.get("seed_retrieved_docs", []) or []) + list(state.get("retrieved_docs", []) or []),
            evidence_items=aggregate_evidence_items,
        )
        composition_selected_claim_ids: List[str] = []
        calculation_projection_override: Optional[Dict[str, Any]] = None
        narrative_answer_locked = bool(
            supported_aggregate_answer
            and self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results)
        )
        if growth_narrative_answer and not narrative_answer_locked:
            growth_compressed_answer = _normalise_spaces(str(growth_narrative_answer.get("compressed_answer") or ""))
            final_answer = growth_compressed_answer or final_answer
            composition_selected_claim_ids.extend(
                str(claim_id).strip()
                for claim_id in (growth_narrative_answer.get("selected_claim_ids") or [])
                if str(claim_id).strip()
            )
            narrative_answer_locked = bool(growth_compressed_answer) or self._answer_satisfies_growth_narrative_intent(
                query=str(state.get("query") or ""),
                answer=final_answer,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            )
            planner_feedback = ""
            deterministic_feedback = ""
        if entity_table_answer and not narrative_answer_locked:
            final_answer = _normalise_spaces(str(entity_table_answer.get("compressed_answer") or "")) or final_answer
            composition_selected_claim_ids.extend(
                str(claim_id).strip()
                for claim_id in (entity_table_answer.get("selected_claim_ids") or [])
                if str(claim_id).strip()
            )
            projection = entity_table_answer.get("calculation_projection")
            if isinstance(projection, dict):
                calculation_projection_override = projection
            planner_feedback = ""
            deterministic_feedback = ""
        business_focus_answer = self._compose_business_technology_focus_answer(
            query=str(state.get("query") or ""),
            existing_answer=final_answer,
            docs=list(state.get("seed_retrieved_docs", []) or []) + list(state.get("retrieved_docs", []) or []),
            evidence_items=aggregate_evidence_items,
        )
        if business_focus_answer and not narrative_answer_locked:
            final_answer = _normalise_spaces(str(business_focus_answer.get("compressed_answer") or "")) or final_answer
            composition_selected_claim_ids.extend(
                str(claim_id).strip()
                for claim_id in (business_focus_answer.get("selected_claim_ids") or [])
                if str(claim_id).strip()
            )
            planner_feedback = ""
            deterministic_feedback = ""
        dividend_policy_answer = self._compose_dividend_policy_hybrid_answer(
            query=str(state.get("query") or ""),
            evidence_items=aggregate_evidence_items,
        )
        if dividend_policy_answer:
            dividend_answer = _normalise_spaces(str(dividend_policy_answer.get("answer") or ""))
            if dividend_answer:
                final_answer = dividend_answer
                composition_selected_claim_ids.extend(
                    str(claim_id).strip()
                    for claim_id in (dividend_policy_answer.get("supporting_claim_ids") or [])
                    if str(claim_id).strip()
                )
                calculation_projection_override = None
                planner_feedback = ""
                deterministic_feedback = ""
        quantitative_impact_answer = self._compose_supported_quantitative_impact_answer(
            query=str(state.get("query") or ""),
            evidence_items=aggregate_evidence_items,
        )
        if quantitative_impact_answer and not narrative_answer_locked:
            final_answer = _normalise_spaces(str(quantitative_impact_answer.get("answer") or "")) or final_answer
            composition_selected_claim_ids.extend(
                str(claim_id).strip()
                for claim_id in (quantitative_impact_answer.get("supporting_claim_ids") or [])
                if str(claim_id).strip()
            )
            narrative_answer_locked = True
            planner_feedback = ""
            deterministic_feedback = ""
        if not deterministic_feedback:
            augmented_answer = self._augment_narrative_answer_with_supported_drivers(
                final_answer,
                aggregate_evidence_items,
                query=str(state.get("query") or ""),
            )
            if augmented_answer and augmented_answer != final_answer:
                final_answer = augmented_answer
                composition_selected_claim_ids = self._expand_selected_claim_ids_for_narrative_drivers(
                    composition_selected_claim_ids,
                    aggregate_evidence_items,
                    query=str(state.get("query") or ""),
                )
        if not self._answer_satisfies_growth_narrative_intent(
            query=str(state.get("query") or ""),
            answer=final_answer,
            ordered_results=ordered_results,
            evidence_items=aggregate_evidence_items,
        ):
            repaired_growth_narrative_answer = self._compose_growth_narrative_answer(
                query=str(state.get("query") or ""),
                ordered_results=ordered_results,
                existing_answer=final_answer,
                evidence_items=aggregate_evidence_items,
            )
            repaired_answer = _normalise_spaces(
                str((repaired_growth_narrative_answer or {}).get("compressed_answer") or "")
            )
            if repaired_answer and self._answer_satisfies_growth_narrative_intent(
                query=str(state.get("query") or ""),
                answer=repaired_answer,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            ):
                final_answer = repaired_answer
                composition_selected_claim_ids = [
                    str(claim_id).strip()
                    for claim_id in ((repaired_growth_narrative_answer or {}).get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                ]
        if numeric_answer_locked:
            if has_narrative_summary and has_growth_rate_result:
                refreshed_answer = self._refresh_numeric_answer_preserving_narrative_context(
                    query=str(state.get("query") or ""),
                    current_answer=final_answer,
                    numeric_answer=complete_numeric_answer,
                    ordered_results=ordered_results,
                    evidence_items=aggregate_evidence_items,
                )
                final_answer = _normalise_spaces(str(refreshed_answer.get("answer") or complete_numeric_answer))
                composition_selected_claim_ids = [
                    str(claim_id).strip()
                    for claim_id in (refreshed_answer.get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                ]
            else:
                final_answer = complete_numeric_answer
                composition_selected_claim_ids = []
            calculation_projection_override = None
            planner_feedback = ""
            deterministic_feedback = ""
        final_answer = self._preserve_source_visible_query_terms(
            final_answer,
            query=str(state.get("query") or ""),
            ordered_results=ordered_results,
            evidence_items=aggregate_evidence_items,
            docs=list(state.get("seed_retrieved_docs", []) or []) + list(state.get("retrieved_docs", []) or []),
        )
        # Prefer the deterministic structured-material check over a stale
        # deterministic hint, but preserve independent synthesizer feedback for
        # replan/budget-exhausted cases.
        preliminary_status = _normalise_spaces(
            str((preliminary_projection.get("calculation_result") or {}).get("status") or "")
        ).lower()
        if (
            preliminary_status == "ok"
            and deterministic_feedback
            and (not planner_feedback or planner_feedback == deterministic_feedback)
        ):
            planner_feedback = ""
            deterministic_feedback = ""
        if (
            (planner_feedback or deterministic_feedback)
            and self._answer_satisfies_growth_narrative_intent(
                query=str(state.get("query") or ""),
                answer=final_answer,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            )
        ):
            planner_feedback = ""
            deterministic_feedback = ""
        source_task_ids = [
            str(row.get("task_id") or "").strip()
            for row in ordered_results
            if str(row.get("task_id") or "").strip()
        ]
        selected_claim_ids_for_integrity = list(
            dict.fromkeys(
                [
                    *[
                        claim_id
                        for row in ordered_results
                        for claim_id in (row.get("selected_claim_ids") or [])
                        if str(claim_id).strip()
                    ],
                    *composition_selected_claim_ids,
                ]
            )
        )
        ordered_result_source_refs = _clean_source_row_ids(
            [
                value
                for row in ordered_results
                for value in [
                    row.get("source_row_id"),
                    row.get("source_row_ids"),
                    (row.get("calculation_result") or {}).get("source_row_id")
                    if isinstance(row.get("calculation_result"), dict)
                    else None,
                    (row.get("calculation_result") or {}).get("source_row_ids")
                    if isinstance(row.get("calculation_result"), dict)
                    else None,
                    (row.get("answer_slots") or {}).get("source_row_id")
                    if isinstance(row.get("answer_slots"), dict)
                    else None,
                    (row.get("answer_slots") or {}).get("source_row_ids")
                    if isinstance(row.get("answer_slots"), dict)
                    else None,
                ]
            ]
        )
        projection_for_integrity = (
            calculation_projection_override
            if isinstance(calculation_projection_override, dict) and calculation_projection_override
            else preliminary_projection
        )
        projection_result_for_integrity = dict(projection_for_integrity.get("calculation_result") or {})
        projection_slots_for_integrity = dict(projection_result_for_integrity.get("answer_slots") or {})
        state_result_for_integrity = dict(state.get("calculation_result") or {})
        state_slots_for_integrity = dict(state_result_for_integrity.get("answer_slots") or {})
        ledger_artifacts = self._enrich_reconciliation_artifact_refs(
            list(state.get("artifacts") or []),
            task_id="",
            task_ids=source_task_ids,
            operand_rows=list(projection_for_integrity.get("calculation_operands") or []),
            extra_refs=[
                projection_result_for_integrity.get("source_row_id"),
                projection_result_for_integrity.get("source_row_ids"),
                projection_slots_for_integrity.get("source_row_id"),
                projection_slots_for_integrity.get("source_row_ids"),
                state_result_for_integrity.get("source_row_id"),
                state_result_for_integrity.get("source_row_ids"),
                state_slots_for_integrity.get("source_row_id"),
                state_slots_for_integrity.get("source_row_ids"),
                ordered_result_source_refs,
                selected_claim_ids_for_integrity,
            ],
        )
        task_artifact_trace = _project_task_artifact_trace(
            state.get("tasks") or [],
            ledger_artifacts,
        )
        integrity_feedback = _task_artifact_integrity_feedback(task_artifact_trace)
        if integrity_feedback:
            planner_feedback = ""
            deterministic_feedback = integrity_feedback
        if not deterministic_feedback:
            planner_feedback = ""
        elif not planner_feedback:
            planner_feedback = deterministic_feedback
        should_replan = bool(planner_feedback) and plan_loop_count < max_plan_loops
        if planner_feedback and not should_replan:
            refusal_suffix = "다만 질문에 필요한 수치를 끝내 모두 확보하지 못해 원하신 답을 완전히 확정할 수는 없습니다."
            visible_partial_answer = _normalise_spaces(final_answer or fallback_answer)
            if visible_partial_answer:
                final_answer = _normalise_spaces(f"{visible_partial_answer} {refusal_suffix}")
            else:
                final_answer = "질문에 필요한 수치를 끝내 충분히 확보하지 못했습니다."
        selected_claim_ids = list(
            dict.fromkeys(
                [
                    *[
                        claim_id
                        for row in ordered_results
                        for claim_id in (row.get("selected_claim_ids") or [])
                        if str(claim_id).strip()
                    ],
                    *composition_selected_claim_ids,
                ]
            )
        )
        aggregate_projection = self._build_aggregate_calculation_projection(ordered_results, final_answer)
        aligned_ordered_results = self._align_lookup_results_with_dependency_projection(
            ordered_results,
            state,
            aggregate_projection,
        )
        if aligned_ordered_results is not ordered_results:
            ordered_results = aligned_ordered_results
            refreshed_numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
            if refreshed_numeric_answer and (
                not narrative_answer_locked
                or self._aggregate_results_include_source_task_slot_realignment(ordered_results)
            ):
                refreshed_answer = self._refresh_numeric_answer_preserving_narrative_context(
                    query=str(state.get("query") or ""),
                    current_answer=final_answer,
                    numeric_answer=refreshed_numeric_answer,
                    ordered_results=ordered_results,
                    evidence_items=aggregate_evidence_items,
                )
                final_answer = _normalise_spaces(str(refreshed_answer.get("answer") or refreshed_numeric_answer))
                selected_claim_ids = list(
                    dict.fromkeys(
                        [
                            *selected_claim_ids,
                            *[
                                str(claim_id).strip()
                                for claim_id in (refreshed_answer.get("selected_claim_ids") or [])
                                if str(claim_id).strip()
                            ],
                        ]
                    )
                )
            aggregate_projection = self._build_aggregate_calculation_projection(ordered_results, final_answer)
        if calculation_projection_override:
            for key in ("calculation_operands", "calculation_plan", "calculation_result"):
                if calculation_projection_override.get(key):
                    aggregate_projection[key] = calculation_projection_override[key]
        projection_calculation_result = dict(aggregate_projection.get("calculation_result") or {})
        projection_answer_slots = dict(projection_calculation_result.get("answer_slots") or {})
        projection_operation_family = _normalise_spaces(
            str(
                projection_answer_slots.get("operation_family")
                or (projection_calculation_result.get("derived_metrics") or {}).get("operation_family")
                or ""
            )
        ).lower()
        projection_rendered_value = _normalise_spaces(str(projection_calculation_result.get("rendered_value") or ""))
        if (
            projection_operation_family == "ratio"
            and projection_rendered_value
            and projection_rendered_value not in _normalise_spaces(final_answer)
        ):
            refreshed_ratio_answer = self._compact_ratio_answer(
                {
                    **state,
                    "active_subtask": {
                        **dict(state.get("active_subtask") or {}),
                        "metric_label": projection_answer_slots.get("metric_label")
                        or (state.get("active_subtask") or {}).get("metric_label")
                        or "",
                    },
                },
                projection_calculation_result,
            )
            if refreshed_ratio_answer:
                final_answer = refreshed_ratio_answer
                aggregate_projection["calculation_result"]["formatted_result"] = final_answer
        slot_based_difference_answer = self._compose_slot_based_difference_answer(
            query=str(state.get("query") or ""),
            report_scope=dict(state.get("report_scope") or {}),
            calculation_result=dict(aggregate_projection.get("calculation_result") or {}),
        )
        if slot_based_difference_answer:
            final_answer = slot_based_difference_answer
            aggregate_projection["calculation_result"]["formatted_result"] = final_answer
        final_answer = self._preserve_source_visible_query_terms(
            final_answer,
            query=str(state.get("query") or ""),
            ordered_results=ordered_results,
            evidence_items=aggregate_evidence_items,
            docs=list(state.get("seed_retrieved_docs", []) or []) + list(state.get("retrieved_docs", []) or []),
        )
        if has_narrative_summary:
            final_answer = self._prune_irrelevant_growth_narrative_sentences(
                query=str(state.get("query") or ""),
                answer=final_answer,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            )
        final_conflicting_narrative: Dict[str, Any] = {}
        if not self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results):
            final_conflicting_narrative = self._preferred_conflicting_growth_narrative_answer(
                query=str(state.get("query") or ""),
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            )
        if final_conflicting_narrative:
            final_answer = _normalise_spaces(str(final_conflicting_narrative.get("answer") or final_answer))
            selected_claim_ids = list(
                dict.fromkeys(
                    [
                        *selected_claim_ids,
                        *[
                            str(claim_id).strip()
                            for claim_id in (final_conflicting_narrative.get("selected_claim_ids") or [])
                            if str(claim_id).strip()
                        ],
                    ]
                )
            )
        if has_narrative_summary and not self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results):
            final_answer = self._ensure_complete_growth_numeric_answer(
                final_answer,
                ordered_results,
                evidence_items=aggregate_evidence_items,
            )
        late_promoted_results = self._promote_stronger_nested_aggregate_results(ordered_results)
        if late_promoted_results is not ordered_results:
            ordered_results = late_promoted_results
            aggregate_projection = self._build_aggregate_calculation_projection(ordered_results, final_answer)
            late_aligned_results = self._align_lookup_results_with_dependency_projection(
                ordered_results,
                state,
                aggregate_projection,
            )
            if late_aligned_results is not ordered_results:
                ordered_results = late_aligned_results
                aggregate_projection = self._build_aggregate_calculation_projection(ordered_results, final_answer)
            late_supported_answer = self._supported_aggregate_subtask_answer(ordered_results)
            late_numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
            late_answer = late_supported_answer or late_numeric_answer
            if late_answer:
                refreshed_answer = self._refresh_numeric_answer_preserving_narrative_context(
                    query=str(state.get("query") or ""),
                    current_answer=final_answer,
                    numeric_answer=late_answer,
                    ordered_results=ordered_results,
                    evidence_items=aggregate_evidence_items,
                )
                final_answer = _normalise_spaces(str(refreshed_answer.get("answer") or late_answer))
                selected_claim_ids = list(
                    dict.fromkeys(
                        [
                            *selected_claim_ids,
                            *[
                                str(claim_id).strip()
                                for claim_id in (refreshed_answer.get("selected_claim_ids") or [])
                                if str(claim_id).strip()
                            ],
                        ]
                    )
                )
        runtime_numeric_answer = self._late_runtime_numeric_answer(state, final_answer)
        if runtime_numeric_answer:
            if has_narrative_summary and has_growth_rate_result:
                refreshed_answer = self._refresh_numeric_answer_preserving_narrative_context(
                    query=str(state.get("query") or ""),
                    current_answer=final_answer,
                    numeric_answer=runtime_numeric_answer,
                    ordered_results=ordered_results,
                    evidence_items=aggregate_evidence_items,
                )
                final_answer = _normalise_spaces(str(refreshed_answer.get("answer") or runtime_numeric_answer))
                selected_claim_ids = list(
                    dict.fromkeys(
                        [
                            *selected_claim_ids,
                            *[
                                str(claim_id).strip()
                                for claim_id in (refreshed_answer.get("selected_claim_ids") or [])
                                if str(claim_id).strip()
                            ],
                        ]
                    )
                )
            else:
                final_answer = runtime_numeric_answer
        final_answer = self._enforce_source_stated_growth_answer_contract(
            final_answer,
            ordered_results,
            evidence_items=aggregate_evidence_items,
        )
        if final_answer:
            aggregate_projection.setdefault("calculation_result", {})["formatted_result"] = final_answer
            if str((aggregate_projection.get("calculation_plan") or {}).get("mode") or "") == "aggregate_subtasks":
                aggregate_projection["calculation_result"]["rendered_value"] = final_answer
        if final_answer and not deterministic_feedback:
            aggregate_projection["calculation_result"]["status"] = "ok"
        aggregate_evidence_items = self._append_operand_evidence_for_final_answer(
            aggregate_evidence_items,
            operands=list(aggregate_projection.get("calculation_operands") or []),
            final_answer=final_answer,
        )
        narrative_docs = list(state.get("seed_retrieved_docs", []) or []) + list(state.get("retrieved_docs", []) or [])
        aggregate_evidence_items, retrieved_narrative_claim_ids = self._append_retrieved_narrative_evidence_for_final_answer(
            aggregate_evidence_items,
            final_answer=final_answer,
            docs=narrative_docs,
        )
        if retrieved_narrative_claim_ids:
            selected_claim_ids = list(dict.fromkeys([*selected_claim_ids, *retrieved_narrative_claim_ids]))
            source_surface_answer = self._preserve_retrieved_narrative_source_surface(
                final_answer,
                aggregate_evidence_items,
            )
            if source_surface_answer != final_answer:
                final_answer = source_surface_answer
                aggregate_projection.setdefault("calculation_result", {})["formatted_result"] = final_answer
                if str((aggregate_projection.get("calculation_plan") or {}).get("mode") or "") == "aggregate_subtasks":
                    aggregate_projection["calculation_result"]["rendered_value"] = final_answer
        if has_narrative_summary and not self._answer_satisfies_growth_narrative_intent(
            query=str(state.get("query") or ""),
            answer=final_answer,
            ordered_results=ordered_results,
            evidence_items=aggregate_evidence_items,
        ):
            repaired_growth_narrative_answer = self._compose_growth_narrative_answer(
                query=str(state.get("query") or ""),
                ordered_results=ordered_results,
                existing_answer=final_answer,
                evidence_items=aggregate_evidence_items,
            )
            repaired_answer = _normalise_spaces(
                str((repaired_growth_narrative_answer or {}).get("compressed_answer") or "")
            )
            if repaired_answer and self._answer_satisfies_growth_narrative_intent(
                query=str(state.get("query") or ""),
                answer=repaired_answer,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            ):
                final_answer = repaired_answer
                selected_claim_ids = list(
                    dict.fromkeys(
                        [
                            *selected_claim_ids,
                            *[
                                str(claim_id).strip()
                                for claim_id in ((repaired_growth_narrative_answer or {}).get("selected_claim_ids") or [])
                                if str(claim_id).strip()
                            ],
                        ]
                    )
                )
                aggregate_projection.setdefault("calculation_result", {})["formatted_result"] = final_answer
                if str((aggregate_projection.get("calculation_plan") or {}).get("mode") or "") == "aggregate_subtasks":
                    aggregate_projection["calculation_result"]["rendered_value"] = final_answer
                aggregate_evidence_items = self._append_operand_evidence_for_final_answer(
                    aggregate_evidence_items,
                    operands=list(aggregate_projection.get("calculation_operands") or []),
                    final_answer=final_answer,
                )
        contracted_answer = self._enforce_source_stated_growth_answer_contract(
            final_answer,
            ordered_results,
            evidence_items=aggregate_evidence_items,
        )
        if contracted_answer != final_answer:
            final_answer = contracted_answer
            aggregate_projection.setdefault("calculation_result", {})["formatted_result"] = final_answer
            if str((aggregate_projection.get("calculation_plan") or {}).get("mode") or "") == "aggregate_subtasks":
                aggregate_projection["calculation_result"]["rendered_value"] = final_answer
            aggregate_evidence_items = self._append_operand_evidence_for_final_answer(
                aggregate_evidence_items,
                operands=list(aggregate_projection.get("calculation_operands") or []),
                final_answer=final_answer,
            )
        source_surface_answer = self._preserve_retrieved_narrative_source_surface(
            final_answer,
            aggregate_evidence_items,
        )
        if source_surface_answer != final_answer:
            final_answer = source_surface_answer
            aggregate_projection.setdefault("calculation_result", {})["formatted_result"] = final_answer
            if str((aggregate_projection.get("calculation_plan") or {}).get("mode") or "") == "aggregate_subtasks":
                aggregate_projection["calculation_result"]["rendered_value"] = final_answer
        if final_answer and has_narrative_summary and has_growth_rate_result:
            missing_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ()))
            final_answer_is_missing = any(marker and marker in final_answer for marker in missing_markers)
            final_has_nonnumeric_narrative = False
            for sentence in _split_narrative_sentences(final_answer):
                cleaned_sentence = _normalise_spaces(sentence)
                if not cleaned_sentence or self._answer_evidence_numeric_candidates(cleaned_sentence):
                    continue
                sentence_terms = [
                    term
                    for term in self._narrative_context_terms(cleaned_sentence)
                    if len(term) >= 3
                ]
                if len(sentence_terms) >= 2:
                    final_has_nonnumeric_narrative = True
                    break
            final_answer_terms = {
                term.lower()
                for term in self._narrative_context_terms(final_answer)
                if len(term) >= 3
            }
            narrative_rows = [
                row
                for row in ordered_results
                if self._row_is_narrative_summary(row)
            ] if not (final_answer_is_missing or final_has_nonnumeric_narrative) else []
            for row in narrative_rows:
                row_answer = _normalise_spaces(
                    str(
                        row.get("answer")
                        or (row.get("calculation_result") or {}).get("formatted_result")
                        or (row.get("calculation_result") or {}).get("rendered_value")
                        or ""
                    )
                )
                if not row_answer or row_answer in final_answer:
                    continue
                if any(marker and marker in row_answer for marker in missing_markers):
                    continue
                if self._answer_evidence_numeric_candidates(row_answer):
                    continue
                row_answer_terms = {
                    term.lower()
                    for term in self._narrative_context_terms(row_answer)
                    if len(term) >= 3
                }
                if row_answer_terms and final_answer_terms:
                    overlap = row_answer_terms & final_answer_terms
                    if len(overlap) >= max(2, min(len(row_answer_terms), len(final_answer_terms)) // 2):
                        continue
                if self._narrative_summary_conflicts_with_growth_trace(
                    row_answer,
                    ordered_results,
                    aggregate_evidence_items,
                ):
                    continue
                combined_answer = _normalise_spaces(f"{final_answer} {row_answer}")
                if self._growth_answer_has_untraced_numeric_material(
                    combined_answer,
                    ordered_results,
                    aggregate_evidence_items,
                ):
                    continue
                final_answer = combined_answer
                aggregate_projection.setdefault("calculation_result", {})["formatted_result"] = final_answer
                if str((aggregate_projection.get("calculation_plan") or {}).get("mode") or "") == "aggregate_subtasks":
                    aggregate_projection["calculation_result"]["rendered_value"] = final_answer
                selected_claim_ids = list(
                    dict.fromkeys(
                        [
                            *selected_claim_ids,
                            *[
                                str(claim_id).strip()
                                for claim_id in (row.get("selected_claim_ids") or [])
                                if str(claim_id).strip()
                            ],
                        ]
                    )
                )
                break
        aggregate_evidence_items = self._filter_aggregate_evidence_for_final_answer(
            aggregate_evidence_items,
            final_answer=final_answer,
            selected_claim_ids=selected_claim_ids,
        )
        kept_evidence_ids = [
            str(item.get("evidence_id") or "").strip()
            for item in aggregate_evidence_items
            if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
        ]
        if kept_evidence_ids:
            kept_evidence_id_set = set(kept_evidence_ids)
            selected_claim_ids = list(
                dict.fromkeys(
                    [
                        *[
                            claim_id
                            for claim_id in selected_claim_ids
                            if claim_id in kept_evidence_id_set
                        ],
                        *[
                            evidence_id
                            for evidence_id in kept_evidence_ids
                            if evidence_id.startswith("operand::")
                        ],
                    ]
                )
            )
        aggregate_projection = self._filter_aggregate_projection_provenance(
            aggregate_projection,
            kept_evidence_ids,
        )
        artifacts = list(ledger_artifacts)
        tasks = list(state.get("tasks") or [])
        artifact_id = f"aggregate:{len(artifacts) + 1:03d}"
        artifacts = _append_artifact(
            artifacts,
            artifact_id=artifact_id,
            task_id="aggregate",
            kind=ArtifactKind.AGGREGATED_ANSWER,
            status="ok",
            summary=final_answer[:200],
            payload={
                "subtask_results": ordered_results,
                "final_answer": final_answer,
                "planner_feedback": planner_feedback,
                **aggregate_projection,
            },
            evidence_refs=selected_claim_ids,
        )
        tasks = _upsert_task(
            tasks,
            task_id="aggregate",
            kind=TaskKind.SYNTHESIS,
            label="Aggregate subtask results",
            status=TaskStatus.PARTIAL if planner_feedback else TaskStatus.COMPLETED,
            query=str(state.get("query") or ""),
            metric_family="aggregate",
            artifact_id=artifact_id,
        )
        return {
            "subtask_results": ordered_results,
            "subtask_loop_complete": True,
            "answer": final_answer,
            "compressed_answer": final_answer,
            "planner_mode": "replan" if should_replan else "initial",
            "planner_feedback": planner_feedback,
            "draft_points": [final_answer] if final_answer else [],
            "selected_claim_ids": selected_claim_ids,
            "kept_claim_ids": selected_claim_ids,
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "tasks": tasks,
            "artifacts": artifacts,
            "evidence_items": aggregate_evidence_items or aggregate_projection.get("evidence_items", []),
            **_runtime_trace_state_update(
                state,
                calculation_operands=aggregate_projection["calculation_operands"],
                calculation_plan=aggregate_projection["calculation_plan"],
                calculation_result=aggregate_projection["calculation_result"],
                include_compatibility_mirrors=False,
            ),
        }

    def _prepare_reflection_retry(self, state: FinancialAgentState) -> Dict[str, Any]:
        current_count = int(state.get("reflection_count") or 0)
        runtime_trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        operands = list(runtime_trace.get("calculation_operands") or [])
        plan = dict(runtime_trace.get("calculation_plan") or {})
        calc_result = dict(runtime_trace.get("calculation_result") or {})
        reflection_plan = dict(state.get("reflection_plan") or {})

        missing_info = [
            str(item).strip()
            for item in (
                reflection_plan.get("missing_info")
                or plan.get("missing_info")
                or state.get("missing_info")
                or []
            )
            if str(item).strip()
        ]
        if not missing_info:
            missing_info = self._infer_missing_info(state, operands)
        retry_queries = self._finalize_retry_queries(state, reflection_plan, missing_info)
        retry_reason = (
            str(reflection_plan.get("explanation") or "")
            or str(plan.get("explanation") or "")
            or str(calc_result.get("explanation") or "")
            or str(state.get("retry_reason") or "")
            or "missing operands"
        )
        logger.info(
            "[reflection] trigger retry=%s missing_info=%s retry_queries=%s reason=%s",
            current_count + 1,
            missing_info,
            retry_queries,
            retry_reason,
        )
        return {
            "missing_info": missing_info,
            "reflection_count": current_count + 1,
            "retry_reason": retry_reason,
            "retry_strategy": _normalise_spaces(
                str(reflection_plan.get("retry_strategy") or state.get("retry_strategy") or "retry_retrieval")
            ).lower(),
            "retry_queries": retry_queries,
            "evidence_bullets": [],
            "evidence_items": [],
            "evidence_status": "missing",
            "selected_claim_ids": [],
            "draft_points": [],
            "compressed_answer": "",
            "kept_claim_ids": [],
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "answer": "",
            "citations": [],
            "calculation_debug_trace": {},
            "planner_debug_trace": {},
            "reflection_plan": reflection_plan,
            **_runtime_trace_state_update(
                state,
                calculation_operands=[],
                calculation_plan={},
                calculation_result={},
                include_compatibility_mirrors=False,
            ),
        }

    def _route_after_prepare_retry(self, state: FinancialAgentState) -> str:
        if self._active_retry_strategy(state) == "synthesize_from_task_outputs":
            return "operand_extractor"
        return "retrieve"

    def _route_after_expand(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        active_operation = str(active_subtask.get("operation_family") or "").strip().lower()
        if active_operation == "narrative_summary":
            return "evidence"
        if list(state.get("calc_subtasks") or []):
            if active_operation in {"lookup", "single_value"}:
                return "numeric_extractor"
            return "evidence"
        intent = state.get("intent") or state.get("query_type", "qa")
        if intent == "numeric_fact":
            return "numeric_extractor"
        return "evidence"

    def _route_after_numeric_extractor(self, state: FinancialAgentState) -> str:
        if list(state.get("calc_subtasks") or []):
            active_subtask = dict(state.get("active_subtask") or {})
            active_operation = str(active_subtask.get("operation_family") or "").strip().lower()
            evidence_status = str(state.get("evidence_status") or "").strip().lower()
            has_retrieved_docs = bool(state.get("retrieved_docs") or state.get("seed_retrieved_docs"))
            if active_operation in {"lookup", "single_value"} and evidence_status == "missing" and has_retrieved_docs:
                return "reconcile_plan"
            return "advance_subtask"
        return "cite"

    def _route_after_evidence(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        active_operation = str(active_subtask.get("operation_family") or "").strip().lower()
        if active_operation == "narrative_summary":
            return "compress"
        if list(state.get("calc_subtasks") or []):
            return "reconcile_plan"
        intent = state.get("intent") or state.get("query_type", "qa")
        if intent in {"comparison", "trend"}:
            return "reconcile_plan"
        return "compress"

    def _route_after_reconcile_plan(self, state: FinancialAgentState) -> str:
        result = dict(state.get("reconciliation_result") or {})
        status = str(result.get("status") or "ready")
        retry_strategy = _normalise_spaces(str(result.get("retry_strategy") or "")).lower()
        if status == "ready":
            return "operand_extractor"
        if retry_strategy == "synthesize_from_task_outputs":
            return "operand_extractor"
        if status == "retry_retrieval":
            return "retrieve"
        if status == "insufficient_operands":
            active_subtask = dict(state.get("active_subtask") or {})
            required_operands = [
                item
                for item in (active_subtask.get("required_operands") or [])
                if isinstance(item, dict) and bool(item.get("required", True))
            ]
            has_retrieved_docs = bool(state.get("retrieved_docs") or state.get("seed_retrieved_docs"))
            if required_operands and has_retrieved_docs and not _requires_direct_numeric_grounding(active_subtask):
                return "operand_extractor"
        return "advance_subtask"

    def _route_after_advance_subtask(self, state: FinancialAgentState) -> str:
        if bool(state.get("subtask_loop_complete")):
            return "aggregate_subtasks"
        active_subtask = dict(state.get("active_subtask") or {})
        active_operation = str(active_subtask.get("operation_family") or "").strip().lower()
        if active_operation in {"lookup", "single_value", "narrative_summary"}:
            return "retrieve"
        return "reconcile_plan"

    def _route_after_aggregate_subtasks(self, state: FinancialAgentState) -> str:
        planner_feedback = _normalise_spaces(str(state.get("planner_feedback") or ""))
        if planner_feedback and int(state.get("plan_loop_count") or 0) < 2:
            return "pre_calc_planner"
        return "cite"

    def _route_after_validate(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        if str(active_subtask.get("operation_family") or "").strip().lower() == "narrative_summary" and list(state.get("calc_subtasks") or []):
            return "advance_subtask"
        return "cite"

    def _route_after_formula_planner(self, state: FinancialAgentState) -> str:
        if not self._is_reflection_eligible(state):
            return "calculator"
        if int(state.get("reflection_count") or 0) >= 1:
            return "calculator"
        plan = dict(
            _resolve_runtime_calculation_trace(
                dict(state),
                allow_legacy_top_level=False,
            ).get("calculation_plan") or {}
        )
        status = str(plan.get("status") or "ok").lower()
        if status == "incomplete":
            return "reflection_replan"
        return "calculator"

    def _route_after_calculator(self, state: FinancialAgentState) -> str:
        if not self._is_reflection_eligible(state):
            return "calc_render"
        if int(state.get("reflection_count") or 0) >= 1:
            return "calc_render"
        result = dict(
            _resolve_runtime_calculation_trace(
                dict(state),
                allow_legacy_top_level=False,
            ).get("calculation_result") or {}
        )
        status = str(result.get("status") or "")
        if status in {"insufficient_operands", "parse_error"}:
            return "reflection_replan"
        return "calc_render"

    def _format_citations(self, state: FinancialAgentState) -> Dict[str, Any]:
        seen = set()
        citations: List[str] = []
        selected_claim_ids = {
            str(claim_id).strip()
            for claim_id in (state.get("selected_claim_ids") or [])
            if str(claim_id).strip()
        }
        for evidence in list(state.get("evidence_items") or []):
            if not isinstance(evidence, dict):
                continue
            evidence_id = str(evidence.get("evidence_id") or "").strip()
            if selected_claim_ids and evidence_id not in selected_claim_ids:
                continue
            anchor = _normalise_spaces(str(evidence.get("source_anchor") or ""))
            metadata = dict(evidence.get("metadata") or {})
            metadata_anchor = self._build_source_anchor(metadata) if metadata else ""
            if metadata_anchor and (not anchor or len(metadata_anchor) > len(anchor)):
                anchor = metadata_anchor
            if not anchor:
                continue
            key = ("evidence", anchor)
            if key in seen:
                continue
            seen.add(key)
            citations.append(anchor)
        for doc, score in state.get("retrieved_docs", []):
            metadata = doc.metadata or {}
            key = (
                metadata.get("company"),
                metadata.get("year"),
                metadata.get("section_path"),
                metadata.get("chunk_uid"),
            )
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                f"[{metadata.get('company', '?')}] {metadata.get('year', '?')}년 "
                f"{metadata.get('report_type', '?')} / {metadata.get('section_path', metadata.get('section', '?'))} "
                f"/ {metadata.get('block_type', '?')} (score: {score:.3f})"
            )
        return {"citations": citations}

