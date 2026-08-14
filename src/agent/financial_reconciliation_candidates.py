"""State-free structured reconciliation candidate projections."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.agent.financial_graph_helpers import (
    _resolve_candidate_local_unit_hint,
    _score_operand_candidate,
)
from src.agent.financial_operand_resolution import (
    candidate_satisfies_direct_acceptance_contract,
    coerce_lookup_magnitude_value,
)
from src.agent.financial_operation_policies import _label_implies_percent_metric
from src.agent.financial_row_surfaces import _parse_unstructured_table_row_cells
from src.agent.financial_runtime_normalization import _normalise_operand_value, _normalise_spaces
from src.agent.financial_scope_policies import operand_period_focus, operand_target_years
from src.agent.financial_structured_cells import _structured_cell_period_text, score_structured_cell
from src.config.retrieval_policy import (
    FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES,
    RECONCILIATION_POLICY,
)


def _candidate_statement_type(candidate: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    explicit_statement_type = _normalise_spaces(str(metadata.get("statement_type") or ""))
    if explicit_statement_type:
        return explicit_statement_type
    surface = _normalise_spaces(
        " ".join(
            str(value or "")
            for value in (
                metadata.get("section_path"),
                metadata.get("section_title"),
                metadata.get("local_heading"),
                metadata.get("table_context"),
                candidate.get("source_anchor"),
                candidate.get("source_context"),
            )
            if str(value or "").strip()
        )
    )
    if not surface:
        return ""
    for policy in FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES:
        markers = [
            _normalise_spaces(str(marker))
            for marker in (policy.get("markers") or [])
            if _normalise_spaces(str(marker))
        ]
        if not any(marker in surface for marker in markers):
            continue
        statement_types = [
            _normalise_spaces(str(statement_type))
            for statement_type in (policy.get("statement_types") or [])
            if _normalise_spaces(str(statement_type))
        ]
        if statement_types:
            return statement_types[0]
    return ""


def _structured_candidate_unit_hint(
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


def _fallback_period_text_for_operand(operand: Dict[str, Any], query_years: List[int]) -> str:
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


def structured_cell_identity(cell: Dict[str, Any]) -> str:
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
    *,
    operand: Dict[str, Any],
    cell: Dict[str, Any],
    query_years: List[int],
    period_focus: str,
) -> str:
    effective_period_focus = operand_period_focus(operand, period_focus)
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
        target_years = operand_target_years(operand, query_years)
        if report_year is not None and target_years and report_year in target_years:
            period = str(report_year)
        elif report_year is not None:
            period = str(report_year)
        else:
            period = _fallback_period_text_for_operand(operand_with_period_focus, query_years)
    return period


def pair_candidate_period_score(
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
    cell_score = score_structured_cell(
        cell,
        query_years=operand_target_years(operand, query_years),
        period_focus=operand_period_focus(operand, period_focus),
        operand=operand,
    )
    period = _resolved_period_text_for_operand(
        operand=operand,
        cell=cell,
        query_years=query_years,
        period_focus=period_focus,
    )
    return candidate_score + cell_score, period


def find_reconciliation_match_entry(
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


def build_operand_row_from_candidate_cell(
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
    raw_unit = _structured_candidate_unit_hint(
        raw_value=raw_value,
        raw_unit=raw_unit,
        candidate=candidate,
        operand=operand,
        selected_cell=selected_cell,
    )
    normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
    normalized_value = coerce_lookup_magnitude_value(
        normalized_value=normalized_value,
        normalized_unit=normalized_unit,
        raw_value=raw_value,
        concept=str(operand.get("concept") or ""),
        statement_type=_candidate_statement_type(candidate, metadata),
        row_label=str(metadata.get("row_label") or ""),
        semantic_label=str(metadata.get("semantic_label") or ""),
    )
    if normalized_value is None:
        return None
    period = _resolved_period_text_for_operand(
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
        "statement_type": _candidate_statement_type(candidate, metadata),
        "consolidation_scope": metadata.get("consolidation_scope"),
        "value_role": _normalise_spaces(str(selected_cell.get("value_role") or metadata.get("value_role") or "")),
        "aggregation_stage": _normalise_spaces(
            str(selected_cell.get("aggregation_stage") or metadata.get("aggregation_stage") or "")
        ),
        "aggregate_label": _normalise_spaces(
            str(selected_cell.get("aggregate_label") or metadata.get("aggregate_label") or "")
        ),
        "matched_operand_label": str(operand.get("label") or "").strip(),
        "matched_operand_concept": str(operand.get("concept") or "").strip(),
        "matched_operand_role": str(operand.get("role") or "").strip(),
    }


def effective_structured_cell_unit_hint(
    *,
    candidate: Dict[str, Any],
    selected_cell: Dict[str, Any],
    operand: Dict[str, Any],
) -> str:
    metadata = dict(candidate.get("metadata") or {})
    raw_value = str(selected_cell.get("value_text") or "").strip()
    raw_unit = str(selected_cell.get("unit_hint") or metadata.get("unit_hint") or "").strip()
    return _structured_candidate_unit_hint(
        raw_value=raw_value,
        raw_unit=raw_unit,
        candidate=candidate,
        operand=operand,
        selected_cell=selected_cell,
    )


def expand_structured_candidate_ids(
    candidate_ids: List[str],
    candidate_map: Dict[str, Dict[str, Any]],
) -> List[str]:
    expanded: List[str] = []
    seen: set[str] = set()
    for raw_candidate_id in candidate_ids:
        cleaned = str(raw_candidate_id).strip()
        if not cleaned:
            continue
        candidate_variants = [cleaned]
        if cleaned.startswith("recon::"):
            candidate_variants.append(cleaned.removeprefix("recon::"))
        else:
            candidate_variants.append(f"recon::{cleaned}")
        expanded_variants: List[str] = []
        for candidate_variant in list(dict.fromkeys(candidate_variants)):
            expanded_variants.append(candidate_variant)
            expanded_variants.append(f"{candidate_variant}::raw_row")
        for current_id in expanded_variants:
            if current_id in seen or current_id not in candidate_map:
                continue
            seen.add(current_id)
            expanded.append(current_id)
    return expanded


def structured_candidate_from_id(
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


def extract_structured_period_pair_rows(
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
        current_match = find_reconciliation_match_entry(reconciliation_result, current_operand)
        prior_match = find_reconciliation_match_entry(reconciliation_result, prior_operand)
        candidate_ids: List[str] = []
        for match_entry in (current_match, prior_match):
            for candidate_id in (match_entry.get("candidate_ids") or []):
                cleaned = str(candidate_id).strip()
                if cleaned and cleaned not in candidate_ids:
                    candidate_ids.append(cleaned)
        candidate_ids = expand_structured_candidate_ids(candidate_ids, candidate_map)
        structured_candidates: List[Dict[str, Any]] = []
        for candidate_id in candidate_ids:
            current_candidate = structured_candidate_from_id(candidate_id, candidate_map)
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
                if candidate_satisfies_direct_acceptance_contract(
                    candidate,
                    operand=current_operand,
                    constraints=constraints,
                    query_years=query_years,
                    operation_family=operation_family,
                    selected_cell=cell,
                    report_scope=report_scope,
                ):
                    current_score, current_period = pair_candidate_period_score(
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
                if candidate_satisfies_direct_acceptance_contract(
                    candidate,
                    operand=prior_operand,
                    constraints=constraints,
                    query_years=query_years,
                    operation_family=operation_family,
                    selected_cell=cell,
                    report_scope=report_scope,
                ):
                    prior_score, prior_period = pair_candidate_period_score(
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
                current_identity = structured_cell_identity(current_cell)
                for prior_cell, prior_period, prior_score in accepted_prior_entries:
                    if current_identity == structured_cell_identity(prior_cell):
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
                    if structured_cell_identity(current_cell) == structured_cell_identity(prior_cell):
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
        current_unit_hint = effective_structured_cell_unit_hint(
            candidate=current_candidate,
            selected_cell=current_cell,
            operand=current_operand,
        )
        prior_unit_hint = effective_structured_cell_unit_hint(
            candidate=prior_candidate,
            selected_cell=prior_cell,
            operand=prior_operand,
        )
        if current_unit_hint and not prior_unit_hint:
            prior_cell = {**prior_cell, "unit_hint": current_unit_hint}
        elif prior_unit_hint and not current_unit_hint:
            current_cell = {**current_cell, "unit_hint": prior_unit_hint}
        current_row = build_operand_row_from_candidate_cell(
            candidate=current_candidate,
            selected_cell=current_cell,
            operand=current_operand,
            index=next_index,
            period_focus=period_focus,
            query_years=query_years,
        )
        prior_row = build_operand_row_from_candidate_cell(
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
