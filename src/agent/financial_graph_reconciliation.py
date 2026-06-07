"""
Reconciliation mixin for the financial graph agent.

This module turns retrieved evidence into operand-ready candidate sets:
- build candidate rows/chunks from evidence and retrieved docs
- score and optionally rerank candidates per operand
- decide whether retrieval should retry or calculation can continue
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from src.agent.financial_graph_helpers import *  # noqa: F401,F403
from src.agent.financial_graph_helpers import _coerce_lookup_magnitude_value
from src.agent.financial_graph_models import (
    FinancialAgentState,
    ReconciliationCandidateRerank,
    ReflectionPlanRecord,
    ReflectionQueryPlan,
)
from src.config import get_financial_ontology
from src.config.retrieval_policy import RECONCILIATION_POLICY
from src.schema import ArtifactKind, TaskKind, TaskStatus

logger = logging.getLogger(__name__)

ALLOWED_REFLECTION_RETRY_STRATEGIES = {
    "retry_retrieval",
    "synthesize_from_task_outputs",
    "stop_insufficient",
}


def _normalise_reflection_plan_record(
    plan: Dict[str, Any],
    *,
    fallback_plan: Dict[str, Any],
    missing_info: List[str],
    preferred_sections: List[str],
) -> ReflectionPlanRecord:
    plan_data = dict(plan or {})
    plan_data["missing_info"] = [
        str(item).strip()
        for item in (plan_data.get("missing_info") or [])
        if str(item).strip()
    ]
    plan_data["subqueries"] = [
        _normalise_spaces(str(item))
        for item in (plan_data.get("subqueries") or [])
        if _normalise_spaces(str(item))
    ]
    plan_data["preferred_sections"] = [
        _normalise_spaces(str(item))
        for item in (plan_data.get("preferred_sections") or [])
        if _normalise_spaces(str(item))
    ]
    retry_strategy = _normalise_spaces(str(plan_data.get("retry_strategy") or "")).lower()
    if retry_strategy not in ALLOWED_REFLECTION_RETRY_STRATEGIES:
        retry_strategy = str(fallback_plan.get("retry_strategy") or "retry_retrieval")
    plan_data["retry_strategy"] = retry_strategy
    if not plan_data["missing_info"]:
        plan_data["missing_info"] = list(missing_info)
    if not plan_data["preferred_sections"]:
        plan_data["preferred_sections"] = list(preferred_sections[:3])
    if not plan_data["subqueries"]:
        plan_data = dict(fallback_plan)
        plan_data["explanation"] = "fallback to heuristic because reflection planner returned no subqueries"
    return plan_data


class FinancialAgentReconciliationMixin:
    def _active_subtask_with_sibling_lookup_surfaces(
        self,
        active_subtask: Dict[str, Any],
        state: FinancialAgentState,
    ) -> Dict[str, Any]:
        enriched = dict(active_subtask or {})
        active_task_id = str(enriched.get("task_id") or "").strip()
        surfaces = [
            str(item).strip()
            for item in (enriched.get("sibling_lookup_surfaces") or [])
            if str(item).strip()
        ]
        for task in list(state.get("calc_subtasks") or []):
            current = dict(task or {})
            task_id = str(current.get("task_id") or "").strip()
            if active_task_id and task_id == active_task_id:
                continue
            operation_family = str(current.get("operation_family") or "").strip().lower()
            metric_family = str(current.get("metric_family") or "").strip().lower()
            if operation_family not in {"lookup", "single_value"} and metric_family not in {
                "concept_lookup",
                "concept_single_value",
            }:
                continue
            period_prefix_pattern = str(RECONCILIATION_POLICY.get("lookup_surface_period_prefix_pattern") or "")
            metric_label = (
                re.sub(period_prefix_pattern, "", str(current.get("metric_label") or "").strip())
                if period_prefix_pattern
                else str(current.get("metric_label") or "").strip()
            )
            if metric_label:
                surfaces.append(metric_label)
            for operand in list(current.get("required_operands") or []):
                operand_data = dict(operand or {})
                label = (
                    re.sub(period_prefix_pattern, "", str(operand_data.get("label") or "").strip())
                    if period_prefix_pattern
                    else str(operand_data.get("label") or "").strip()
                )
                if label:
                    surfaces.append(label)
                surfaces.extend(
                    str(alias).strip()
                    for alias in list(operand_data.get("aliases") or [])
                    if str(alias).strip()
                )
        enriched["sibling_lookup_surfaces"] = list(dict.fromkeys(surface for surface in surfaces if surface))
        return enriched

    def _dependency_resolved_reconciliation_result(
        self,
        *,
        active_subtask: Dict[str, Any],
        dependency_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        matched_operands: List[Dict[str, Any]] = []
        for binding in list(dependency_state.get("bindings") or []):
            preferred_task_id = _normalise_spaces(str(binding.get("preferred_task_id") or ""))
            matched_operands.append(
                {
                    "label": _normalise_spaces(str(binding.get("label") or "")),
                    "role": _normalise_spaces(str(binding.get("role") or "")),
                    "concept": _normalise_spaces(str(binding.get("concept") or "")),
                    "matched": True,
                    "candidate_ids": [f"task_output:{preferred_task_id}"] if preferred_task_id else [],
                    "reason": "resolved_from_task_outputs",
                }
            )
        return {
            "status": "ready",
            "task_id": str(active_subtask.get("task_id") or ""),
            "matched_operands": matched_operands,
            "missing_operands": [],
            "retry_queries": [],
            "notes": ["dependency_task_outputs_ready"],
            "retry_strategy": "",
        }

    def _reconciliation_evidence_refs(self, result: Dict[str, Any]) -> List[str]:
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

    def _structured_candidate_unit_hint(
        self,
        *,
        raw_value: str,
        raw_unit: str,
        candidate: Dict[str, Any],
        operand: Dict[str, Any],
        selected_cell: Dict[str, Any],
    ) -> str:
        desired_unit_family = str(operand.get("unit_family") or "").strip().upper()
        policy = dict(RECONCILIATION_POLICY)
        percent_unit = str(policy.get("percent_unit") or "")
        if desired_unit_family == "PERCENT":
            if percent_unit and percent_unit in str(raw_unit or ""):
                return raw_unit
            label_surfaces = " ".join(
                part
                for part in (
                    str(operand.get("label") or "").strip(),
                    " ".join(str(item).strip() for item in (operand.get("aliases") or []) if str(item).strip()),
                    " ".join(str(item).strip() for item in (selected_cell.get("column_headers") or []) if str(item).strip()),
                    str((candidate.get("metadata") or {}).get("semantic_label") or "").strip(),
                    str((candidate.get("metadata") or {}).get("row_label") or "").strip(),
                )
                if part
            )
            if _label_implies_percent_metric(label_surfaces):
                return percent_unit
        candidate_metadata = dict(candidate.get("metadata") or {})
        statement_type = str(candidate_metadata.get("statement_type") or "").strip().lower()
        current_unit = str(raw_unit or "").strip()
        ambiguous_units = {str(item) for item in (policy.get("ambiguous_krw_units") or ())}
        note_statement_type = str(policy.get("note_statement_type") or "")
        if current_unit in ambiguous_units:
            resolved_local_unit = _resolve_candidate_local_unit_hint(candidate, raw_value)
            if resolved_local_unit and (current_unit == "" or statement_type == note_statement_type):
                return resolved_local_unit
        return raw_unit

    def _fallback_period_text_for_operand(self, operand: Dict[str, Any], query_years: List[int]) -> str:
        period_focus = str(operand.get("_effective_period_focus") or "").strip()
        role = str(operand.get("role") or "").strip()
        if query_years and (role == "current_period" or period_focus == "current"):
            return str(max(query_years))
        if query_years and (role == "prior_period" or period_focus == "prior"):
            ordered_years = sorted({int(year) for year in query_years}, reverse=True)
            if len(ordered_years) >= 2:
                return str(ordered_years[1])
            return str(ordered_years[0] - 1)
        return str(operand.get("period_hint") or "").strip()

    def _structured_cell_identity(self, cell: Dict[str, Any]) -> str:
        value_id = str(cell.get("value_id") or "").strip()
        if value_id:
            return value_id
        row_index = str(cell.get("row_index") or "").strip()
        column_index = str(cell.get("column_index") or "").strip()
        if row_index or column_index:
            return f"{row_index}:{column_index}"
        header_key = "|".join(str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip())
        return f"{header_key}|{str(cell.get('value_text') or '').strip()}"

    def _resolved_period_text_for_operand(
        self,
        *,
        operand: Dict[str, Any],
        cell: Dict[str, Any],
        query_years: List[int],
        period_focus: str,
    ) -> str:
        effective_period_focus = _operand_period_focus(operand, period_focus)
        operand_with_period_focus = {**operand, "_effective_period_focus": effective_period_focus}
        period = _structured_cell_period_text(cell, query_years, effective_period_focus)
        period_presence_pattern = str(RECONCILIATION_POLICY.get("period_presence_pattern") or "")
        if period_presence_pattern and not re.search(period_presence_pattern, period):
            report_year: Optional[int] = None
            for raw_year in (cell.get("_report_year"), cell.get("report_year"), cell.get("year")):
                try:
                    if raw_year not in (None, ""):
                        report_year = int(raw_year)
                        break
                except (TypeError, ValueError):
                    continue
            target_years = _operand_target_years(operand, query_years)
            if report_year is not None and target_years and report_year in target_years:
                period = str(report_year)
            elif report_year is not None:
                period = str(report_year)
            else:
                period = self._fallback_period_text_for_operand(operand_with_period_focus, query_years)
        return period

    def _pair_candidate_period_score(
        self,
        *,
        candidate: Dict[str, Any],
        cell: Dict[str, Any],
        operand: Dict[str, Any],
        preferred_statement_types: List[str],
        constraints: Dict[str, Any],
        query_years: List[int],
        period_focus: str,
        report_scope: Optional[Dict[str, Any]] = None,
    ) -> tuple[float, str]:
        candidate_score = _score_operand_candidate(
            candidate,
            operand=operand,
            preferred_statement_types=preferred_statement_types,
            constraints=constraints,
            query_years=query_years,
            report_scope=report_scope,
        )
        cell_score = _score_structured_cell(
            cell,
            query_years=_operand_target_years(operand, query_years),
            period_focus=_operand_period_focus(operand, period_focus),
            operand=operand,
        )
        period = self._resolved_period_text_for_operand(
            operand=operand,
            cell=cell,
            query_years=query_years,
            period_focus=period_focus,
        )
        return candidate_score + cell_score, period

    def _find_reconciliation_match_entry(
        self,
        reconciliation_result: Dict[str, Any],
        operand: Dict[str, Any],
    ) -> Dict[str, Any]:
        label = str(operand.get("label") or "").strip()
        role = str(operand.get("role") or "").strip()
        rows = [
            dict(item)
            for item in (reconciliation_result.get("matched_operands") or [])
            if str(item.get("label") or "").strip() == label
        ]
        if role:
            exact = next((row for row in rows if str(row.get("role") or "").strip() == role), None)
            if exact:
                return exact
        return rows[0] if rows else {}

    def _build_operand_row_from_candidate_cell(
        self,
        *,
        candidate: Dict[str, Any],
        selected_cell: Dict[str, Any],
        operand: Dict[str, Any],
        index: int,
        period_focus: str,
        query_years: List[int],
    ) -> Optional[Dict[str, Any]]:
        metadata = dict(candidate.get("metadata") or {})
        raw_value = str(selected_cell.get("value_text") or "").strip()
        raw_unit = str(selected_cell.get("unit_hint") or metadata.get("unit_hint") or "").strip()
        raw_unit = self._structured_candidate_unit_hint(
            raw_value=raw_value,
            raw_unit=raw_unit,
            candidate=candidate,
            operand=operand,
            selected_cell=selected_cell,
        )
        normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
        normalized_value = _coerce_lookup_magnitude_value(
            normalized_value=normalized_value,
            normalized_unit=normalized_unit,
            raw_value=raw_value,
            concept=str(operand.get("concept") or ""),
            statement_type=str(metadata.get("statement_type") or ""),
            row_label=str(metadata.get("row_label") or ""),
            semantic_label=str(metadata.get("semantic_label") or ""),
        )
        if normalized_value is None:
            return None
        period = self._resolved_period_text_for_operand(
            operand=operand,
            cell=selected_cell,
            query_years=query_years,
            period_focus=period_focus,
        )
        row_label = str(operand.get("label") or metadata.get("semantic_label") or metadata.get("row_label") or "").strip()
        return {
            "operand_id": f"op_{index:03d}",
            "evidence_id": str(candidate.get("candidate_id") or ""),
            "source_anchor": candidate.get("source_anchor"),
            "label": f"{period} {row_label}".strip(),
            "raw_value": raw_value,
            "raw_unit": raw_unit,
            "normalized_value": normalized_value,
            "normalized_unit": normalized_unit,
            "period": period,
            "table_source_id": metadata.get("table_source_id"),
            "statement_type": metadata.get("statement_type"),
            "consolidation_scope": metadata.get("consolidation_scope"),
            "matched_operand_label": str(operand.get("label") or "").strip(),
            "matched_operand_concept": str(operand.get("concept") or "").strip(),
            "matched_operand_role": str(operand.get("role") or "").strip(),
        }

    def _effective_structured_cell_unit_hint(
        self,
        *,
        candidate: Dict[str, Any],
        selected_cell: Dict[str, Any],
        operand: Dict[str, Any],
    ) -> str:
        metadata = dict(candidate.get("metadata") or {})
        raw_value = str(selected_cell.get("value_text") or "").strip()
        raw_unit = str(selected_cell.get("unit_hint") or metadata.get("unit_hint") or "").strip()
        return self._structured_candidate_unit_hint(
            raw_value=raw_value,
            raw_unit=raw_unit,
            candidate=candidate,
            operand=operand,
            selected_cell=selected_cell,
        )

    def _repair_note_operand_units_from_same_block(
        self,
        operand_rows: List[Dict[str, Any]],
        candidate_map: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if len(operand_rows) < 2:
            return operand_rows

        ambiguous_units = {str(item) for item in (RECONCILIATION_POLICY.get("ambiguous_krw_units") or ())}
        note_statement_type = str(RECONCILIATION_POLICY.get("note_statement_type") or "")
        rows = [dict(row) for row in operand_rows]
        block_groups: Dict[str, List[Dict[str, Any]]] = {}

        for row in rows:
            if str(row.get("statement_type") or "").strip().lower() != note_statement_type:
                continue
            evidence_id = str(row.get("evidence_id") or "").strip()
            candidate = candidate_map.get(evidence_id) or {}
            block_key = _candidate_row_block_signature(candidate)
            if not block_key:
                continue
            block_groups.setdefault(block_key, []).append(row)

        for block_rows in block_groups.values():
            resolved_units = list(
                dict.fromkeys(
                    str(row.get("raw_unit") or "").strip()
                    for row in block_rows
                    if str(row.get("raw_unit") or "").strip() not in ambiguous_units
                )
            )
            if len(resolved_units) != 1:
                continue
            inherited_unit = resolved_units[0]
            for row in block_rows:
                current_unit = str(row.get("raw_unit") or "").strip()
                if current_unit not in ambiguous_units:
                    continue
                normalized_value, normalized_unit = _normalise_operand_value(
                    str(row.get("raw_value") or "").strip(),
                    inherited_unit,
                )
                normalized_value = _coerce_lookup_magnitude_value(
                    normalized_value=normalized_value,
                    normalized_unit=normalized_unit,
                    raw_value=str(row.get("raw_value") or "").strip(),
                    concept=str(row.get("matched_operand_concept") or ""),
                    statement_type=str(row.get("statement_type") or ""),
                    row_label=str(row.get("matched_operand_label") or ""),
                    semantic_label=str(row.get("matched_operand_label") or ""),
                )
                if normalized_value is None:
                    continue
                row["raw_unit"] = inherited_unit
                row["normalized_value"] = normalized_value
                row["normalized_unit"] = normalized_unit

        return rows

    def _expand_structured_candidate_ids(
        self,
        candidate_ids: List[str],
        candidate_map: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        expanded: List[str] = []
        seen: set[str] = set()
        for raw_candidate_id in candidate_ids:
            cleaned = str(raw_candidate_id).strip()
            if not cleaned:
                continue
            for current_id in (cleaned, f"{cleaned}::raw_row"):
                if current_id in seen or current_id not in candidate_map:
                    continue
                seen.add(current_id)
                expanded.append(current_id)
        return expanded

    def _structured_candidate_from_id(
        self,
        candidate_id: str,
        candidate_map: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        candidate = dict(candidate_map.get(str(candidate_id).strip()) or {})
        if not candidate:
            return None
        metadata = dict(candidate.get("metadata") or {})
        candidate_kind = str(candidate.get("candidate_kind") or "").strip()
        if candidate_kind == "evidence_row" and str(metadata.get("row_text") or "").strip():
            candidate["candidate_kind"] = "table_row"
        return candidate

    def _extract_structured_period_pair_rows(
        self,
        *,
        required_operands: List[Dict[str, Any]],
        reconciliation_result: Dict[str, Any],
        candidate_map: Dict[str, Dict[str, Any]],
        preferred_statement_types: List[str],
        constraints: Dict[str, Any],
        query_years: List[int],
        start_index: int,
        operation_family: str,
        report_scope: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[Dict[str, Any]], set[tuple[str, str]]]:
        period_focus = str(constraints.get("period_focus") or "unknown").strip()
        grouped: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for operand in required_operands:
            role = str(operand.get("role") or "").strip()
            if role not in {"current_period", "prior_period"}:
                continue
            concept = str(operand.get("concept") or "").strip()
            label = str(operand.get("label") or "").strip()
            group_key = concept or label
            grouped.setdefault(group_key, {})[role] = dict(operand)

        rows: List[Dict[str, Any]] = []
        handled: set[tuple[str, str]] = set()
        next_index = start_index

        for members in grouped.values():
            current_operand = members.get("current_period")
            prior_operand = members.get("prior_period")
            if not current_operand or not prior_operand:
                continue
            current_match = self._find_reconciliation_match_entry(reconciliation_result, current_operand)
            prior_match = self._find_reconciliation_match_entry(reconciliation_result, prior_operand)
            candidate_ids: List[str] = []
            for match_entry in (current_match, prior_match):
                for candidate_id in (match_entry.get("candidate_ids") or []):
                    cleaned = str(candidate_id).strip()
                    if cleaned and cleaned not in candidate_ids:
                        candidate_ids.append(cleaned)
            candidate_ids = self._expand_structured_candidate_ids(candidate_ids, candidate_map)
            structured_candidates: List[Dict[str, Any]] = []
            for candidate_id in candidate_ids:
                current_candidate = self._structured_candidate_from_id(candidate_id, candidate_map)
                if not current_candidate:
                    continue
                if str(current_candidate.get("candidate_kind") or "") not in {
                    "structured_value",
                    "structured_row",
                    "structured_column_value",
                    "table_row",
                    "evidence_row",
                }:
                    continue
                structured_candidates.append(current_candidate)
            best_pair: Optional[tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = None
            best_cross_pair: Optional[tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = None
            best_score = float("-inf")
            current_entries: List[tuple[Dict[str, Any], Dict[str, Any], str, float]] = []
            prior_entries: List[tuple[Dict[str, Any], Dict[str, Any], str, float]] = []
            for candidate in structured_candidates:
                metadata = dict(candidate.get("metadata") or {})
                cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
                if not cells and str(candidate.get("candidate_kind") or "") in {"table_row", "evidence_row"}:
                    cells = _parse_unstructured_table_row_cells(str(metadata.get("row_text") or ""), metadata)
                if not cells:
                    continue
                enriched_cells: List[Dict[str, Any]] = []
                for cell in cells:
                    enriched = dict(cell)
                    enriched["_sibling_cells"] = [dict(item) for item in cells]
                    enriched["_report_year"] = metadata.get("year")
                    enriched_cells.append(enriched)
                accepted_current_entries: List[tuple[Dict[str, Any], str, float]] = []
                accepted_prior_entries: List[tuple[Dict[str, Any], str, float]] = []
                for cell in enriched_cells:
                    if _candidate_satisfies_direct_acceptance_contract(
                        candidate,
                        operand=current_operand,
                        constraints=constraints,
                        query_years=query_years,
                        operation_family=operation_family,
                        selected_cell=cell,
                        report_scope=report_scope,
                    ):
                        current_score, current_period = self._pair_candidate_period_score(
                            candidate=candidate,
                            cell=cell,
                            operand=current_operand,
                            preferred_statement_types=preferred_statement_types,
                            constraints=constraints,
                            query_years=query_years,
                            period_focus=period_focus,
                            report_scope=report_scope,
                        )
                        accepted_current_entries.append((cell, current_period, current_score))
                        current_entries.append((candidate, cell, current_period, current_score))
                    if _candidate_satisfies_direct_acceptance_contract(
                        candidate,
                        operand=prior_operand,
                        constraints=constraints,
                        query_years=query_years,
                        operation_family=operation_family,
                        selected_cell=cell,
                        report_scope=report_scope,
                    ):
                        prior_score, prior_period = self._pair_candidate_period_score(
                            candidate=candidate,
                            cell=cell,
                            operand=prior_operand,
                            preferred_statement_types=preferred_statement_types,
                            constraints=constraints,
                            query_years=query_years,
                            period_focus=period_focus,
                            report_scope=report_scope,
                        )
                        accepted_prior_entries.append((cell, prior_period, prior_score))
                        prior_entries.append((candidate, cell, prior_period, prior_score))

                for current_cell, current_period, current_score in accepted_current_entries:
                    current_identity = self._structured_cell_identity(current_cell)
                    for prior_cell, prior_period, prior_score in accepted_prior_entries:
                        if current_identity == self._structured_cell_identity(prior_cell):
                            continue
                        if current_period and prior_period and current_period == prior_period:
                            continue
                        pair_score = current_score + prior_score + 4.0
                        if current_period and prior_period and current_period != prior_period:
                            pair_score += 2.0
                        if str(metadata.get("table_source_id") or "").strip():
                            pair_score += 0.75
                        if pair_score > best_score:
                            best_score = pair_score
                            best_pair = (candidate, current_cell, prior_cell)

            if not best_pair and current_entries and prior_entries:
                for current_candidate, current_cell, current_period, current_score in current_entries:
                    current_metadata = dict(current_candidate.get("metadata") or {})
                    current_table_id = str(current_metadata.get("table_source_id") or "").strip()
                    for prior_candidate, prior_cell, prior_period, prior_score in prior_entries:
                        if self._structured_cell_identity(current_cell) == self._structured_cell_identity(prior_cell):
                            continue
                        prior_metadata = dict(prior_candidate.get("metadata") or {})
                        prior_table_id = str(prior_metadata.get("table_source_id") or "").strip()
                        if not current_table_id or current_table_id != prior_table_id:
                            continue
                        if current_period and prior_period and current_period == prior_period:
                            continue
                        pair_score = current_score + prior_score + 3.0
                        if current_table_id:
                            pair_score += 1.5
                        if pair_score > best_score:
                            best_score = pair_score
                            best_cross_pair = (current_candidate, current_cell, prior_candidate, prior_cell)

            if not best_pair and not best_cross_pair:
                continue
            if best_pair:
                pair_candidate, current_cell, prior_cell = best_pair
                current_candidate = pair_candidate
                prior_candidate = pair_candidate
            else:
                current_candidate, current_cell, prior_candidate, prior_cell = best_cross_pair
            current_unit_hint = self._effective_structured_cell_unit_hint(
                candidate=current_candidate,
                selected_cell=current_cell,
                operand=current_operand,
            )
            prior_unit_hint = self._effective_structured_cell_unit_hint(
                candidate=prior_candidate,
                selected_cell=prior_cell,
                operand=prior_operand,
            )
            if current_unit_hint and not prior_unit_hint:
                prior_cell = {**prior_cell, "unit_hint": current_unit_hint}
            elif prior_unit_hint and not current_unit_hint:
                current_cell = {**current_cell, "unit_hint": prior_unit_hint}
            current_row = self._build_operand_row_from_candidate_cell(
                candidate=current_candidate,
                selected_cell=current_cell,
                operand=current_operand,
                index=next_index,
                period_focus=period_focus,
                query_years=query_years,
            )
            prior_row = self._build_operand_row_from_candidate_cell(
                candidate=prior_candidate,
                selected_cell=prior_cell,
                operand=prior_operand,
                index=next_index + 1,
                period_focus=period_focus,
                query_years=query_years,
            )
            if not current_row or not prior_row:
                continue
            rows.extend([current_row, prior_row])
            handled.add((str(current_operand.get("label") or "").strip(), "current_period"))
            handled.add((str(prior_operand.get("label") or "").strip(), "prior_period"))
            next_index += 2

        return rows, handled

    def _build_reconciliation_candidates(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        """Build a mixed candidate pool from evidence items and retrieved docs.

        The pool intentionally includes both coarse chunks and more structured
        row-level candidates so later scoring can prefer precise numeric rows
        without losing narrative fallback context.
        """
        candidates: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for item in list(state.get("evidence_items", []) or []):
            evidence_id = str(item.get("evidence_id") or "").strip()
            anchor = str(item.get("source_anchor") or "").strip()
            candidate_id = evidence_id or anchor
            if not candidate_id or candidate_id in seen:
                continue
            seen.add(candidate_id)
            text = " ".join(
                [
                    str(item.get("claim") or ""),
                    str(item.get("quote_span") or ""),
                    str(item.get("source_context") or ""),
                    str(item.get("raw_row_text") or ""),
                    anchor,
                ]
            )
            candidates.append(
                _build_reconciliation_candidate(
                    candidate_id=candidate_id,
                    anchor=anchor,
                    text=text,
                    metadata=dict(item.get("metadata") or {}),
                )
            )
            raw_row_text = _normalise_spaces(str(item.get("raw_row_text") or ""))
            if raw_row_text:
                row_candidate = _build_reconciliation_candidate(
                    candidate_id=f"{candidate_id}::raw_row",
                    anchor=anchor,
                    text=" ".join(
                        part
                        for part in (
                            raw_row_text,
                            str(item.get("source_context") or ""),
                            str(item.get("claim") or ""),
                            anchor,
                        )
                        if part
                    ),
                    metadata={**dict(item.get("metadata") or {}), "row_text": raw_row_text},
                    candidate_kind="evidence_row",
                    row_label=_extract_table_row_label(raw_row_text),
                )
                row_candidate_id = str(row_candidate.get("candidate_id") or "").strip()
                if row_candidate_id and row_candidate_id not in seen:
                    seen.add(row_candidate_id)
                    candidates.append(row_candidate)

        doc_stream: List[tuple[Any, Any]] = []
        for item in list(state.get("retrieved_docs", []) or []):
            doc_stream.append(item)
        for item in list(state.get("seed_retrieved_docs", []) or []):
            doc_stream.append(item)

        for index, (doc, _score) in enumerate(doc_stream, start=1):
            metadata = dict(doc.metadata or {})
            anchor = self._build_source_anchor(metadata)
            candidate_id = str(metadata.get("chunk_uid") or f"doc_{index}")
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            text = " ".join(
                [
                    str(doc.page_content or ""),
                    str(metadata.get("table_header_context") or ""),
                    str(metadata.get("section_path") or metadata.get("section") or ""),
                    anchor,
                ]
            )
            candidates.append(
                _build_reconciliation_candidate(
                    candidate_id=candidate_id,
                    anchor=anchor,
                    text=text,
                    metadata=metadata,
                )
            )
            for row_candidate in _build_table_row_reconciliation_candidates(
                candidate_id_prefix=candidate_id,
                anchor=anchor,
                table_text=str(doc.page_content or ""),
                metadata=metadata,
            ):
                row_candidate_id = str(row_candidate.get("candidate_id") or "").strip()
                if not row_candidate_id or row_candidate_id in seen:
                    continue
                seen.add(row_candidate_id)
                candidates.append(row_candidate)
        return candidates

    def _should_llm_rerank_candidates(
        self,
        scored_candidates: List[Dict[str, Any]],
    ) -> bool:
        """Escalate only ambiguous top candidates to the LLM reranker."""
        if len(scored_candidates) < 2:
            return False

        top = scored_candidates[0]
        second = scored_candidates[1]
        top_candidate = dict(top.get("candidate") or {})
        top_kind = str(top_candidate.get("candidate_kind") or "")
        score_gap = float(top.get("score") or 0.0) - float(second.get("score") or 0.0)
        top_kinds = {
            str(item.get("candidate", {}).get("candidate_kind") or "")
            for item in scored_candidates[:5]
        }

        if _candidate_is_descriptor_row(top_candidate):
            return True
        if top_kind == "chunk":
            return True
        if score_gap < 1.0:
            return True
        if "chunk" in top_kinds and any(
            kind in {"structured_value", "structured_row", "structured_column_value", "table_row", "evidence_row"}
            for kind in top_kinds
        ):
            return True
        return False

    def _llm_rerank_operand_candidates(
        self,
        *,
        query: str,
        operand: Dict[str, Any],
        scored_candidates: List[Dict[str, Any]],
    ) -> List[str]:
        top_candidates = scored_candidates[: min(5, len(scored_candidates))]
        if len(top_candidates) < 2:
            return [
                str(item.get("candidate", {}).get("candidate_id") or "").strip()
                for item in top_candidates
                if str(item.get("candidate", {}).get("candidate_id") or "").strip()
            ]

        option_lines: List[str] = []
        allowed_ids: List[str] = []
        for rank, item in enumerate(top_candidates, start=1):
            candidate = dict(item.get("candidate") or {})
            metadata = dict(candidate.get("metadata") or {})
            candidate_id = str(candidate.get("candidate_id") or "").strip()
            if not candidate_id:
                continue
            allowed_ids.append(candidate_id)
            preview = _normalise_spaces(
                str(metadata.get("row_text") or metadata.get("table_header_context") or candidate.get("text") or "")
            )[:280]
            option_lines.append(
                "\n".join(
                    [
                        f"[candidate {rank}]",
                        f"id: {candidate_id}",
                        f"kind: {candidate.get('candidate_kind')}",
                        f"section: {metadata.get('section_path') or metadata.get('section') or ''}",
                        f"statement_type: {metadata.get('statement_type') or ''}",
                        f"consolidation_scope: {metadata.get('consolidation_scope') or ''}",
                        f"row_label: {metadata.get('row_label') or ''}",
                        f"preview: {preview}",
                    ]
                )
            )

        if len(allowed_ids) < 2:
            return allowed_ids

        structured_llm = self._llm_for_phase("reconciliation_rerank").with_structured_output(ReconciliationCandidateRerank)
        prompt = ChatPromptTemplate.from_template(
            str(RECONCILIATION_POLICY.get("candidate_rerank_prompt_template") or "")
        )
        try:
            reranked: ReconciliationCandidateRerank = (prompt | structured_llm).invoke(
                {
                    "query": query,
                    "operand_label": str(operand.get("label") or ""),
                    "options": "\n\n".join(option_lines),
                }
            )
        except Exception as exc:
            logger.info("[reconcile] llm rerank skipped operand=%s error=%s", operand.get("label"), exc)
            return allowed_ids

        ordered_ids: List[str] = []
        seen: set[str] = set()
        for candidate_id in reranked.ordered_candidate_ids:
            cleaned = str(candidate_id or "").strip()
            if cleaned and cleaned in allowed_ids and cleaned not in seen:
                seen.add(cleaned)
                ordered_ids.append(cleaned)
        for candidate_id in allowed_ids:
            if candidate_id not in seen:
                ordered_ids.append(candidate_id)
        return ordered_ids

    def _rerank_reconciliation_matches_with_llm(
        self,
        state: FinancialAgentState,
        result: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        years: List[int],
    ) -> Dict[str, Any]:
        active_subtask = self._active_subtask_with_sibling_lookup_surfaces(
            dict(state.get("active_subtask") or {}),
            state,
        )
        query = str(active_subtask.get("query") or state.get("query") or "")
        operand_specs = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if str(item.get("label") or "").strip()
        ]
        preferred_statement_types = [
            str(item).strip()
            for item in (active_subtask.get("preferred_statement_types") or [])
            if str(item).strip()
        ]
        constraints = dict(active_subtask.get("constraints") or {})
        report_scope = dict(state.get("report_scope") or {})

        updated = dict(result or {})
        notes = [str(item).strip() for item in (updated.get("notes") or []) if str(item).strip()]
        reranked_rows: List[Dict[str, Any]] = []

        for row in (updated.get("matched_operands") or []):
            current = dict(row)
            label = str(current.get("label") or "").strip()
            role = str(current.get("role") or "").strip()
            operand = next(
                (
                    item
                    for item in operand_specs
                    if str(item.get("label") or "").strip() == label
                    and (not role or str(item.get("role") or "").strip() == role)
                ),
                None,
            )
            if operand is None:
                operand = next(
                    (item for item in operand_specs if str(item.get("label") or "").strip() == label),
                    None,
                )
            if not operand:
                reranked_rows.append(current)
                continue

            operand_role = str(operand.get("role") or "").strip()
            if operand_role in {"current_period", "prior_period"}:
                reranked_rows.append(current)
                continue
            if str(active_subtask.get("operation_family") or "").strip().lower() in {"ratio", "sum"} and str(operand.get("concept") or "").strip():
                reranked_rows.append(current)
                continue

            matches = [candidate for candidate in candidates if _candidate_matches_operand(candidate, operand)]
            scored_candidates = [
                {
                    "candidate": candidate,
                    "score": _score_operand_candidate(
                        candidate,
                        operand=operand,
                        preferred_statement_types=preferred_statement_types,
                        constraints=constraints,
                        query_years=years,
                        report_scope=report_scope,
                    ),
                }
                for candidate in matches
            ]
            scored_candidates.sort(key=lambda item: item["score"], reverse=True)
            if not self._should_llm_rerank_candidates(scored_candidates):
                reranked_rows.append(current)
                continue

            ordered_ids = self._llm_rerank_operand_candidates(
                query=query,
                operand=operand,
                scored_candidates=scored_candidates,
            )
            if ordered_ids:
                current["candidate_ids"] = ordered_ids
                notes.append(f"llm_rerank:{label}")
            reranked_rows.append(current)

        updated["matched_operands"] = reranked_rows
        updated["notes"] = list(dict.fromkeys(notes))
        return updated

    def _evidence_items_from_reconciliation_matches(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        reconciliation_result = dict(state.get("reconciliation_result") or {})
        if str(reconciliation_result.get("status") or "") not in {"ready", "retry_retrieval", "insufficient_operands"}:
            return []

        active_subtask = self._active_subtask_with_sibling_lookup_surfaces(
            dict(state.get("active_subtask") or {}),
            state,
        )
        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        operand_map = {
            (
                str(item.get("label") or "").strip(),
                str(item.get("role") or "").strip(),
            ): item
            for item in required_operands
            if str(item.get("label") or "").strip()
        }
        constraints = dict(active_subtask.get("constraints") or {})
        query_years = _query_years_from_state(state)
        report_scope = dict(state.get("report_scope") or {})
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        candidate_map = {
            str(candidate.get("candidate_id") or "").strip(): candidate
            for candidate in self._build_reconciliation_candidates(state)
            if str(candidate.get("candidate_id") or "").strip()
        }
        items: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for operand_match in (reconciliation_result.get("matched_operands") or []):
            operand = (
                operand_map.get((str(operand_match.get("label") or "").strip(), str(operand_match.get("role") or "").strip()))
                or operand_map.get((str(operand_match.get("label") or "").strip(), ""))
                or {}
            )
            for candidate_id in (operand_match.get("candidate_ids") or [])[:2]:
                current = candidate_map.get(str(candidate_id).strip())
                if not current:
                    continue
                if operand and not _candidate_is_direct_grounding_candidate(
                    current,
                    operand=operand,
                    constraints=constraints,
                    query_years=query_years,
                    report_scope=report_scope,
                ):
                    continue
                evidence_id = f"recon::{candidate_id}"
                if evidence_id in seen:
                    continue
                seen.add(evidence_id)
                metadata = dict(current.get("metadata") or {})
                raw_row_text = _normalise_spaces(str(metadata.get("row_text") or ""))
                if not raw_row_text and str(current.get("candidate_kind") or "") in {"structured_value", "structured_row", "structured_column_value"}:
                    row_label = str(metadata.get("row_label") or "").strip()
                    values = [
                        str(cell.get("value_text") or "").strip()
                        for cell in (metadata.get("structured_cells") or [])
                        if str(cell.get("value_text") or "").strip()
                    ]
                    raw_row_text = " | ".join([part for part in [row_label, *values] if part])
                claim = _normalise_spaces(raw_row_text or str(current.get("text") or ""))
                quote_span = _normalise_spaces(str(raw_row_text or current.get("text") or ""))[:240]
                items.append(
                    {
                        "evidence_id": evidence_id,
                        "source_anchor": str(current.get("source_anchor") or "").strip(),
                        "claim": claim[:1200],
                        "quote_span": quote_span,
                        "support_level": "direct",
                        "question_relevance": "high",
                        "allowed_terms": [],
                        "source_context": str(metadata.get("table_header_context") or metadata.get("section_path") or "").strip(),
                        "raw_row_text": raw_row_text or None,
                        "metadata": metadata,
                    }
                )
        return items

    def _extract_structured_operands_from_reconciliation(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        reconciliation_result = dict(state.get("reconciliation_result") or {})
        if str(reconciliation_result.get("status") or "") != "ready":
            return []

        active_subtask = self._active_subtask_with_sibling_lookup_surfaces(
            dict(state.get("active_subtask") or {}),
            state,
        )
        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        if not required_operands:
            return []

        constraints = dict(active_subtask.get("constraints") or {})
        preferred_statement_types = [
            str(item).strip()
            for item in (active_subtask.get("preferred_statement_types") or [])
            if str(item).strip()
        ]
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        if operation_family == "ratio":
            required_operands = sorted(
                required_operands,
                key=lambda item: (
                    0
                    if str(item.get("role") or "").strip().startswith("numerator")
                    else 1
                    if str(item.get("role") or "").strip().startswith("denominator")
                    else 2,
                    str(item.get("role") or "").strip(),
                    str(item.get("label") or "").strip(),
                ),
            )
        period_focus = str(constraints.get("period_focus") or "unknown").strip()
        query_years = _query_years_from_state(state)
        report_scope = dict(state.get("report_scope") or {})
        candidates = self._build_reconciliation_candidates(state)
        candidate_map = {
            str(candidate.get("candidate_id") or "").strip(): candidate
            for candidate in candidates
            if str(candidate.get("candidate_id") or "").strip()
        }

        match_map = {
            (
                str(item.get("label") or "").strip(),
                str(item.get("role") or "").strip(),
            ): dict(item)
            for item in (reconciliation_result.get("matched_operands") or [])
            if str(item.get("label") or "").strip()
        }

        operand_rows: List[Dict[str, Any]] = []
        paired_rows, handled_operands = self._extract_structured_period_pair_rows(
            required_operands=required_operands,
            reconciliation_result=reconciliation_result,
            candidate_map=candidate_map,
            preferred_statement_types=preferred_statement_types,
            constraints=constraints,
            query_years=query_years,
            start_index=1,
            operation_family=operation_family,
            report_scope=report_scope,
        )
        operand_rows.extend(paired_rows)
        next_index = len(operand_rows) + 1
        for index, operand in enumerate(required_operands, start=1):
            label = str(operand.get("label") or "").strip()
            if not label:
                continue
            role = str(operand.get("role") or "").strip()
            if (label, role) in handled_operands:
                continue
            match_entry = match_map.get((label, role)) or match_map.get((label, "")) or {}
            candidate_ids = [
                str(value).strip()
                for value in (match_entry.get("candidate_ids") or [])
                if str(value).strip()
            ]
            candidate_ids = self._expand_structured_candidate_ids(candidate_ids, candidate_map)
            structured_candidates: List[Dict[str, Any]] = []
            for candidate_id in candidate_ids:
                current = self._structured_candidate_from_id(candidate_id, candidate_map)
                if not current:
                    continue
                if str(current.get("candidate_kind") or "") in {
                    "structured_value",
                    "structured_row",
                    "structured_column_value",
                    "table_row",
                    "evidence_row",
                }:
                    structured_candidates.append(current)
            candidate: Optional[Dict[str, Any]] = None
            selected_cell: Optional[Dict[str, Any]] = None
            if structured_candidates:
                structured_candidates.sort(
                    key=lambda current: _score_operand_candidate(
                        current,
                        operand=operand,
                        preferred_statement_types=preferred_statement_types,
                        constraints=constraints,
                        query_years=query_years,
                        report_scope=report_scope,
                    ),
                    reverse=True,
                )
                for current_candidate in structured_candidates:
                    current_metadata = dict(current_candidate.get("metadata") or {})
                    cells = [dict(cell) for cell in (current_metadata.get("structured_cells") or []) if dict(cell)]
                    if not cells and str(current_candidate.get("candidate_kind") or "") in {"table_row", "evidence_row"}:
                        cells = _parse_unstructured_table_row_cells(str(current_metadata.get("row_text") or ""), current_metadata)
                    if not cells:
                        continue
                    cells = [{**cell, "_report_year": current_metadata.get("year")} for cell in cells]
                    current_cell = _select_structured_cell(
                        cells,
                        operand=operand,
                        query_years=query_years,
                        period_focus=_operand_period_focus(operand, period_focus),
                    )
                    if not current_cell:
                        continue
                    if not _candidate_satisfies_direct_acceptance_contract(
                        current_candidate,
                        operand=operand,
                        constraints=constraints,
                        query_years=query_years,
                        operation_family=operation_family,
                        selected_cell=current_cell,
                        report_scope=report_scope,
                    ):
                        continue
                    candidate = current_candidate
                    selected_cell = current_cell
                    break
            if (not candidate or not selected_cell) and operation_family == "ratio":
                operand_role = str(operand.get("role") or "").strip()
                if operand_role.startswith("denominator"):
                    counterpart_prefix = "numerator"
                elif operand_role.startswith("numerator"):
                    counterpart_prefix = "denominator"
                else:
                    counterpart_prefix = ""
                same_table_ids = {
                    str(row.get("table_source_id") or "").strip()
                    for row in operand_rows
                    if str(row.get("table_source_id") or "").strip()
                    and (
                        not counterpart_prefix
                        or str(row.get("matched_operand_role") or "").strip().startswith(counterpart_prefix)
                    )
                }
                same_block_keys = {
                    _candidate_row_block_signature(candidate_map.get(str(row.get("evidence_id") or "").strip()) or {})
                    for row in operand_rows
                    if str(row.get("table_source_id") or "").strip()
                    and (
                        not counterpart_prefix
                        or str(row.get("matched_operand_role") or "").strip().startswith(counterpart_prefix)
                    )
                }
                same_block_keys = {key for key in same_block_keys if key}
                if same_table_ids:
                    same_table_candidates: List[Dict[str, Any]] = []
                    for current_candidate in candidate_map.values():
                        if str(current_candidate.get("candidate_kind") or "") not in {
                            "structured_value",
                            "structured_row",
                            "structured_column_value",
                            "table_row",
                            "evidence_row",
                        }:
                            continue
                        current_metadata = dict(current_candidate.get("metadata") or {})
                        table_source_id = str(current_metadata.get("table_source_id") or "").strip()
                        if table_source_id and table_source_id in same_table_ids:
                            if same_block_keys:
                                candidate_block_key = _candidate_row_block_signature(current_candidate)
                                if candidate_block_key and candidate_block_key not in same_block_keys:
                                    continue
                            same_table_candidates.append(current_candidate)
                    same_table_candidates.sort(
                        key=lambda current: (
                            6.0 if same_block_keys and _candidate_row_block_signature(current) in same_block_keys else 0.0
                        ) + (
                            3.0
                            + _score_operand_candidate(
                                current,
                                operand=operand,
                                preferred_statement_types=preferred_statement_types,
                                constraints=constraints,
                                query_years=query_years,
                                report_scope=report_scope,
                            )
                        ),
                        reverse=True,
                    )
                    for current_candidate in same_table_candidates:
                        current_metadata = dict(current_candidate.get("metadata") or {})
                        cells = [dict(cell) for cell in (current_metadata.get("structured_cells") or []) if dict(cell)]
                        if not cells and str(current_candidate.get("candidate_kind") or "") in {"table_row", "evidence_row"}:
                            cells = _parse_unstructured_table_row_cells(str(current_metadata.get("row_text") or ""), current_metadata)
                        if not cells:
                            continue
                        cells = [{**cell, "_report_year": current_metadata.get("year")} for cell in cells]
                        current_cell = _select_structured_cell(
                            cells,
                            operand=operand,
                            query_years=query_years,
                            period_focus=_operand_period_focus(operand, period_focus),
                        )
                        if not current_cell:
                            continue
                        direct_accept = _candidate_satisfies_direct_acceptance_contract(
                            current_candidate,
                            operand=operand,
                            constraints=constraints,
                            query_years=query_years,
                            operation_family=operation_family,
                            selected_cell=current_cell,
                            report_scope=report_scope,
                        )
                        if not direct_accept:
                            current_metadata = dict(current_candidate.get("metadata") or {})
                            candidate_value_role = str(current_metadata.get("value_role") or "").strip().lower()
                            candidate_aggregation_stage = str(current_metadata.get("aggregation_stage") or "").strip().lower()
                            relaxed_same_table_ratio_accept = (
                                operand_role.startswith("denominator")
                                and _candidate_has_numeric_value_signal(current_candidate)
                                and candidate_value_role == "aggregate"
                                and candidate_aggregation_stage in {"final", "subtotal", "direct"}
                            )
                            if not relaxed_same_table_ratio_accept:
                                continue
                        candidate = current_candidate
                        selected_cell = current_cell
                        break
            if not candidate or not selected_cell:
                continue
            operand_row = self._build_operand_row_from_candidate_cell(
                candidate=candidate,
                selected_cell=selected_cell,
                operand=operand,
                index=next_index,
                period_focus=period_focus,
                query_years=query_years,
            )
            if not operand_row:
                continue
            operand_rows.append(operand_row)
            next_index += 1

        return self._repair_note_operand_units_from_same_block(operand_rows, candidate_map)

    def _reconcile_retrieved_evidence(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Match required operands to the best available evidence candidates."""
        active_subtask = self._active_subtask_with_sibling_lookup_surfaces(
            dict(state.get("active_subtask") or {}),
            state,
        )
        dependency_state = self._dependency_binding_resolution_state(state)
        if dependency_state.get("all_resolved") and self._task_prefers_sibling_output_synthesis(state):
            result = self._dependency_resolved_reconciliation_result(
                active_subtask=active_subtask,
                dependency_state=dependency_state,
            )
            status = "ready"
            logger.info(
                "[reconcile] status=%s task=%s candidates=%s missing=%s retry_count=%s",
                status,
                result.get("task_id"),
                0,
                0,
                int(state.get("reconciliation_retry_count") or 0),
            )
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str(active_subtask.get("task_id") or "reconcile")
            artifact_id = f"reconcile:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.RECONCILIATION_RESULT,
                status=status,
                summary="reconciliation=ready(dependency_outputs)",
                payload={"reconciliation_result": result},
                evidence_refs=self._reconciliation_evidence_refs(result),
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.RECONCILIATION,
                label=f"reconcile {active_subtask.get('metric_label') or active_subtask.get('metric_family') or task_id}",
                status=TaskStatus.COMPLETED,
                query=str(active_subtask.get("query") or ""),
                metric_family=str(active_subtask.get("metric_family") or ""),
                constraints=dict(active_subtask.get("constraints") or {}),
                artifact_id=artifact_id,
            )
            return {
                "reconciliation_result": result,
                "retry_strategy": "",
                "retry_queries": [],
                "retry_reason": "",
                "tasks": tasks,
                "artifacts": artifacts,
            }

        years = _query_years_from_state(state)
        report_scope = dict(state.get("report_scope") or {})
        scope_year_raw = report_scope.get("year")
        try:
            if scope_year_raw not in (None, ""):
                scope_year = int(scope_year_raw)
                if scope_year not in years:
                    years = [scope_year, *years]
        except (TypeError, ValueError):
            pass

        candidates = self._build_reconciliation_candidates(state)
        retry_count = int(state.get("reconciliation_retry_count") or 0)
        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=years,
            reconciliation_retry_count=retry_count,
            report_scope=report_scope,
        )
        result = self._rerank_reconciliation_matches_with_llm(
            state,
            result,
            candidates,
            years,
        )
        result["retry_strategy"] = self._select_retry_strategy_for_reconciliation(
            state,
            result,
        )
        status = str(result.get("status") or "ready")
        logger.info(
            "[reconcile] status=%s task=%s candidates=%s missing=%s retry_count=%s",
            status,
            result.get("task_id"),
            len(candidates),
            len(result.get("missing_operands") or []),
            retry_count,
        )
        artifacts = list(state.get("artifacts") or [])
        tasks = list(state.get("tasks") or [])
        task_id = str(active_subtask.get("task_id") or "reconcile")
        artifact_id = f"reconcile:{task_id}:{len(artifacts) + 1:03d}"
        artifacts = _append_artifact(
            artifacts,
            artifact_id=artifact_id,
            task_id=task_id,
            kind=ArtifactKind.RECONCILIATION_RESULT,
            status=status,
            summary=f"reconciliation={status}",
            payload={"reconciliation_result": result},
            evidence_refs=self._reconciliation_evidence_refs(result),
        )
        tasks = _upsert_task(
            tasks,
            task_id=task_id,
            kind=TaskKind.RECONCILIATION,
            label=f"reconcile {active_subtask.get('metric_label') or active_subtask.get('metric_family') or task_id}",
            status=TaskStatus.COMPLETED if status == "ready" else TaskStatus.PARTIAL,
            query=str(active_subtask.get("query") or ""),
            metric_family=str(active_subtask.get("metric_family") or ""),
            constraints=dict(active_subtask.get("constraints") or {}),
            artifact_id=artifact_id,
        )
        updates: Dict[str, Any] = {
            "reconciliation_result": result,
            "tasks": tasks,
            "artifacts": artifacts,
        }
        if status == "retry_retrieval":
            updates.update(
                {
                    "retry_strategy": str(result.get("retry_strategy") or "retry_retrieval"),
                    "retry_queries": list(result.get("retry_queries") or []),
                    "retry_reason": "missing_operands",
                    "reconciliation_retry_count": retry_count + 1,
                }
            )
        elif status == "insufficient_operands":
            metric_label = str(active_subtask.get("metric_label") or "해당 지표").strip()
            missing_operands = [str(item).strip() for item in (result.get("missing_operands") or []) if str(item).strip()]
            if missing_operands:
                answer = f"{metric_label} 계산에 필요한 값({', '.join(missing_operands)})을 문서 근거에서 충분히 확인하지 못해 계산할 수 없습니다."
            else:
                answer = f"{metric_label} 계산에 필요한 값을 문서 근거에서 충분히 확인하지 못해 계산할 수 없습니다."
            updates.update(
                {
                    "answer": answer,
                    "compressed_answer": answer,
                    "draft_points": [answer],
                    "retry_strategy": str(result.get("retry_strategy") or "stop_insufficient"),
                    "retry_queries": [],
                    "retry_reason": "insufficient_operands",
                }
            )
        else:
            updates.update({"retry_strategy": "", "retry_queries": [], "retry_reason": ""})
        return updates

    def _select_retry_strategy_for_reconciliation(
        self,
        state: FinancialAgentState,
        result: Dict[str, Any],
    ) -> str:
        status = _normalise_spaces(str(result.get("status") or "")).lower()
        if status == "ready":
            return ""
        if self._task_prefers_sibling_output_synthesis(state):
            dependency_state = self._dependency_binding_resolution_state(state)
            if dependency_state.get("all_resolved"):
                return "synthesize_from_task_outputs"
        if status == "insufficient_operands":
            return "stop_insufficient"
        return "retry_retrieval"

    def _apply_strict_filter(self, docs, predicate):
        filtered = [item for item in docs if predicate(item[0])]
        return filtered if filtered else docs

    def _supplement_section_seed_docs(self, state: FinancialAgentState) -> List[tuple[Document, float]]:
        query = state["query"]
        topic = state.get("topic") or query
        intent = state.get("intent") or state.get("query_type", "qa")
        section_terms = _supplement_section_terms_for_query(query, topic, intent)
        section_terms.extend(_active_preferred_sections(state, query, topic, intent))
        section_terms = list(dict.fromkeys(term for term in section_terms if term))
        active_subtask = dict(state.get("active_subtask") or {})
        active_operand_needles = [
            _normalise_spaces(needle)
            for operand in (active_subtask.get("required_operands") or [])
            for needle in _operand_needles(dict(operand))
            if _normalise_spaces(needle)
        ]
        active_operand_needles.extend(
            _normalise_spaces(label)
            for label in _extract_generic_operand_labels(query)
            if _normalise_spaces(label)
        )
        active_operand_needles = list(dict.fromkeys(active_operand_needles))
        active_preferred_statement_types = [
            _normalise_spaces(str(item))
            for item in (active_subtask.get("preferred_statement_types") or [])
            if _normalise_spaces(str(item))
        ]
        for operand in (active_subtask.get("required_operands") or []):
            active_preferred_statement_types.extend(
                _normalise_spaces(str(item))
                for item in (dict(operand or {}).get("preferred_statement_types") or [])
                if _normalise_spaces(str(item))
            )
        active_preferred_statement_types.extend(_active_preferred_statement_types(state, query, topic))
        active_preferred_statement_types = list(dict.fromkeys(active_preferred_statement_types))
        if not section_terms and not (active_preferred_statement_types and active_operand_needles):
            return []
        bm25_docs = list(getattr(self.vsm, "bm25_docs", []) or [])
        bm25_metadatas = list(getattr(self.vsm, "bm25_metadatas", []) or [])
        if not bm25_docs or not bm25_metadatas:
            return []

        companies = {str(company).lower() for company in (state.get("companies") or [])}
        years = [int(year) for year in (state.get("years") or [])]
        multi_period = intent in {"comparison", "trend"} and len(years) > 1
        ratio_query = _is_ratio_percent_query(f"{query} {topic}")
        ontology = get_financial_ontology()
        metric_patterns = ontology.row_patterns(query, topic, intent)
        for spec in ontology.component_specs(query, topic, intent):
            metric_patterns.extend(re.escape(keyword) for keyword in spec.get("keywords", []))
        metric_patterns = list(dict.fromkeys(metric_patterns))

        supplemented: List[tuple[Document, float]] = []
        seen_chunk_uids: set[str] = set()
        for body, metadata in zip(bm25_docs, bm25_metadatas):
            metadata = dict(metadata or {})
            section_path = str(metadata.get("section_path") or metadata.get("section") or "")
            local_heading = _normalise_spaces(str(metadata.get("local_heading") or ""))
            row_labels = _normalise_spaces(str(metadata.get("table_row_labels_text") or ""))
            body_text = _normalise_spaces(str(body or ""))
            table_context = _normalise_spaces(str(metadata.get("table_context") or ""))
            section_surface = " ".join(part for part in (section_path, local_heading, table_context, row_labels, body_text[:800]) if part)
            section_match = any(term in section_surface for term in section_terms)
            statement_type = _normalise_spaces(str(metadata.get("statement_type") or ""))
            preferred_statement_match = bool(
                active_preferred_statement_types
                and statement_type in active_preferred_statement_types
            )
            operand_surface_match = bool(
                active_operand_needles
                and any(needle in section_surface for needle in active_operand_needles)
            )
            if not section_match and not (preferred_statement_match and operand_surface_match):
                continue
            company = str(metadata.get("company", "")).lower()
            if companies and company not in companies and not any(target in company or company in target for target in companies):
                continue
            if years and not multi_period:
                year_value = metadata.get("year")
                if int(year_value or 0) not in set(years):
                    continue

            chunk_uid = str(metadata.get("chunk_uid") or "")
            if chunk_uid and chunk_uid in seen_chunk_uids:
                continue
            seen_chunk_uids.add(chunk_uid)

            text = _normalise_spaces("\n".join(part for part in (local_heading, table_context, row_labels, body_text) if part))
            score = 0.02
            bonus_terms = tuple(
                str(item)
                for item in (RECONCILIATION_POLICY.get("supplemental_section_bonus_terms") or ())
                if str(item)
            )
            if bonus_terms and any(term in section_path for term in bonus_terms):
                score += 0.03
            if ratio_query and metric_patterns and any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in metric_patterns):
                score += 0.04
            if metric_patterns and any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in ontology.row_patterns(query, topic, intent)):
                score += 0.06
            if active_operand_needles and any(needle in text for needle in active_operand_needles):
                score += 0.08
            if preferred_statement_match and operand_surface_match:
                score += 0.12
            if active_operand_needles:
                covered_needles = sum(1 for needle in active_operand_needles if needle in text)
                score += min(0.06, covered_needles * 0.01)

            supplemented.append((Document(page_content=str(body or ""), metadata=metadata), score))

        supplemented.sort(key=lambda item: item[1], reverse=True)
        if supplemented:
            logger.info(
                "[retrieve] supplemental section seeds=%s for terms=%s",
                len(supplemented[:6]),
                section_terms,
            )
        return supplemented[:6]

    def _is_reflection_eligible(self, state: FinancialAgentState) -> bool:
        intent = state.get("intent") or state.get("query_type", "qa")
        return intent in {"comparison", "trend"}

    def _infer_missing_info(self, state: FinancialAgentState, operands: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        query = self._calc_query(state)
        topic = self._calc_topic(state)
        intent = state.get("intent") or state.get("query_type", "qa")
        years = [int(year) for year in (state.get("years") or [])]
        ontology = get_financial_ontology()
        metric_key = self._calc_metric_family(state)
        metric_info = ontology.metric_family(metric_key) if metric_key else None

        inferred: List[str] = []
        if metric_info:
            display_name = str(metric_info.get("display_name") or "").strip()
            if display_name and _is_ratio_percent_query(query):
                if years:
                    year_template = str(RECONCILIATION_POLICY.get("missing_info_year_template") or "{year} {label}")
                    inferred.extend(year_template.format(year=year, label=display_name) for year in years)
                else:
                    inferred.append(display_name)
            for component in (metric_info.get("components") or {}).values():
                component_name = str((component or {}).get("name") or "").strip()
                if not component_name:
                    continue
                if years:
                    year_template = str(RECONCILIATION_POLICY.get("missing_info_year_template") or "{year} {label}")
                    inferred.extend(year_template.format(year=year, label=component_name) for year in years)
                else:
                    inferred.append(component_name)

        if not inferred and years:
            year_template = str(RECONCILIATION_POLICY.get("missing_info_year_template") or "{year} {label}")
            inferred.extend(year_template.format(year=year, label=topic) for year in years)
        if not inferred:
            inferred.append(topic)

        cleaned_inferred: List[str] = []
        for item in inferred:
            cleanup_pattern = str(RECONCILIATION_POLICY.get("missing_info_suffix_cleanup_pattern") or "")
            cleaned = _normalise_spaces(
                re.sub(cleanup_pattern, "", str(item or "")) if cleanup_pattern else str(item or "")
            )
            if cleaned:
                cleaned_inferred.append(cleaned)
        inferred = cleaned_inferred or inferred

        if operands:
            operand_text = " ".join(
                _normalise_spaces(
                    " ".join(
                        [
                            str(row.get("label") or ""),
                            str(row.get("raw_value") or ""),
                            str(row.get("period") or ""),
                        ]
                    )
                )
                for row in operands
            )
            filtered: List[str] = []
            for candidate in inferred:
                token_pattern = str(RECONCILIATION_POLICY.get("missing_info_token_pattern") or "")
                candidate_tokens = [
                    token for token in re.findall(token_pattern, candidate) if len(token) >= 2
                ] if token_pattern else []
                if candidate_tokens and all(token in operand_text for token in candidate_tokens):
                    continue
                filtered.append(candidate)
            inferred = filtered or inferred

        return list(dict.fromkeys(item for item in inferred if item))

    def _build_retry_queries(self, state: FinancialAgentState, missing_info: List[str]) -> List[str]:
        companies = [str(company).strip() for company in (state.get("companies") or []) if str(company).strip()]
        if not companies:
            for doc, _score in (state.get("seed_retrieved_docs") or []):
                company = str((doc.metadata or {}).get("company") or "").strip()
                if company:
                    companies.append(company)
                    break
        years = [str(int(year)) for year in (state.get("years") or [])]
        query = state["query"]
        topic = state.get("topic") or query
        intent = state.get("intent") or state.get("query_type", "qa")
        preferred_sections = _preferred_calc_sections(query, topic, intent)

        queries: List[str] = []
        for item in missing_info:
            parts: List[str] = []
            if companies:
                parts.extend(companies)
            if years:
                parts.extend(years)
            parts.append(item)
            if preferred_sections:
                parts.extend(preferred_sections[:2])
            queries.append(_normalise_spaces(" ".join(parts)))
        return list(dict.fromkeys(query_text for query_text in queries if query_text))

    def _heuristic_reflection_query_plan(
        self,
        state: FinancialAgentState,
        operands: List[Dict[str, Any]],
        retry_objective: str = "generic_retry",
        explanation: str = "",
    ) -> Dict[str, Any]:
        retry_strategy = "retry_retrieval"
        dependency_state = self._dependency_binding_resolution_state(state)
        if self._task_prefers_sibling_output_synthesis(state) and dependency_state.get("all_resolved"):
            retry_strategy = "synthesize_from_task_outputs"
        elif not operands and not (state.get("missing_info") or []):
            retry_strategy = "stop_insufficient"
        missing_info = [
            str(item).strip()
            for item in (state.get("missing_info") or [])
            if str(item).strip()
        ]
        if not missing_info:
            missing_info = self._infer_missing_info(state, operands)
        subqueries = self._build_retry_queries(state, missing_info)
        preferred_sections = _preferred_calc_sections(
            state["query"],
            state.get("topic") or state["query"],
            state.get("intent") or state.get("query_type", "qa"),
        )
        return {
            "status": "ready" if subqueries else "skip",
            "retry_objective": retry_objective if subqueries else "generic_retry",
            "retry_strategy": retry_strategy,
            "missing_info": missing_info,
            "subqueries": subqueries,
            "preferred_sections": preferred_sections,
            "explanation": explanation or "heuristic retry query plan",
        }

    def _finalize_retry_queries(
        self,
        state: FinancialAgentState,
        reflection_plan: Dict[str, Any],
        missing_info: List[str],
    ) -> List[str]:
        base_queries = [
            _normalise_spaces(str(item))
            for item in (reflection_plan.get("subqueries") or [])
            if _normalise_spaces(str(item))
        ]
        if not base_queries:
            base_queries = self._build_retry_queries(state, missing_info)

        retry_objective = str(reflection_plan.get("retry_objective") or "")
        if retry_objective in {
            "find_missing_values",
            "resolve_binding",
            "find_direct_row",
        }:
            for item in missing_info[:2]:
                normalized = _normalise_spaces(str(item))
                if normalized:
                    base_queries.append(normalized)

        companies = [str(company).strip() for company in (state.get("companies") or []) if str(company).strip()]
        report_company_hint = ""
        for doc, _score in (state.get("seed_retrieved_docs") or []):
            company = str((doc.metadata or {}).get("company") or "").strip()
            if company:
                report_company_hint = company
                break
        if not report_company_hint:
            for doc, _score in (state.get("retrieved_docs") or []):
                company = str((doc.metadata or {}).get("company") or "").strip()
                if company:
                    report_company_hint = company
                    break

        global_preferred_sections = _preferred_calc_sections(
            state["query"],
            state.get("topic") or state["query"],
            state.get("intent") or state.get("query_type", "qa"),
        )
        preferred_sections = [
            _section_hint_alias(section)
            for section in (
                global_preferred_sections
                + list(reflection_plan.get("preferred_sections") or [])
            )
            if _section_hint_alias(section)
        ]
        preferred_sections = list(dict.fromkeys(preferred_sections))

        if preferred_sections and retry_objective in {
            "find_direct_row",
            "resolve_binding",
        }:
            for item in missing_info[:2]:
                normalized = _normalise_spaces(str(item))
                if not normalized:
                    continue
                for hint in preferred_sections[:2]:
                    base_queries.append(_normalise_spaces(f"{normalized} {hint}"))

        finalized: List[str] = []
        for query_text in base_queries:
            normalized_query = _normalise_spaces(query_text)
            for raw_section in (reflection_plan.get("preferred_sections") or []):
                alias = _section_hint_alias(str(raw_section))
                raw_section_text = _normalise_spaces(str(raw_section))
                if raw_section_text and alias:
                    normalized_query = normalized_query.replace(raw_section_text, alias)
            parts: List[str] = []
            lowered = normalized_query.lower()
            if report_company_hint and report_company_hint.lower() not in lowered:
                parts.append(report_company_hint)
            parts.append(normalized_query)
            finalized.append(_normalise_spaces(" ".join(parts)))

        return list(dict.fromkeys(item for item in finalized if item))

    def _plan_reflection_retry(self, state: FinancialAgentState) -> Dict[str, Any]:
        runtime_trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        operands = list(runtime_trace.get("calculation_operands") or [])
        plan = dict(runtime_trace.get("calculation_plan") or {})
        calc_result = dict(runtime_trace.get("calculation_result") or {})
        query = state["query"]
        topic = state.get("topic") or query
        intent = state.get("intent") or state.get("query_type", "qa")
        years = [int(year) for year in (state.get("years") or [])]
        companies = [str(company).strip() for company in (state.get("companies") or []) if str(company).strip()]
        preferred_sections = _preferred_calc_sections(query, topic, intent)

        missing_info = [
            str(item).strip()
            for item in (plan.get("missing_info") or state.get("missing_info") or [])
            if str(item).strip()
        ]
        if not missing_info:
            missing_info = self._infer_missing_info(state, operands)

        ratio_query = _is_ratio_percent_query(query)
        percent_point_query = _is_percent_point_difference_query(query)
        sum_markers = tuple(
            str(item)
            for item in (RECONCILIATION_POLICY.get("reflection_sum_query_markers") or ())
            if str(item)
        )
        sum_query = bool(sum_markers and any(token in query for token in sum_markers))
        binding_query_pattern = str(RECONCILIATION_POLICY.get("reflection_binding_query_pattern") or "")
        fallback_retry_objective = "generic_retry"
        if percent_point_query:
            fallback_retry_objective = "find_direct_row"
        elif ratio_query and len(operands) < 2:
            fallback_retry_objective = "find_missing_values"
        elif sum_query:
            fallback_retry_objective = "find_missing_values"
        elif years and len(years) > 1:
            fallback_retry_objective = "resolve_binding"
        elif binding_query_pattern and re.search(binding_query_pattern, query):
            fallback_retry_objective = "resolve_binding"
        elif not operands:
            fallback_retry_objective = "find_missing_values"

        seed_sections: List[str] = []
        for doc, _score in (state.get("seed_retrieved_docs") or [])[:6]:
            section_path = str((doc.metadata or {}).get("section_path") or (doc.metadata or {}).get("section") or "").strip()
            if section_path:
                seed_sections.append(section_path)
        seed_sections = list(dict.fromkeys(seed_sections))

        ontology = get_financial_ontology()
        metric_key = self._calc_metric_family(state)
        metric_info = ontology.metric_family(metric_key) if metric_key else None
        ontology_lines: List[str] = []
        if metric_info:
            ontology_lines.append(f"- key={metric_info.get('key', '')}")
            ontology_lines.append(f"- display_name={metric_info.get('display_name', '')}")
            ontology_lines.append(f"- result_unit={metric_info.get('result_unit', '')}")
            formula_template = str(metric_info.get("formula_template") or "").strip()
            if formula_template:
                ontology_lines.append(f"- formula_template={formula_template}")
            components = metric_info.get("components") or {}
            if components:
                ontology_lines.append("- components:")
                for role, component in components.items():
                    component_name = str((component or {}).get("name") or "").strip()
                    component_keywords = [str(keyword).strip() for keyword in ((component or {}).get("keywords") or []) if str(keyword).strip()]
                    ontology_lines.append(
                        f"  - {role}: {component_name} | keywords={component_keywords}"
                    )
        ontology_context = "\n".join(ontology_lines) or "-"

        operand_lines = [
            (
                f"- {row.get('operand_id', '')} | label={row.get('label', '')} | "
                f"raw={row.get('raw_value', '')} {row.get('raw_unit', '')} | "
                f"normalized={row.get('normalized_value', '')} {row.get('normalized_unit', '')} | "
                f"period={row.get('period', '')}"
            )
            for row in operands
        ]
        seed_section_text = "\n".join(f"- {section}" for section in seed_sections) or "-"
        operand_text = "\n".join(operand_lines) or "-"
        plan_text = json.dumps(plan, ensure_ascii=False, indent=2) if plan else "{}"
        calc_result_text = json.dumps(calc_result, ensure_ascii=False, indent=2) if calc_result else "{}"
        heuristic_plan = self._heuristic_reflection_query_plan(
            state,
            operands,
            retry_objective=fallback_retry_objective,
            explanation="fallback reflection query plan",
        )

        structured_llm = self._llm_for_phase("reflection_planning").with_structured_output(ReflectionQueryPlan)
        prompt = ChatPromptTemplate.from_template(str(RECONCILIATION_POLICY.get("reflection_prompt_template") or ""))
        try:
            reflection_plan: ReflectionQueryPlan = (prompt | structured_llm).invoke(
                {
                    "query": query,
                    "intent": intent,
                    "topic": topic,
                    "companies": companies or ["-"],
                    "years": years or ["-"],
                    "retry_objective": fallback_retry_objective,
                    "missing_info": missing_info or ["-"],
                    "ontology_context": ontology_context,
                    "operands": operand_text,
                    "plan_text": plan_text,
                    "calc_result_text": calc_result_text,
                    "seed_sections": seed_section_text,
                    "heuristic_plan": json.dumps(heuristic_plan, ensure_ascii=False, indent=2),
                }
            )
            plan_data = _normalise_reflection_plan_record(
                reflection_plan.model_dump(),
                fallback_plan=heuristic_plan,
                missing_info=missing_info,
                preferred_sections=preferred_sections,
            )
            logger.info(
                "[reflection_replan] status=%s retry_objective=%s subqueries=%s",
                plan_data.get("status"),
                plan_data.get("retry_objective"),
                len(plan_data.get("subqueries") or []),
            )
            return {
                "reflection_plan": plan_data,
                "missing_info": plan_data.get("missing_info", []),
                "retry_reason": str(plan_data.get("explanation") or ""),
                "planner_debug_trace": {
                    **dict(state.get("planner_debug_trace") or {}),
                    "reflection_plan": plan_data,
                    "reflection_seed_sections": seed_sections,
                    "reflection_llm_invoked": True,
                },
            }
        except Exception as exc:
            logger.warning("[reflection_replan] structured output failed: %s", exc)
            fallback_plan = heuristic_plan
            fallback_plan["explanation"] = f"heuristic fallback after reflection planner error: {exc}"
            return {
                "reflection_plan": fallback_plan,
                "missing_info": fallback_plan.get("missing_info", []),
                "retry_reason": str(fallback_plan.get("explanation") or ""),
                "planner_debug_trace": {
                    **dict(state.get("planner_debug_trace") or {}),
                    "reflection_plan": fallback_plan,
                    "reflection_seed_sections": seed_sections,
                    "reflection_llm_invoked": True,
                    "reflection_error": str(exc),
                },
            }

