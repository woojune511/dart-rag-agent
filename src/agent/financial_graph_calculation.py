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
from src.config import get_financial_ontology
from src.config.retrieval_policy import KOREAN_PERIOD_PREFIX_RE_FRAGMENT
from src.schema import ArtifactKind, TaskKind, TaskStatus

logger = logging.getLogger(__name__)

class FinancialAgentCalculationMixin:
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
            label = re.sub(r"20\d{2}\s*년?", " ", label)
            for needle in ("총액", "증감률", "증감액", "증가율", "비중", "비율"):
                label = label.replace(needle, " ")
            label = re.sub(r"(^|\s)부문(?=\s|$)", " ", label)
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
        match = re.search(r"20\d{2}\s*년?", label)
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
                *(match.group(0) for match in re.finditer(r"20\d{2}\s*년?", metric_label)),
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

    def _preferred_aggregate_fallback_answer(
        self,
        ordered_results: List[Dict[str, Any]],
        default_answer: str,
    ) -> str:
        for row in ordered_results:
            sibling_metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            sibling_operation_family = self._aggregate_result_operation_family(row)
            if sibling_metric_family != "narrative_summary" and sibling_operation_family != "narrative_summary":
                continue
            sibling_answer = _normalise_spaces(str(row.get("answer") or ""))
            if sibling_answer and re.search(r"\d", sibling_answer):
                return sibling_answer
        return default_answer

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
            if raw_unit in {"%", "%p"}:
                normalized_unit = "PERCENT"
            elif raw_unit in {"원", "천원", "백만원", "억원", "조원"}:
                normalized_unit = "KRW"
            elif raw_unit in {"개", "명"}:
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
            if not self._answer_slot_has_material(source_slot):
                continue
            if not self._dependency_slot_matches_input(binding, source_slot, sibling_row=sibling_row):
                continue
            raw_unit, normalized_unit = self._infer_dependency_row_unit(source_slot, sibling_result)
            normalized_value = source_slot.get("normalized_value")
            if normalized_value is None:
                normalized_value = sibling_result.get("result_value")
            source_anchor = _normalise_spaces(str(source_slot.get("source_anchor") or sibling_result.get("source_anchor") or ""))
            if not source_anchor:
                for operand_row in list(sibling_row.get("calculation_operands") or []):
                    operand_candidate = dict(operand_row or {})
                    if not _operand_row_matches_requirement(operand_candidate, binding):
                        continue
                    source_anchor = _normalise_spaces(str(operand_candidate.get("source_anchor") or ""))
                    if source_anchor:
                        break
            dependency_rows.append(
                {
                    "operand_id": f"dep_{preferred_task_id}_{index:03d}",
                    "evidence_id": f"task_output:{preferred_task_id}",
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
                    "matched_operand_label": _normalise_spaces(str(binding.get("label") or "")),
                    "matched_operand_concept": _normalise_spaces(str(binding.get("concept") or "")),
                    "matched_operand_role": _normalise_spaces(str(binding.get("role") or "")),
                    "source_task_id": preferred_task_id,
                    "source_slot": source_slot_name,
                    "dependency_resolved": True,
                }
            )
        return dependency_rows

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

    def _dependency_binding_identity(self, binding: Dict[str, Any]) -> tuple[str, str]:
        return (
            _normalise_spaces(str(binding.get("label") or "")),
            _normalise_spaces(str(binding.get("role") or "")),
        )

    def _material_gap_feedback_for_subtask_result(self, row: Dict[str, Any]) -> str:
        metric_label = _normalise_spaces(
            str(row.get("metric_label") or row.get("answer") or row.get("task_id") or "계산 결과")
        )
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        operation_family = str(
            answer_slots.get("operation_family")
            or ((row.get("calculation_plan") or {}).get("operation_family"))
            or ((calculation_result.get("derived_metrics") or {}).get("operation_family"))
            or ""
        ).strip().lower()
        if not operation_family:
            operation_family = str((row.get("calculation_plan") or {}).get("operation") or "").strip().lower()

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
                return f"{metric_label} direct value가 누락되었습니다."
            return ""

        if operation_family in {"difference", "growth_rate"}:
            current_slot = dict(answer_slots.get("current_value") or {})
            prior_slot = dict(answer_slots.get("prior_value") or {})
            primary_slot = dict(answer_slots.get("primary_value") or {})
            missing_labels: List[str] = []
            if not self._answer_slot_has_material(current_slot):
                missing_labels.append(f"{str(current_slot.get('period') or calculation_result.get('current_period') or 'current')} 값")
            if not self._answer_slot_has_material(prior_slot):
                missing_labels.append(f"{str(prior_slot.get('period') or calculation_result.get('prior_period') or 'prior')} 값")
            if operation_family == "difference":
                if not self._answer_slot_has_material(dict(answer_slots.get("delta_value") or primary_slot)):
                    missing_labels.append("증감값")
            else:
                if not self._answer_slot_has_material(primary_slot):
                    missing_labels.append("증감률")
            if missing_labels:
                return f"{metric_label} 계산에 필요한 {' / '.join(missing_labels)}이 누락되었습니다."
            return ""

        if operation_family in {"ratio", "sum"}:
            if not self._answer_slot_has_material(dict(answer_slots.get("primary_value") or {})):
                return f"{metric_label} 계산 결과가 누락되었습니다."
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
                    or self._narrative_summary_gap_is_satisfied(row, ordered_results)
                ):
                    continue
                gap = self._material_gap_feedback_for_subtask_result(row)
                if gap:
                    if self._feedback_gap_is_satisfied_by_derived_slots(gap, ordered_results):
                        continue
                    return gap
                metric_label = _normalise_spaces(
                    str(row.get("metric_label") or row.get("task_id") or "계산 결과")
                )
                generic_gap = f"{metric_label} 계산에 필요한 재료가 누락되었습니다."
                if self._feedback_gap_is_satisfied_by_derived_slots(generic_gap, ordered_results):
                    continue
                return generic_gap

            gap = self._material_gap_feedback_for_subtask_result(row)
            if gap and (
                self._sibling_lookup_gap_is_satisfied(row, ordered_results)
                or self._lookup_gap_is_satisfied_by_sibling_slots(row, ordered_results)
                or self._narrative_summary_gap_is_satisfied(row, ordered_results)
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
            "2023년",
            "2022년",
            "전년",
            "대비",
            "증감률",
            "계산",
            "계산해",
            "찾고",
            "찾아",
            "총액",
            "시설투자",
            "CAPEX",
            "capex",
            "집행된",
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
            if "이사의 경영진단" in source_text:
                term_score += 2
            if str(evidence.get("support_level") or "").lower() == "context":
                term_score += 1
            if term_score <= best_score:
                continue
            best_score = term_score
            best_sentence = claim

        if best_score <= 0 or not best_sentence:
            return ""
        best_sentence = re.split(r"(?<=[.!?。])\s+", best_sentence)[0]
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
            if term not in {"불구하고", "불구"}
        ]
        context_terms = [term for term in key_terms if term in context]
        if context_terms and any(term in answer_text for term in context_terms):
            return answer_text
        if context in answer_text:
            return answer_text
        return _normalise_spaces(f"{context} {answer_text}")

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
        narrative_markers = ("영향", "기여", "개선", "성장", "인수", "편입", "확대", "강화", "회복", "둔화")
        missing_markers = ("확인하지 못", "충분히 확인", "계산할 수 없습니다", "누락", "필요한 값")
        candidates: List[tuple[int, str, List[str]]] = []

        def _add_candidate(text: str, claim_ids: List[str], base_score: int) -> None:
            normalized = _normalise_spaces(text)
            if not normalized or any(marker in normalized for marker in missing_markers):
                return
            sentences = re.split(r"(?<=[.!?。])\s+", normalized)
            for sentence in sentences:
                cleaned = _normalise_spaces(sentence)
                if not cleaned or any(marker in cleaned for marker in missing_markers):
                    continue
                haystack = cleaned.lower()
                score = base_score
                score += sum(3 for term in query_terms if term.lower() in haystack)
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
            claim = str(evidence.get("claim") or evidence.get("quote_span") or evidence.get("raw_row_text") or "")
            claim_id = str(evidence.get("evidence_id") or "").strip()
            _add_candidate(claim, [claim_id] if claim_id else [], 2)

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates

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
        if not self._answer_looks_truncated(existing_answer):
            return None

        growth_row: Optional[Dict[str, Any]] = None
        growth_slots: Dict[str, Any] = {}
        for row in ordered_results or []:
            if self._aggregate_result_operation_family(row) != "growth_rate":
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

        primary_slot = growth_slots["primary_value"]
        current_slot = growth_slots["current_value"]
        prior_slot = growth_slots["prior_value"]
        growth_value = _normalise_spaces(str(primary_slot.get("rendered_value") or primary_slot.get("raw_value") or ""))
        current_value = _normalise_spaces(str(current_slot.get("rendered_value") or current_slot.get("raw_value") or ""))
        prior_period = _normalise_spaces(str(prior_slot.get("period") or "전년"))
        current_period = _normalise_spaces(str(current_slot.get("period") or primary_slot.get("period") or ""))
        metric_label = _normalise_spaces(
            str(current_slot.get("label") or primary_slot.get("label") or growth_row.get("metric_label") or "")
        )
        metric_label = re.sub(r"20\d{2}\s*년?", " ", metric_label)
        metric_label = _normalise_spaces(metric_label)
        if not growth_value or not current_value or not metric_label:
            return None

        direction = _normalise_spaces(str(primary_slot.get("direction") or primary_slot.get("direction_hint") or "")).lower()
        if not direction:
            normalized_value = primary_slot.get("normalized_value")
            try:
                direction = "decrease" if normalized_value is not None and float(normalized_value) < 0 else "increase"
            except (TypeError, ValueError):
                direction = "decrease" if growth_value.startswith("-") else "increase"
        direction_word = "감소" if direction == "decrease" else ("성장" if "매출" in metric_label else "증가")
        period_prefix = f"{current_period}년 " if current_period and not current_period.endswith("년") else f"{current_period} " if current_period else ""
        numeric_sentence = _normalise_spaces(
            f"{period_prefix}{metric_label}은 {current_value}으로, {prior_period} 대비 {growth_value} {direction_word}했습니다."
        )
        narrative_sentence, selected_claim_ids = narrative_candidates[0][1], narrative_candidates[0][2]
        if narrative_sentence and not re.search(r"[.!?。]$", narrative_sentence):
            narrative_sentence = f"{narrative_sentence}."
        return {
            "compressed_answer": _normalise_spaces(f"{numeric_sentence} {narrative_sentence}"),
            "selected_claim_ids": selected_claim_ids,
        }

    def _answer_satisfies_growth_narrative_intent(
        self,
        *,
        query: str,
        answer: str,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        query_text = _normalise_spaces(str(query or ""))
        answer_text = _normalise_spaces(str(answer or ""))
        if not query_text or not answer_text or not _query_requests_narrative_context(query_text):
            return False
        if not re.search(r"(성장률|증감률|증가율|전년\s*대비)", query_text):
            return False
        missing_markers = ("확인하지 못", "찾을 수 없", "계산할 수 없습니다", "충분히 확보하지 못", "누락")
        if any(marker in answer_text for marker in missing_markers):
            return False
        if not re.search(r"\d+(?:\.\d+)?\s*%", answer_text):
            return False
        impact_markers = ("영향", "기여", "기인", "개선", "인수", "편입", "성장", "강화", "증가")
        if not any(marker in answer_text for marker in impact_markers):
            return False

        generic_terms = {
            "부문",
            "매출",
            "성장률",
            "계산하고",
            "요약해",
            "영향",
            "실적",
            "전년",
            "대비",
        }
        focus_terms = [
            term
            for term in self._narrative_context_terms(query_text)
            if term not in generic_terms and len(term) >= 2
        ]
        if focus_terms and not any(term.lower() in answer_text.lower() for term in focus_terms):
            return False

        has_growth_row = any(
            self._aggregate_result_operation_family(row) == "growth_rate"
            or "growth" in _normalise_spaces(str(row.get("metric_family") or "")).lower()
            or "성장률" in _normalise_spaces(str(row.get("metric_label") or ""))
            for row in ordered_results or []
        )
        has_narrative_material = any(
            self._aggregate_result_operation_family(row) == "narrative_summary"
            or _normalise_spaces(str(row.get("metric_family") or "")).lower() == "narrative_summary"
            for row in ordered_results or []
        )
        return has_growth_row and has_narrative_material

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
        if not unit_hint:
            return current_unit
        if not current_unit:
            return unit_hint
        normalized_current = _normalise_spaces(current_unit).lower()
        normalized_hint = _normalise_spaces(unit_hint).lower()
        if normalized_current == normalized_hint:
            return current_unit
        bare_numeric = bool(re.fullmatch(r"[\(\)\-]?\d[\d,]*(?:\.\d+)?", str(raw_value or "").strip()))
        if bare_numeric and normalized_current in {"원", "krw"} and normalized_hint in {"천원", "백만원", "억원", "조원"}:
            return unit_hint
        return current_unit

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
        if raw_unit in {"억원", "조원", "원"} or any(unit in raw_value for unit in ("억", "조")):
            target_values.append(float(normalized_value))

        operand_aliases = [
            str(row.get("label") or "").strip(),
            str(row.get("matched_operand_label") or "").strip(),
        ]
        for label_surface in list(operand_aliases):
            for match in re.finditer(r"\(([^)]{2,80})\)", label_surface):
                operand_aliases.append(_normalise_spaces(match.group(1)))
            without_parenthetical = _normalise_spaces(re.sub(r"\([^)]*\)", " ", label_surface))
            if without_parenthetical:
                operand_aliases.append(without_parenthetical)
                stripped_period = _normalise_spaces(
                    re.sub(r"^(?:(?:20\d{2}\s*년?)|(?:제\s*\d+\s*기))(?:\s+|$)", " ", without_parenthetical)
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
                    for cell in list(current_record.get("cells") or []):
                        cell_data = dict(cell or {})
                        if not _is_krw_cell(cell_data):
                            continue
                        return cell_data
                for previous_label in reversed(row_labels[:index]):
                    record = records_by_label.get(previous_label)
                    if not record:
                        continue
                    for cell in list(record.get("cells") or []):
                        cell_data = dict(cell or {})
                        if not _is_krw_cell(cell_data):
                            continue
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

        best_cell: Optional[Dict[str, Any]] = None
        best_normalized: Optional[float] = None
        best_diff: Optional[float] = None
        best_target: Optional[float] = None
        if target_values:
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

        contextual_cell = _cell_from_contextual_note_row() if best_cell is None else None
        if contextual_cell:
            contextual_value, contextual_unit = _normalise_operand_value(
                _normalise_spaces(str(contextual_cell.get("value_text") or "")),
                _normalise_spaces(str(contextual_cell.get("unit_hint") or "")),
            )
            if contextual_value is not None and contextual_unit == "KRW":
                best_cell = contextual_cell
                best_normalized = float(contextual_value)

        if not best_cell or best_normalized is None:
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
                or "비율"
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
        if len(periods) == 1 and re.fullmatch(r"20\d{2}", periods[0]):
            period_prefix = f"{periods[0]}년 "
        if metric_label and rendered_value:
            return f"{period_prefix}{metric_label}은 {rendered_value}입니다."
        return rendered_value or metric_label

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
            left_pair = _first_pair("current_period") or _first_pair("minuend")
            right_pair = _first_pair("prior_period") or _first_pair("subtrahend")
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
            if right_role == "subtrahend" and right_value is not None and float(right_value) < 0:
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
            metadata = dict((item or {}).get("metadata") or {})
            scope = _normalise_spaces(str(metadata.get("consolidation_scope") or "unknown"))
            section_path = _normalise_spaces(str(metadata.get("section_path") or metadata.get("section") or ""))
            if scope == desired_consolidation_scope:
                return False
            if desired_consolidation_scope == "consolidated":
                if scope == "separate":
                    return True
                return bool(section_path and "연결" not in section_path)
            if desired_consolidation_scope == "separate":
                if scope == "consolidated":
                    return True
                return bool("연결" in section_path)
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
                for item in surface_contract_evidence:
                    evidence_id = str(item.get("evidence_id") or "").strip()
                    source_anchor = str(item.get("source_anchor") or "").strip()
                    if any(
                        evidence_id and evidence_id == str(existing.get("evidence_id") or "").strip()
                        or source_anchor and source_anchor == str(existing.get("source_anchor") or "").strip()
                        for existing in evidence_items
                    ):
                        continue
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
        if direct_structured_rows and required_operands:
            direct_structured_rows = [
                row
                for row in direct_structured_rows
                if any(_operand_row_matches_requirement(row, operand) for operand in required_operands)
            ]
        dependency_state = self._dependency_binding_resolution_state(state)
        dependency_rows = list(dependency_state.get("rows") or [])
        dependency_bindings = list(dependency_state.get("bindings") or [])
        dependency_resolved_keys = set(dependency_state.get("resolved_keys") or set())
        retry_strategy = self._active_retry_strategy(state)
        synthesis_only_retry = (
            retry_strategy == "synthesize_from_task_outputs"
            and self._task_prefers_sibling_output_synthesis(state)
        )
        if dependency_rows:
            direct_structured_rows = _merge_operand_rows(
                dependency_rows,
                direct_structured_rows,
                required_operands=required_operands,
            )
            logger.info("[calc_operands] dependency task-output operands=%s", len(dependency_rows))
        dependency_binding_keys = set(dependency_state.get("binding_keys") or set())
        direct_dependency_fill_allowed = operation_family in {"difference", "growth_rate"}
        if dependency_binding_keys and direct_structured_rows:
            duplicate_guard_keys = dependency_resolved_keys
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
        missing_dependency_bindings = list(dependency_state.get("missing_bindings") or [])
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
        allow_dependency_retry_fallback = (
            operation_family in {"ratio", "difference"}
            and bool(missing_dependency_bindings)
            and (
                int(state.get("reconciliation_retry_count") or 0) > 0
                or has_retrieved_docs_for_dependency_fallback
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

        if required_operands and not direct_numeric_grounding:
            deterministic_required_rows = self._build_required_operands_from_candidates(
                evidence_items,
                required_operands=required_operands,
                query=query,
                topic=topic,
                report_scope=report_scope,
            )
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

        structured_llm = self.llm.with_structured_output(OperandExtraction)
        evidence_text = self._format_evidence_for_prompt(evidence_items, evidence_bullets)
        prompt = ChatPromptTemplate.from_template(
            """당신은 재무 계산을 위한 피연산자 추출기입니다.
질문을 풀기 위해 필요한 숫자만 single-shot으로 한 번에 추출하세요.

규칙:
- 여러 번 나눠 찾지 말고, 필요한 피연산자를 한 번의 호출로 모두 찾으세요.
- operand_id는 비워도 됩니다. 코드는 이후에 고유 ID를 부여합니다.
- 각 operand는 반드시 evidence_id와 source_anchor를 포함하세요.
- raw_value는 문서에 있는 숫자 표현 그대로 적으세요. '111조 659억원'처럼 조+억 복합 표기는 절대 억원이나 조원으로 변환하지 말고 원문 그대로 적으세요. 변환하면 반올림 오차가 발생합니다.
- raw_unit은 숫자 바로 옆 단위를 적으세요. 복합 표기('111조 659억원')는 raw_unit을 '억원'으로 적지 말고, raw_value에 원문 전체를 넣고 raw_unit은 '원'으로 적으세요.
- normalized_value와 normalized_unit은 추정해서 채워도 되지만, 이후 코드가 다시 검증합니다.
- 비교/추세 질문은 질문 해결에 꼭 필요한 숫자만 추출하세요.
- source_context와 raw_row_text가 있으면, 해당 표의 헤더와 행을 함께 읽어 period와 숫자 매핑을 복원하세요.
- raw_row_text에 같은 metric의 여러 연도/기간 값이 함께 있으면, 각 연도/기간별 숫자를 별도 operand로 나누어 추출하세요.
- 질문이 단일 비율/비중/이익률 조회라면 피연산자 1개만 추출할 수 있습니다.
- 질문이 두 기간/두 부문/두 비율의 차이·비교·대비·%p 차이를 묻는다면, 절대 단일 비율 피연산자 1개로 축약하지 말고 비교 대상별 피연산자를 각각 추출하세요.
- 질문에 `%p`, `차이`, `비교`, `대비`가 있고 evidence에 동일 metric의 여러 기간/부문 percent 값이 보이면, 해당 percent 값들을 period별/대상별로 각각 별도 operand로 추출하세요.
- 추이(trend) 질문이고 evidence에 3개 이상의 연도/기간 수치가 보이면, 가능한 한 3개 이상 기간의 피연산자를 빠짐없이 추출하세요.
- 문서 메타데이터의 보고서 연도와 표 안에 적힌 비교 기간(예: 2024년, 2023년, 2022년)을 혼동하지 말고, period 필드에는 표에서 읽은 실제 기간을 그대로 적으세요.
- 수치가 없는 descriptive evidence는 operand로 만들지 마세요.

질문: {query}

Structured Evidence:
{evidence}
"""
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
                row["raw_unit"] = self._coerce_operand_unit_from_evidence(
                    raw_value=str(item.raw_value or ""),
                    raw_unit=str(item.raw_unit or ""),
                    evidence_item=evidence_item,
                )
                if evidence_item:
                    metadata = dict(evidence_item.get("metadata") or {})
                    row["statement_type"] = metadata.get("statement_type")
                    row["consolidation_scope"] = metadata.get("consolidation_scope")
                    row["table_source_id"] = metadata.get("table_source_id")
                normalized_value, normalized_unit = _normalise_operand_value(item.raw_value, row["raw_unit"])
                row["operand_id"] = f"op_{index:03d}"
                row["normalized_value"] = normalized_value
                row["normalized_unit"] = normalized_unit
                row = self._refine_operand_precision_from_evidence_table(row, evidence_item)
                operand_rows.append(row)
            if required_operands:
                operand_rows = [
                    row
                    for row in operand_rows
                    if any(_operand_row_matches_requirement(row, operand) for operand in required_operands)
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
                ),
            }

    def _plan_formula_calculation(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Translate normalized operands into an executable calculation plan."""
        runtime_trace = _resolve_runtime_calculation_trace(dict(state))
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
                    calculation_plan=empty_plan,
                    calculation_result={},
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
                    calculation_plan=deterministic_lookup_plan,
                    calculation_result={},
                ),
            }

        deterministic_operation_plan = self._build_deterministic_operation_plan(state, operands)
        if deterministic_operation_plan:
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
                    calculation_plan=deterministic_operation_plan,
                    calculation_result={},
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
                    calculation_plan=guard_plan,
                    calculation_result={},
                ),
            }

        deterministic_plan = self._build_deterministic_ontology_plan(state, operands)
        if deterministic_plan:
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
                    calculation_plan=deterministic_plan,
                    calculation_result={},
                ),
            }
        structured_llm = self.llm.with_structured_output(CalculationPlan)
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
            """당신은 재무 계산 계획기입니다.
질문과 피연산자 목록을 보고 변수 바인딩과 계산식을 작성하세요.

규칙:
- variable_bindings에는 반드시 아래 피연산자 목록의 operand_id만 넣으세요.
- 각 binding의 variable은 A, B, C, D, E, F 중 하나만 사용하세요.
- ordered_operand_ids는 variable_bindings와 같은 순서로 넣으세요.
- operation은 로그/평가용 힌트입니다. subtract, add, ratio, growth_rate, max, min, time_series_trend, none 중 가장 가까운 값을 넣으세요.
- 실제 계산은 formula와 pairwise_formula로 표현합니다.
- formula에는 숫자 상수와 변수(A, B, C...) 그리고 +, -, *, /, **, min(), max(), abs(), round(), log(), exp()만 사용할 수 있습니다.
- mode=single_value 이면 formula로 단일 결과를 계산하세요.
- mode=time_series 이면 variable_bindings를 시계열 순서로 배치하고, formula에는 전체 흐름을 대표하는 계산식(예: ((C - A) / A) * 100)을, pairwise_formula에는 인접 시점 계산식(예: ((CURR - PREV) / PREV) * 100)을 적으세요.
- 최근 3년/연도별/추이 질문처럼 3개 이상 기간 데이터가 있을 때는 mode=time_series 와 operation=time_series_trend 를 우선 사용하세요.
- 이미 계산된 단일 비율/비중/이익률 하나만 답하면 되는 질문이라면 mode=single_value, formula=A 를 사용하세요.
- 질문이 단일 비율/비중/이익률 조회이고 피연산자가 퍼센트 1개뿐이라면 반드시 mode=single_value, formula=A 를 사용하세요.
- 질문이 단일 비율/비중/이익률 조회이고 분자/분모 역할의 금액 피연산자 2개가 있다면 formula는 (A / B) * 100 형태로 작성하세요.
- 두 비율/비중의 차이(%p 차이 포함)를 묻는 질문이라면 mode=single_value 로 두고 formula는 A - B 또는 질문 순서에 맞는 차이식으로 작성하세요. 단일 operand 하나로 끝내지 마세요.
- 증가율/감소율/변화율은 가능한 한 질문에서 기준이 되는 이전 값이 분모가 되도록 식을 작성하세요.
- 현재 피연산자만으로 질문을 풀 수 없으면 억지로 수식을 만들지 말고 status=incomplete, mode=none, operation=none 으로 두고 missing_info에 부족한 정보를 적으세요.
- result_unit은 최종 답변 단위를 적으세요. 예: 억원, 원, %, 개
- ontology_context는 이 질문에 대해 추정된 metric family prior 입니다. 실제 피연산자와 모순되면 ontology_context보다 피연산자를 우선하세요.
- ontology_context에 formula_template과 components가 있으면, 단일 비율 조회는 A 또는 (A / B) * 100, %p 차이는 A - B 같은 계획을 세울 때 참고하세요.

질문: {query}

Ontology Context:
{ontology_context}

사용 가능한 피연산자:
{operands}
"""
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
                    "guard_applied": False,
                    "raw_plan": plan_data,
                },
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_plan=plan_data,
                    calculation_result={},
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
                    calculation_plan=failed_plan,
                    calculation_result={},
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
        scale_by_unit = {
            "원": 1.0,
            "천원": 1_000.0,
            "백만원": 1_000_000.0,
            "억원": 100_000_000.0,
            "조원": 1_000_000_000_000.0,
        }
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
        query_text = _normalise_spaces(
            " ".join(
                str(active_subtask.get(key) or "")
                for key in ("query", "metric_label", "operation_text", "task_id")
            )
        )
        if not (
            any(marker in query_text for marker in ("제외", "실질", "조정"))
            or re.search(r"차감(?!전)", query_text)
        ):
            return ""
        raw_units = [
            _normalise_spaces(str(row.get("raw_unit") or row.get("result_unit") or ""))
            for row in ordered_operands
            if str(row.get("raw_unit") or row.get("result_unit") or "").strip()
        ]
        if not raw_units or len(raw_units) != len(ordered_operands):
            return ""
        if len(set(raw_units)) == 1 and raw_units[0] in {"천원", "백만원"}:
            return raw_units[0]
        source_units = [unit for unit in raw_units if unit in {"천원", "백만원"}]
        if len(set(source_units)) == 1 and any(unit in {"원", "억원", "조원"} for unit in raw_units):
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
        if normalized_unit in {"COUNT", "PERCENT", "%", "퍼센트"} and raw_value:
            if raw_unit and raw_unit in raw_value:
                return raw_value
            return f"{raw_value}{raw_unit}" if raw_unit else raw_value
        if normalized_unit != "KRW" or not raw_value or not raw_unit:
            return ""
        if raw_unit not in {"원", "천원", "백만원", "억원", "조원"}:
            return ""
        if any(token in raw_value for token in ("원", "억", "조", "%")):
            return raw_value
        return f"{raw_value}{raw_unit}"

    def _absolute_display_value(self, value: str) -> str:
        text = str(value or "").strip()
        if text.startswith("-"):
            return text[1:].strip()
        if text.startswith("(") and text.endswith(")"):
            return text[1:-1].strip()
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
            for slot in list(components.get("subtrahend") or []):
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
            replacements = [
                (f"{label} {negative}", f"{label} {positive}"),
                (f"{negative}을 차감", f"{positive}을 차감"),
                (f"{negative}를 차감", f"{positive}를 차감"),
                (f"{negative} 만큼 차감", f"{positive} 만큼 차감"),
                (f"{negative}만큼 차감", f"{positive}만큼 차감"),
            ]
            for source, target in replacements:
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
        scope_text = {"consolidated": "연결기준", "separate": "별도기준"}.get(scope, "")
        prefix_parts = [part for part in (company, f"{period}년" if period and not period.endswith("년") else period, scope_text) if part]
        prefix = " ".join(dict.fromkeys(prefix_parts))

        minuend_label = _normalise_spaces(str(minuend.get("label") or "기준값"))
        subtrahend_label = _normalise_spaces(str(subtrahend.get("label") or "차감값"))
        result_label = _normalise_spaces(str(result_slot.get("label") or calculation_result.get("metric_label") or "계산 결과"))

        if prefix:
            first_sentence = f"{prefix} {minuend_label}은 {minuend_value}입니다."
        else:
            first_sentence = f"{minuend_label}은 {minuend_value}입니다."
        return _normalise_spaces(
            f"{first_sentence} {subtrahend_label} 금액은 {subtrahend_value}이며, 이를 제외한 {result_label}은 {result_value}입니다."
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
        row_ids = [str(item).strip() for item in (source_row_ids or []) if str(item).strip()]
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
        source_row_id = str(row.get("evidence_id") or row.get("row_id") or "")
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
            "source_row_id": source_row_id,
            "source_row_ids": [source_row_id] if source_row_id else [],
            "source_anchor": str(row.get("source_anchor") or ""),
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
        row_ids = [str(item).strip() for item in (source_row_ids or []) if str(item).strip()]
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
            slot = self._build_operand_value_slot(
                row,
                preserve_source_display=family in {"lookup", "single_value"} or preserve_difference_source_display,
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

    def _execute_calculation(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Execute the planned numeric operation and normalize the result."""
        runtime_trace = _resolve_runtime_calculation_trace(dict(state))
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

        def _fail(status: str, reason: str) -> Dict[str, Any]:
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
                ),
            }

        if mode == "none" or not variable_bindings:
            return _fail("insufficient_operands", explanation or "no operation or operands")

        if not ordered_ids:
            ordered_ids = [str(binding.get("operand_id") or "") for binding in variable_bindings]

        ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        if operation_family in {"difference", "growth_rate"} and len(ordered_operands) == 2:
            concept_keys = {
                str(row.get("matched_operand_concept") or "").strip()
                for row in ordered_operands
                if str(row.get("matched_operand_concept") or "").strip()
            }
            if len(concept_keys) == 1:
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
                return {
                    "answer": "",
                    "compressed_answer": "",
                    "selected_claim_ids": selected_evidence_ids,
                    "draft_points": [],
                    "kept_claim_ids": selected_evidence_ids,
                    "dropped_claim_ids": [],
                    "unsupported_sentences": [],
                    "sentence_checks": [],
                    "calculation_result": {
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
                    },
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
        source_row_ids = [
            str(row.get("evidence_id") or "").strip()
            for row in ordered_operands
            if str(row.get("evidence_id") or "").strip()
        ]
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
        result_payload = {
            "answer": "",
            "compressed_answer": "",
            "selected_claim_ids": selected_evidence_ids,
            "draft_points": [],
            "kept_claim_ids": selected_evidence_ids,
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "calculation_result": {
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
            },
        }
        artifacts = list(state.get("artifacts") or [])
        tasks = list(state.get("tasks") or [])
        task_id = str((state.get("active_subtask") or {}).get("task_id") or "calc")
        artifact_id = f"result:{task_id}:{len(artifacts) + 1:03d}"
        calc_result = dict(result_payload.get("calculation_result") or {})
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
                calculation_result=calc_result,
            )
        )
        return result_payload

    def _render_calculation_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        runtime_trace = _resolve_runtime_calculation_trace(dict(state))
        calculation_result = dict(runtime_trace.get("calculation_result") or {})
        plan = dict(runtime_trace.get("calculation_plan") or {})
        operands = list(runtime_trace.get("calculation_operands") or [])
        if not calculation_result:
            return {"answer": "", "compressed_answer": "", "draft_points": []}

        # direction_hint: Python에서 결정론적으로 계산 — LLM에게 부호 판단 위임하지 않음
        operation = str(plan.get("operation") or "")
        result_val = float(calculation_result.get("result_value") or 0)
        if operation == "growth_rate":
            direction_hint = "증가" if result_val > 0 else "감소" if result_val < 0 else "변동 없음"
        elif operation == "subtract":
            direction_hint = "더 큽니다" if result_val > 0 else "더 작습니다" if result_val < 0 else "동일합니다"
        else:
            direction_hint = ""

        # direction_hint가 방향을 표현할 때 rendered_value의 부호는 중복 — 제거
        if direction_hint and result_val < 0:
            rv = str(calculation_result.get("rendered_value") or "")
            calculation_result["rendered_value"] = rv.lstrip("-")

        if str(calculation_result.get("status") or "") != "ok":
            fallback = "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다."
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
                    calculation_result=calculation_result,
                ),
            }

        structured_llm = self.llm.with_structured_output(CalculationRenderOutput)
        prompt = ChatPromptTemplate.from_template(
            """당신은 한국 기업 공시(DART) 계산 결과를 사용자 친화적인 한국어로 렌더링하는 분석가입니다.

[렌더링 규칙]
- CalculationResult의 rendered_value를 그대로 사용하세요. 숫자를 다시 계산하거나 형식을 바꾸지 마세요.
- CalculationResult의 answer_slots가 있으면 rendered_value/series보다 먼저 참고해 현재값, 전기값, 증감값, 주된 결과값을 파악하세요.
- components_by_role에 subtrahend가 있고 그 rendered_value가 음수처럼 보여도, 서술에서는 절댓값을 차감하는 표현을 우선 사용하세요. "-X를 차감"처럼 이중 음수 표현을 만들지 마세요.
- operand label에 포함된 연도·기간 정보(예: '2024년', '2023년', '1분기')는 반드시 그대로 유지하세요. '2024년 영업이익'을 '영업이익'으로 줄이지 마세요.
- direction_hint가 제공된 경우, 그 단어를 그대로 사용하세요. 임의로 '변동', '차이' 등 중립적 표현으로 바꾸지 마세요.
- time_series 해석(상승·하락·반등 등)은 series 또는 derived_metrics의 수치 변화를 근거로 표현하세요.
- 데이터에 없는 새로운 연도, 금액, 비율을 만들지 마세요.
- 질문에 직접 답하는 1~2문장만 작성하세요.

질문:
{query}

Direction Hint (방향 판단 결과, 비어 있으면 무시):
{direction_hint}

CalculationPlan:
{plan_json}

CalculationResult:
{result_json}

Operands:
{operands_json}

반드시 final_answer만 채우세요.
"""
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
                answer = "질문에 필요한 수치를 계산했지만 자연어 답변을 생성하지 못했습니다."

        answer = self._coerce_sign_aware_subtraction_answer(
            answer,
            calculation_result=calculation_result,
        )
        if operation == "ratio" and self._ratio_components_have_suspicious_scale(calculation_result):
            answer = self._compact_ratio_answer(state, calculation_result)

        calculation_result["formatted_result"] = answer
        return {
            "answer": answer,
            "compressed_answer": answer,
            "draft_points": [answer] if answer else [],
            **_runtime_trace_state_update(
                state,
                calculation_result=calculation_result,
            ),
        }

    def _verify_calculation_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Sanity-check that the rendered answer still matches the result."""
        answer = _normalise_spaces(str(state.get("answer") or state.get("compressed_answer") or ""))
        runtime_trace = _resolve_runtime_calculation_trace(dict(state))
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
                **_runtime_trace_state_update(state),
            }

        deterministic_fallback = str(
            calculation_result.get("formatted_result")
            or calculation_result.get("rendered_value")
            or answer
        ).strip()
        rendered_value = str(calculation_result.get("rendered_value") or "").strip()
        operation = str(plan.get("operation") or "")
        result_val = float(calculation_result.get("result_value") or 0)
        if operation == "growth_rate":
            direction_hint = "증가" if result_val > 0 else "감소" if result_val < 0 else "변동 없음"
        elif operation == "subtract":
            direction_hint = "더 큽니다" if result_val > 0 else "더 작습니다" if result_val < 0 else "동일합니다"
        else:
            direction_hint = ""
        structured_llm = self.llm.with_structured_output(CalculationVerificationOutput)
        prompt = ChatPromptTemplate.from_template(
            """당신은 재무 계산 답변 검증기입니다.
사용자에게 내보내기 직전의 계산 답변이 질문, 계산 결과, 피연산자와 모순이 없는지 검토하세요.

규칙:
- 새로운 숫자, 연도, 단위, 근거를 추가하지 마세요.
- 계산 결과와 질문 의도에 맞는다면 verdict=keep.
- 숫자, 단위, 방향, 비교 관계가 어긋나면 verdict=rewrite 로 두고 1~2문장으로 바로잡으세요.
- 답변이 계산 결과와 크게 모순되거나 불필요한 내용을 덧붙였으면 verdict=fallback 으로 두고 deterministic fallback과 같은 뜻으로 작성하세요.
- CalculationResult.answer_slots가 있으면 그 슬롯을 기준으로 답변이 질문 요구사항을 충족하는지 판단하세요.
- final_answer는 rendered_value와 direction_hint를 벗어나지 마세요.
- %p 질문이면 %p를 유지하세요.
- 단일 값 조회 질문이면 계산 과정 설명을 길게 덧붙이지 마세요.

질문:
{query}

현재 답변:
{answer}

Deterministic Fallback:
{fallback}

Direction Hint:
{direction_hint}

CalculationPlan:
{plan_json}

CalculationResult:
{result_json}

Operands:
{operands_json}
"""
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
            if operation == "ratio" and self._ratio_components_have_suspicious_scale(calculation_result):
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
                    calculation_result=calculation_result,
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
        answer_parts = [
            _normalise_spaces(str(row.get("answer") or ""))
            for row in ordered_results
            if _normalise_spaces(str(row.get("answer") or ""))
        ]
        fallback_answer = " ".join(answer_parts).strip() or _normalise_spaces(
            str(state.get("answer") or state.get("compressed_answer") or "")
        )
        fallback_answer = self._preferred_aggregate_fallback_answer(ordered_results, fallback_answer)
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
            structured_llm = self.llm.with_structured_output(AggregateSynthesisOutput)
            prompt = ChatPromptTemplate.from_template(
                """당신은 DART 재무 질의용 최종 synthesizer입니다.
원본 질문과 내부 subtask 결과를 읽고, 사용자에게 보여줄 최종 답변을 작성하세요.

입력 데이터:
1. 원본 질문
2. subtask 결과 목록
3. deterministic structured material check
4. narrative context evidence

규칙:
- 최종 답변은 원본 질문이 명시적으로 요구한 값과 계산 결과를 빠짐없이 포함하도록 노력하세요.
- subtask 결과의 answer, calculation_result.rendered_value, calculation_result.series, calculation_operands를 근거로 사용하세요.
- subtask 결과의 calculation_result.answer_slots가 있으면 그것을 가장 우선적인 structured result contract로 사용하세요.
- narrative context evidence가 있고 원본 질문이 업황/배경/영향 같은 맥락을 요구하면, 최종 답변에 그 맥락을 짧게 반영하세요.
- 새로운 숫자, 연도, 단위를 만들지 마세요.
- deterministic structured material check가 비어 있으면, 현재 재료만으로 원본 질문을 완전히 충족한다고 보고 planner_feedback은 비워 두세요.
- deterministic structured material check가 비어 있지 않으면, 그 누락 재료를 planner_feedback에 반영하세요.
- 현재 재료만으로는 원본 질문의 요구사항 일부를 충족할 수 없다면, planner_feedback에 planner가 추가로 모아야 할 재료를 한 문장으로 적으세요.
- planner_feedback은 내부 시스템용이므로 간결하게, 누락된 값/기간/개념 중심으로 쓰세요.
- final_answer는 사용자용 한국어 답변만 작성하세요.

원본 질문:
{query}

Fallback Answer:
{fallback_answer}

Deterministic Structured Material Check:
{deterministic_feedback}

Narrative Context Evidence:
{narrative_context}

Subtask Results JSON:
{subtask_results_json}
"""
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
            planner_feedback = ""
            deterministic_feedback = ""
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
        if growth_narrative_answer:
            final_answer = _normalise_spaces(str(growth_narrative_answer.get("compressed_answer") or "")) or final_answer
            composition_selected_claim_ids.extend(
                str(claim_id).strip()
                for claim_id in (growth_narrative_answer.get("selected_claim_ids") or [])
                if str(claim_id).strip()
            )
            planner_feedback = ""
            deterministic_feedback = ""
        if entity_table_answer:
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
        if business_focus_answer:
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
            )
        ):
            planner_feedback = ""
            deterministic_feedback = ""
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
        if calculation_projection_override:
            for key in ("calculation_operands", "calculation_plan", "calculation_result"):
                if calculation_projection_override.get(key):
                    aggregate_projection[key] = calculation_projection_override[key]
        slot_based_difference_answer = self._compose_slot_based_difference_answer(
            query=str(state.get("query") or ""),
            report_scope=dict(state.get("report_scope") or {}),
            calculation_result=dict(aggregate_projection.get("calculation_result") or {}),
        )
        if slot_based_difference_answer:
            final_answer = slot_based_difference_answer
            aggregate_projection["calculation_result"]["formatted_result"] = final_answer
        if final_answer and not deterministic_feedback:
            aggregate_projection["calculation_result"]["status"] = "ok"
        artifacts = list(state.get("artifacts") or [])
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
            "artifacts": artifacts,
            "evidence_items": aggregate_evidence_items or aggregate_projection.get("evidence_items", []),
            **_runtime_trace_state_update(
                state,
                calculation_operands=aggregate_projection["calculation_operands"],
                calculation_plan=aggregate_projection["calculation_plan"],
                calculation_result=aggregate_projection["calculation_result"],
            ),
        }

    def _prepare_reflection_retry(self, state: FinancialAgentState) -> Dict[str, Any]:
        current_count = int(state.get("reflection_count") or 0)
        runtime_trace = _resolve_runtime_calculation_trace(dict(state))
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
        if str(active_subtask.get("operation_family") or "").strip().lower() == "narrative_summary":
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
        plan = dict(_resolve_runtime_calculation_trace(dict(state)).get("calculation_plan") or {})
        status = str(plan.get("status") or "ok").lower()
        if status == "incomplete":
            return "reflection_replan"
        return "calculator"

    def _route_after_calculator(self, state: FinancialAgentState) -> str:
        if not self._is_reflection_eligible(state):
            return "calc_render"
        if int(state.get("reflection_count") or 0) >= 1:
            return "calc_render"
        result = dict(_resolve_runtime_calculation_trace(dict(state)).get("calculation_result") or {})
        status = str(result.get("status") or "")
        if status in {"insufficient_operands", "parse_error"}:
            return "reflection_replan"
        return "calc_render"

    def _format_citations(self, state: FinancialAgentState) -> Dict[str, Any]:
        seen = set()
        citations: List[str] = []
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

