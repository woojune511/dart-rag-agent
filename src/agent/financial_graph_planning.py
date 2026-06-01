"""
Planning mixin for the financial graph agent.

This module owns the "front" of the graph:
- classify the query
- extract entity and metric hints
- translate the query into numeric subtasks when possible
- project ledger state back into the legacy flat result shape
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from src.agent.financial_graph_helpers import *  # noqa: F401,F403
from src.agent.financial_graph_helpers import _extract_segment_labels_from_query, _infer_concept_ratio_result_unit
from src.agent.financial_graph_models import (
    ConceptPlannerOutput,
    EntityExtraction,
    FinancialAgentState,
    validate_answer_slots_payload,
)
from src.config import get_financial_ontology
from src.config.retrieval_policy import (
    NARRATIVE_BASE_RETRIEVAL_SUFFIXES,
    NUMERIC_UNIT_NORMALIZATION_POLICY,
    PLANNING_POLICY,
    active_narrative_policies,
    narrative_policy_preferred_sections,
    narrative_policy_query_suffixes,
    narrative_policy_slot_groups,
    narrative_policy_terms,
)
from src.routing import default_format_preference
from src.schema import ArtifactKind, TaskKind, TaskStatus

logger = logging.getLogger(__name__)


_MONEY_SURFACE_RE = re.compile(str(PLANNING_POLICY.get("money_surface_pattern") or r"$^"))
_LOOKUP_YEAR_RE = re.compile(str(PLANNING_POLICY.get("year_token_pattern") or r"$^"))
_LOOKUP_YEAR_LABEL_RE = re.compile(str(PLANNING_POLICY.get("year_label_token_pattern") or r"$^"))


def _slot_has_material(slot: Dict[str, Any]) -> bool:
    if not isinstance(slot, dict) or not slot:
        return False
    status = str(slot.get("status") or "").strip().lower()
    if status == "missing":
        return False
    if slot.get("normalized_value") is not None:
        return True
    return bool(str(slot.get("rendered_value") or slot.get("raw_value") or "").strip())


def _money_match_to_slot_values(match: re.Match[str]) -> Dict[str, Any]:
    raw_number = _normalise_spaces(match.group("raw"))
    if raw_number.startswith("(") and not raw_number.endswith(")"):
        raw_number = raw_number[1:]
    raw_unit = _normalise_spaces(match.group("unit"))
    rendered_value = _normalise_spaces(f"{raw_number}{raw_unit}")
    compound_unit_prefix = str(PLANNING_POLICY.get("money_surface_compound_unit_prefix") or "")
    normalized_input = rendered_value if compound_unit_prefix and raw_unit.startswith(compound_unit_prefix) else raw_number
    normalized_value, normalized_unit = _normalise_operand_value(normalized_input, raw_unit)
    return {
        "raw_value": raw_number,
        "raw_unit": raw_unit,
        "rendered_value": rendered_value,
        "normalized_value": normalized_value,
        "normalized_unit": normalized_unit,
    }


def _slot_values_match_operand_unit(values: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    desired_unit = _normalise_spaces(str(operand.get("unit_family") or "")).upper()
    actual_unit = _normalise_spaces(str(values.get("normalized_unit") or "")).upper()
    if desired_unit not in {"KRW", "USD", "COUNT", "PERCENT"}:
        return True
    if not actual_unit or actual_unit == "UNKNOWN":
        return True
    return actual_unit == desired_unit


def _lookup_operand_matches_active_task(operand: Dict[str, Any], active_subtask: Dict[str, Any]) -> bool:
    active_label = _normalise_spaces(str(active_subtask.get("metric_label") or active_subtask.get("query") or ""))
    operand_label = _normalise_spaces(
        str(operand.get("label") or operand.get("matched_operand_label") or operand.get("name") or "")
    )
    operand_period = _normalise_spaces(str(operand.get("period") or operand.get("period_hint") or ""))
    active_years = set(_LOOKUP_YEAR_RE.findall(active_label))
    operand_years = set(_LOOKUP_YEAR_RE.findall(f"{operand_label} {operand_period}"))
    if active_years and operand_years and not (active_years & operand_years):
        return False
    if active_years and not operand_years:
        return False
    if active_label and operand_label:
        if active_label == operand_label or active_label in operand_label or operand_label in active_label:
            return True
        active_tokens = {
            token
            for token in re.split(r"\s+", active_label)
            if token and not _LOOKUP_YEAR_LABEL_RE.fullmatch(token)
        }
        operand_tokens = {
            token
            for token in re.split(r"\s+", operand_label)
            if token and not _LOOKUP_YEAR_LABEL_RE.fullmatch(token)
        }
        return bool(active_tokens & operand_tokens)
    return True


def _refine_lookup_slot_unit_from_evidence(slot: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    raw_value = _normalise_spaces(str(slot.get("raw_value") or ""))
    if not raw_value:
        return slot
    current_unit = _normalise_spaces(str(slot.get("raw_unit") or ""))
    text = _normalise_spaces(
        " ".join(
            str(part or "")
            for part in [
                evidence.get("raw_row_text"),
                evidence.get("quote_span"),
                evidence.get("claim"),
                (evidence.get("metadata") or {}).get("table_value_labels_text"),
            ]
        )
    )

    def _update_with_unit(unit_text: str) -> Optional[Dict[str, Any]]:
        evidence_unit = _normalise_spaces(str(unit_text or "")).strip("()[]{}")
        if not evidence_unit or evidence_unit == current_unit:
            return None
        aliases = dict(NUMERIC_UNIT_NORMALIZATION_POLICY.get("inline_unit_aliases") or {})
        evidence_unit = str(aliases.get(evidence_unit, evidence_unit))
        normalized_value, normalized_unit = _normalise_operand_value(raw_value, evidence_unit)
        if normalized_value is not None and str(normalized_unit or "").strip().upper() != "UNKNOWN":
            updated = dict(slot)
            updated["raw_unit"] = evidence_unit
            updated["normalized_value"] = normalized_value
            updated["normalized_unit"] = normalized_unit
            updated["rendered_value"] = _normalise_spaces(f"{raw_value}{evidence_unit}")
            return updated
        return None

    if text and raw_value in text:
        inline_pattern = str(NUMERIC_UNIT_NORMALIZATION_POLICY.get("inline_value_unit_pattern") or "")
        if inline_pattern:
            raw_compact = re.sub(r"[,\s()]", "", raw_value)
            for match in re.finditer(inline_pattern, text):
                matched_compact = re.sub(r"[,\s()]", "", str(match.group("value") or ""))
                if matched_compact != raw_compact:
                    continue
                updated = _update_with_unit(str(match.group("unit") or ""))
                if updated:
                    return updated
        match = re.search(rf"{re.escape(raw_value)}\s*([^\s|,)]+)", text)
        if match:
            updated = _update_with_unit(match.group(1))
            if updated:
                return updated
    metadata = dict(evidence.get("metadata") or {})
    unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or ""))
    if unit_hint and not current_unit:
        updated = _update_with_unit(unit_hint)
        if updated:
            return updated
    if current_unit:
        return slot
    return slot


def _extract_lookup_slot_from_answer_text(
    *,
    answer: str,
    operand: Dict[str, Any],
    metric_label: str,
    selected_claim_ids: List[str],
) -> Optional[Dict[str, Any]]:
    """Build a lookup answer slot from ontology operand surfaces in prose."""
    text = _normalise_spaces(answer)
    if not text:
        return None
    surface_contract = dict(operand.get("surface_contract") or {})
    surfaces = [
        _normalise_spaces(str(surface))
        for surface in [
            *(surface_contract.get("positive") or []),
            *_operand_needles(operand),
        ]
        if _normalise_spaces(str(surface))
    ]
    surfaces = sorted(dict.fromkeys(surfaces), key=len, reverse=True)
    money_matches = list(_MONEY_SURFACE_RE.finditer(text))
    if not surfaces:
        if len(money_matches) != 1:
            return None
        best_match = money_matches[0]
        values = _money_match_to_slot_values(best_match)
        if values.get("normalized_value") is None and not values.get("rendered_value"):
            return None
        if not _slot_values_match_operand_unit(values, operand):
            return None
        source_claim_ids = [
            str(claim_id).strip()
            for claim_id in selected_claim_ids
            if str(claim_id).strip()
        ]
        return {
            "label": _normalise_spaces(str(operand.get("label") or metric_label)),
            "concept": _normalise_spaces(str(operand.get("concept") or "")),
            "role": _normalise_spaces(str(operand.get("role") or "primary_value")) or "primary_value",
            "period": _normalise_spaces(str(operand.get("period_hint") or operand.get("period") or "")),
            "status": "ok",
            **values,
            "source_row_id": source_claim_ids[0] if source_claim_ids else "",
            "source_row_ids": source_claim_ids[:1],
            "source_claim_ids": source_claim_ids,
        }

    haystack = text.lower()
    best_match: Optional[re.Match[str]] = None
    best_distance: Optional[int] = None
    for surface in surfaces:
        needle = surface.lower()
        search_from = 0
        while True:
            surface_index = haystack.find(needle, search_from)
            if surface_index < 0:
                break
            window = text[surface_index : surface_index + max(80, len(surface) + 80)]
            money_match = _MONEY_SURFACE_RE.search(window)
            if money_match:
                values = _money_match_to_slot_values(money_match)
                if not _slot_values_match_operand_unit(values, operand):
                    search_from = surface_index + max(1, len(needle))
                    continue
                distance = money_match.start()
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best_match = money_match
            search_from = surface_index + max(1, len(needle))

    if best_match is None:
        return None
    values = _money_match_to_slot_values(best_match)
    if values.get("normalized_value") is None and not values.get("rendered_value"):
        return None
    source_claim_ids = [
        str(claim_id).strip()
        for claim_id in selected_claim_ids
        if str(claim_id).strip()
    ]
    return {
        "label": _normalise_spaces(str(operand.get("label") or metric_label)),
        "concept": _normalise_spaces(str(operand.get("concept") or "")),
        "role": _normalise_spaces(str(operand.get("role") or "primary_value")) or "primary_value",
        "period": _normalise_spaces(str(operand.get("period_hint") or operand.get("period") or "")),
        "status": "ok",
        **values,
        "source_row_id": source_claim_ids[0] if source_claim_ids else "",
        "source_row_ids": source_claim_ids[:1],
        "source_claim_ids": source_claim_ids,
    }


def _synthesize_lookup_answer_slot_from_prose(
    *,
    active_subtask: Dict[str, Any],
    answer: str,
    calculation_result: Dict[str, Any],
    selected_claim_ids: List[str],
) -> Dict[str, Any]:
    operation_family = _normalise_spaces(str(active_subtask.get("operation_family") or "")).lower()
    metric_family = _normalise_spaces(str(active_subtask.get("metric_family") or "")).lower()
    if operation_family not in {"lookup", "single_value", "concept_lookup"} and not metric_family.startswith("concept_"):
        return calculation_result

    operands = [dict(item or {}) for item in list(active_subtask.get("required_operands") or []) if isinstance(item, dict)]
    if not operands:
        operands = [
            {
                "label": _normalise_spaces(str(active_subtask.get("metric_label") or "")),
                "concept": _normalise_spaces(str(active_subtask.get("metric_family") or "")),
                "role": "primary_value",
            }
        ]
    if len(operands) != 1:
        return calculation_result

    answer_slots = dict(calculation_result.get("answer_slots") or {})
    if _slot_has_material(dict(answer_slots.get("primary_value") or {})):
        return calculation_result

    slot = _extract_lookup_slot_from_answer_text(
        answer=answer,
        operand=operands[0],
        metric_label=str(active_subtask.get("metric_label") or ""),
        selected_claim_ids=selected_claim_ids,
    )
    if not slot:
        return calculation_result

    updated_slots = {
        **answer_slots,
        "operation_family": "lookup",
        "primary_value": slot,
    }
    rendered_value = _normalise_spaces(str(slot.get("rendered_value") or ""))
    return {
        **calculation_result,
        "status": "ok",
        "operation_family": "lookup",
        "rendered_value": rendered_value,
        "formatted_result": _normalise_spaces(answer) or rendered_value,
        "answer_slots": validate_answer_slots_payload(updated_slots),
    }


def _doc_metadata_value(doc: Any, key: str) -> str:
    metadata = getattr(doc, "metadata", None)
    if isinstance(metadata, dict):
        return _normalise_spaces(str(metadata.get(key) or ""))
    return ""


def _doc_page_content(doc: Any) -> str:
    return _normalise_spaces(str(getattr(doc, "page_content", "") or ""))


def _source_anchor_from_doc(doc: Any) -> str:
    explicit = _doc_metadata_value(doc, "source_anchor")
    if explicit:
        return explicit
    metadata = getattr(doc, "metadata", None)
    if not isinstance(metadata, dict):
        return ""
    parts = [
        _normalise_spaces(str(metadata.get("company") or "")),
        _normalise_spaces(str(metadata.get("year") or "")),
        _normalise_spaces(str(metadata.get("section_path") or metadata.get("section") or "")),
    ]
    parts = [part for part in parts if part]
    return f"[{' | '.join(parts)}]" if parts else ""


def _lookup_slot_supporting_doc_evidence(
    *,
    active_subtask: Dict[str, Any],
    slot: Dict[str, Any],
    docs: List[Any],
) -> Optional[Dict[str, Any]]:
    rendered_value = _normalise_spaces(str(slot.get("rendered_value") or ""))
    raw_value = _normalise_spaces(str(slot.get("raw_value") or ""))
    if not rendered_value and not raw_value:
        return None
    operands = [dict(item or {}) for item in list(active_subtask.get("required_operands") or []) if isinstance(item, dict)]
    operand = operands[0] if operands else {}
    surface_contract = dict(operand.get("surface_contract") or {})
    surfaces = [
        _normalise_spaces(str(surface))
        for surface in [
            *(surface_contract.get("positive") or []),
            *_operand_needles(operand),
            str(slot.get("label") or ""),
        ]
        if _normalise_spaces(str(surface))
    ]
    compact_raw = raw_value.replace(",", "")
    for doc in docs:
        text = _doc_page_content(doc)
        compact_text = text.replace(",", "")
        if rendered_value and rendered_value not in text:
            if not raw_value or raw_value not in text:
                if not compact_raw or compact_raw not in compact_text:
                    continue
        if surfaces and not any(surface in text for surface in surfaces):
            continue
        anchor = _source_anchor_from_doc(doc)
        metadata = dict(getattr(doc, "metadata", {}) or {})
        return {
            "evidence_id": f"slot_support:{str(active_subtask.get('task_id') or 'lookup')}:primary_value",
            "source_anchor": anchor,
            "claim": text[:700],
            "quote_span": rendered_value or raw_value,
            "metadata": metadata,
        }
    return None


def _project_logical_tasks_from_execution_tasks(
    logical_tasks: List[Dict[str, Any]],
    execution_tasks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Keep semantic-plan tasks compact while borrowing dependency annotations.

    Planner-facing payloads should preserve the original semantic task list
    (e.g. one ratio task), while executor-facing payloads can expand into
    lookup producers plus a derived consumer. We therefore copy dependency
    annotations back onto the original logical tasks without exposing the
    synthetic execution-only lookup tasks in `semantic_plan.tasks`.
    """
    execution_by_id = {
        str(task.get("task_id") or "").strip(): dict(task)
        for task in execution_tasks
        if str(task.get("task_id") or "").strip()
    }
    projected: List[Dict[str, Any]] = []
    for task in logical_tasks:
        task_id = str(task.get("task_id") or "").strip()
        if task_id and task_id in execution_by_id:
            projected.append(dict(execution_by_id[task_id]))
        else:
            projected.append(dict(task))
    return projected


def _dependency_closure_task_ids(
    tasks: List[Dict[str, Any]],
    seed_task_ids: List[str],
) -> set[str]:
    """Return the dependency closure (ancestors + seeds) for the given tasks."""
    task_by_id = {
        str(task.get("task_id") or "").strip(): dict(task)
        for task in tasks
        if str(task.get("task_id") or "").strip()
    }
    closure = {
        _normalise_spaces(task_id)
        for task_id in seed_task_ids
        if _normalise_spaces(task_id)
    }
    pending = list(closure)
    while pending:
        task_id = pending.pop()
        task = task_by_id.get(task_id)
        if not task:
            continue
        for dependency in list(task.get("depends_on") or []):
            dependency_id = _normalise_spaces(str(dependency or ""))
            if dependency_id and dependency_id not in closure:
                closure.add(dependency_id)
                pending.append(dependency_id)
    return closure


def _is_narrative_summary_task(task: Dict[str, Any]) -> bool:
    operation_family = _normalise_spaces(str(task.get("operation_family") or "")).lower()
    metric_family = _normalise_spaces(str(task.get("metric_family") or "")).lower()
    return operation_family == "narrative_summary" or metric_family == "narrative_summary"


def _needs_hybrid_narrative_subtask(query: str, intent: str) -> bool:
    return intent in {"comparison", "trend", "numeric_fact"} and _query_requests_narrative_context(query)


def _build_hybrid_narrative_subtask(
    *,
    query: str,
    intent: str = "qa",
    report_scope: Dict[str, Any],
    next_task_id: str,
) -> Dict[str, Any]:
    consolidation_scope = _desired_consolidation_scope(query, report_scope)
    period_focus = _infer_period_focus(query, "unknown")
    active_policies = active_narrative_policies(query)
    active_slot_groups = [
        group
        for group in narrative_policy_slot_groups(active_policies)
        if any(str(term).strip() and str(term).strip() in query for term in (group.get("query_terms") or []))
    ]
    format_preference_override = (
        "table"
        if active_slot_groups or default_format_preference(intent) == "table"
        else "paragraph"
    )
    retrieval_queries = [_normalise_spaces(query)]
    base_suffixes = (
        ()
        if format_preference_override == "table"
        else NARRATIVE_BASE_RETRIEVAL_SUFFIXES
    )
    retrieval_queries.extend(
        _normalise_spaces(f"{query} {suffix}")
        for suffix in (*base_suffixes, *narrative_policy_query_suffixes(active_policies))
    )
    preferred_sections = (
        narrative_policy_terms(active_policies, "preferred_sections")
        if format_preference_override == "table"
        else narrative_policy_preferred_sections(active_policies)
    )
    return {
        "task_id": next_task_id,
        "metric_family": "narrative_summary",
        "metric_label": str(PLANNING_POLICY.get("hybrid_narrative_metric_label") or ""),
        "query": query,
        "operation_family": "narrative_summary",
        "required_operands": [],
        "preferred_statement_types": [],
        "preferred_sections": preferred_sections,
        "retrieval_queries": list(dict.fromkeys(item for item in retrieval_queries if item)),
        "constraints": {
            "consolidation_scope": consolidation_scope,
            "period_focus": period_focus,
            "entity_scope": "unknown",
            "segment_scope": "none",
            "context_scope": "narrative",
        },
        "intent_override": "qa",
        "format_preference_override": format_preference_override,
    }


def _append_hybrid_narrative_task(
    tasks: List[Dict[str, Any]],
    *,
    query: str,
    intent: str,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    base_tasks = [dict(task) for task in (tasks or [])]
    if not _needs_hybrid_narrative_subtask(query, intent):
        return base_tasks
    if any(_is_narrative_summary_task(task) for task in base_tasks):
        return base_tasks
    next_index = 1
    if base_tasks:
        next_index = max(
            1,
            max(
                (
                    int(match.group(1))
                    for match in (
                        re.match(r"task_(\d+)$", str(task.get("task_id") or "").strip())
                        for task in base_tasks
                    )
                    if match
                ),
                default=0,
            )
            + 1,
        )
    base_tasks.append(
        _build_hybrid_narrative_subtask(
            query=query,
            intent=intent,
            report_scope=report_scope,
            next_task_id=f"task_{next_index}",
        )
    )
    return base_tasks


def _push_narrative_tasks_after_numeric(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ordered = [dict(task) for task in (tasks or [])]
    numeric_task_ids = [
        str(task.get("task_id") or "").strip()
        for task in ordered
        if not _is_narrative_summary_task(task) and str(task.get("task_id") or "").strip()
    ]
    if not numeric_task_ids:
        return ordered

    changed = False
    for task in ordered:
        if not _is_narrative_summary_task(task):
            continue
        task_id = str(task.get("task_id") or "").strip()
        dependencies = [
            _normalise_spaces(str(item or ""))
            for item in (task.get("depends_on") or [])
            if _normalise_spaces(str(item or ""))
        ]
        for dependency_id in numeric_task_ids:
            if dependency_id == task_id or dependency_id in dependencies:
                continue
            dependencies.append(dependency_id)
            changed = True
        task["depends_on"] = dependencies
    if not changed:
        return ordered
    numeric_tasks = [task for task in ordered if not _is_narrative_summary_task(task)]
    narrative_tasks = [task for task in ordered if _is_narrative_summary_task(task)]
    return numeric_tasks + narrative_tasks

def _llm_plan_preserves_segment_sum_shape(base_plan: Dict[str, Any], llm_plan: Dict[str, Any]) -> bool:
    """Reject LLM overrides that destroy deterministic segment-sum structure."""
    base_tasks = [dict(task) for task in (base_plan.get("tasks") or [])]
    has_segment_sum = any(
        str(task.get("operation_family") or "").strip().lower() == "sum"
        and str((task.get("constraints") or {}).get("segment_scope") or "none").strip().lower() == "segment"
        for task in base_tasks
    )
    if not has_segment_sum:
        return True

    llm_tasks = [dict(task) for task in (llm_plan.get("tasks") or [])]
    for task in llm_tasks:
        if str(task.get("operation_family") or "").strip().lower() != "sum":
            continue
        if str((task.get("constraints") or {}).get("segment_scope") or "none").strip().lower() != "segment":
            continue
        addend_roles = [
            str(item.get("role") or "").strip()
            for item in (task.get("required_operands") or [])
            if str(item.get("role") or "").strip().startswith("addend_")
        ]
        if len(addend_roles) >= 2:
            return True
    return False


def _task_concept_role_families(task: Dict[str, Any]) -> set[tuple[str, str]]:
    rows: set[tuple[str, str]] = set()
    for operand in list(task.get("required_operands") or []):
        concept = _normalise_spaces(str(operand.get("concept") or ""))
        role = _normalise_spaces(str(operand.get("role") or ""))
        if role.startswith("numerator"):
            role = "numerator"
        elif role.startswith("denominator"):
            role = "denominator"
        if concept:
            rows.add((concept, role))
    return rows


def _llm_plan_preserves_analysis_shape(base_plan: Dict[str, Any], llm_plan: Dict[str, Any]) -> bool:
    """Reject LLM overrides that erase deterministic ontology analysis hints."""
    base_tasks = [
        dict(task)
        for task in (base_plan.get("tasks") or [])
        if dict(task).get("analysis_hints")
    ]
    if not base_tasks:
        return True

    llm_tasks = [dict(task) for task in (llm_plan.get("tasks") or [])]
    for base_task in base_tasks:
        base_operation = _normalise_spaces(str(base_task.get("operation_family") or ""))
        base_concepts = _task_concept_role_families(base_task)
        if not base_operation or not base_concepts:
            continue
        if any(
            _normalise_spaces(str(task.get("operation_family") or "")) == base_operation
            and base_concepts.issubset(_task_concept_role_families(task))
            for task in llm_tasks
        ):
            continue
        return False
    return True


def _attach_segment_label_to_resolved_spec(spec: Dict[str, Any], segment_label: str) -> Dict[str, Any]:
    updated = dict(spec)
    base_name = str(updated.get("name") or "").strip() or str(PLANNING_POLICY.get("segment_default_metric_name") or "")
    updated["name"] = f"{segment_label} {base_name}".strip()
    aliases = list(updated.get("aliases") or [])
    updated["aliases"] = list(dict.fromkeys([updated["name"], segment_label, base_name, *aliases]))
    binding_policy = dict(updated.get("binding_policy") or {})
    binding_policy["segment_label"] = segment_label
    updated["binding_policy"] = binding_policy
    return updated


def _apply_segment_labels_to_llm_resolved_specs(
    *,
    query: str,
    metric_label: str,
    operation_family: str,
    report_scope: Dict[str, Any],
    resolved_specs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Recover segment-scoped operand identity when the LLM only emits repeated concepts.

    The structured planner can emit the same concept more than once for a
    segment-scoped query. Keep the operation-family/role signal from the LLM,
    but re-attach segment labels from the original query/metric label so
    downstream grounding can distinguish segment rows instead of binding the
    same company-total row twice.
    """
    specs = [dict(spec) for spec in (resolved_specs or [])]
    if not specs:
        return specs

    segment_labels = _extract_segment_labels_from_query(query, report_scope)
    if not segment_labels:
        return specs

    metric_label_text = _normalise_spaces(metric_label)
    segment_labels_lower = [_normalise_spaces(label).lower() for label in segment_labels]

    repeated_same_concept = len({
        str(spec.get("concept") or "").strip()
        for spec in specs
        if str(spec.get("concept") or "").strip()
    }) == 1

    if operation_family in {"sum", "difference", "growth_rate"}:
        roles = [str(spec.get("role") or "").strip() for spec in specs]
        expected_role_prefix = "addend_" if operation_family == "sum" else ""
        valid_difference_roles = {"minuend", "subtrahend"}
        valid_growth_roles = {"current_period", "prior_period"}
        role_shape_ok = (
            all(role.startswith(expected_role_prefix) for role in roles)
            if operation_family == "sum"
            else (
                valid_difference_roles.issubset(set(roles))
                if operation_family == "difference"
                else valid_growth_roles.issubset(set(roles))
            )
        )
        required_segment_labels = 2 if operation_family in {"sum", "difference"} else 1
        if repeated_same_concept and len(specs) >= 2 and role_shape_ok and len(segment_labels) >= required_segment_labels:
            if operation_family == "growth_rate":
                for index, spec in enumerate(specs):
                    specs[index] = _attach_segment_label_to_resolved_spec(spec, segment_labels[0])
            else:
                for index, spec in enumerate(specs):
                    if index >= len(segment_labels):
                        break
                    specs[index] = _attach_segment_label_to_resolved_spec(spec, segment_labels[index])
            return specs

    if operation_family == "ratio" and repeated_same_concept and len(specs) >= 2 and segment_labels:
        for index, spec in enumerate(specs):
            role = str(spec.get("role") or "").strip()
            if not role.startswith("numerator"):
                continue
            specs[index] = _attach_segment_label_to_resolved_spec(spec, segment_labels[0])
            break
        return specs

    if operation_family in {"lookup", "single_value"} and len(specs) == 1:
        matched_segment = next(
            (
                segment_labels[index]
                for index, segment_key in enumerate(segment_labels_lower)
                if segment_key and segment_key in metric_label_text.lower()
            ),
            "",
        )
        if matched_segment:
            specs[0] = _attach_segment_label_to_resolved_spec(specs[0], matched_segment)
    return specs

class FinancialAgentPlanningMixin:
    def _default_format_preference(self, intent: str) -> str:
        return default_format_preference(intent)

    def _align_scope_hints(
        self,
        *,
        companies: Optional[List[str]],
        years: Optional[List[int]],
        report_scope: Dict[str, Any],
    ) -> tuple[List[str], List[int]]:
        scope_company = str(report_scope.get("company") or "").strip()
        scope_year_raw = report_scope.get("year")
        scope_year: Optional[int] = None
        try:
            if scope_year_raw not in (None, ""):
                scope_year = int(scope_year_raw)
        except (TypeError, ValueError):
            scope_year = None

        normalized_companies = [str(item).strip() for item in (companies or []) if str(item).strip()]
        normalized_years: List[int] = []
        for item in list(years or []):
            try:
                value = int(item)
            except (TypeError, ValueError):
                continue
            if value not in normalized_years:
                normalized_years.append(value)

        if scope_company:
            if not normalized_companies:
                normalized_companies = [scope_company]
            elif scope_company not in normalized_companies:
                normalized_companies = [scope_company, *normalized_companies]

        if scope_year is not None:
            if not normalized_years:
                normalized_years = [scope_year]
            elif scope_year not in normalized_years:
                normalized_years = [scope_year, *normalized_years]

        return normalized_companies, normalized_years

    def _classify_query(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Run the lightweight router before any expensive retrieval work."""
        result = self.query_router.route(state["query"])
        return {
            "query_type": result.intent,
            "intent": result.intent,
            "format_preference": result.format_preference,
            "routing_source": result.routing_source,
            "routing_confidence": float(result.routing_confidence or 0.0),
            "routing_scores": dict(result.routing_scores or {}),
        }

    def _extract_entities(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Seed lightweight scope hints before the planner builds the full understanding plan."""
        query = str(state.get("query") or "")
        report_scope = dict(state.get("report_scope") or {})
        query_years = [int(token) for token in re.findall(r"20\d{2}", query)]
        years = list(dict.fromkeys(query_years))
        companies, years = self._align_scope_hints(companies=[], years=years, report_scope=report_scope)
        logger.info(
            "[extract] companies=%s years=%s target_metric=%s",
            companies,
            years,
            "-",
        )
        return {
            "companies": companies,
            "years": years,
            "topic": query,
            "section_filter": None,
            # Keep metric-family hints empty by default so the planner can prefer
            # concept + operation decomposition instead of eagerly collapsing the
            # query into a legacy metric family.
            "target_metric_family": "",
            "target_metric_family_hint": "",
        }

    def _build_llm_concept_numeric_plan(
        self,
        *,
        query: str,
        topic: str,
        intent: str,
        report_scope: Dict[str, Any],
        planner_feedback: str = "",
        existing_tasks: Optional[List[Dict[str, Any]]] = None,
        replan_mode: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Ask the LLM to rewrite an implicit numeric query into concept-level tasks.

        This planner is intentionally constrained:
        - operations are limited to a small closed set
        - operands must reference known ontology concepts
        - output is converted back into the same task IR used elsewhere
        """
        if getattr(self, "low_api_debug", False):
            logger.info("[concept_llm_plan] skipped by low_api_debug")
            return None

        ontology = get_financial_ontology()
        planner_feedback = _normalise_spaces(planner_feedback)
        concept_seed_query = query if not planner_feedback else f"{query}\n{planner_feedback}"
        concept_specs = ontology.concept_specs(concept_seed_query, topic, intent)
        used_full_catalog_fallback = False
        if not concept_specs:
            concept_specs = ontology.all_concept_specs()
            used_full_catalog_fallback = True
        if not concept_specs:
            return None
        concept_spec_by_key = {
            str(spec.get("concept") or "").strip(): dict(spec)
            for spec in concept_specs
            if str(spec.get("concept") or "").strip()
        }
        allowed_concept_keys = {
            str(spec.get("concept") or "").strip()
            for spec in concept_specs
            if str(spec.get("concept") or "").strip()
        }
        for spec in concept_specs:
            allowed_concept_keys.update(
                str(item).strip()
                for item in (spec.get("member_concepts") or [])
                if str(item).strip()
            )
        existing_tasks = [dict(task) for task in (existing_tasks or [])]

        concept_lines: List[str] = []
        for spec in concept_specs:
            concept_lines.append(
                "- {concept} [{kind}]: {name} | aliases={aliases} | expands_to={expands_to} | preferred_statement_types={statement_types} | preferred_sections={sections}".format(
                    concept=str(spec.get("concept") or "").strip(),
                    kind="group" if spec.get("is_group") else "atomic",
                    name=str(spec.get("name") or "").strip(),
                    aliases=", ".join(spec.get("aliases") or []) or "-",
                    expands_to=", ".join(spec.get("member_concepts") or []) or "-",
                    statement_types=", ".join(spec.get("preferred_statement_types") or []) or "-",
                    sections=", ".join(spec.get("preferred_sections") or []) or "-",
                )
            )
        guidance = ontology.planner_guidance
        intent_cues = dict(guidance.get("intent_cues") or {})
        allowed_operations = ["lookup", "sum", "difference", "ratio", "growth_rate", "single_value"]
        existing_task_lines: List[str] = []
        for task in existing_tasks:
            operand_bits = ", ".join(
                f"{str(item.get('concept') or '').strip()}[{str(item.get('role') or '').strip() or '-'}]"
                for item in (task.get("required_operands") or [])
                if str(item.get("concept") or "").strip()
            ) or "-"
            existing_task_lines.append(
                "- {task_id}: {label} | op={operation} | operands={operands}".format(
                    task_id=str(task.get("task_id") or "").strip() or "-",
                    label=str(task.get("metric_label") or task.get("metric_family") or "").strip() or "-",
                    operation=str(task.get("operation_family") or "").strip() or "-",
                    operands=operand_bits,
                )
            )
        mode_specific_rules = (
            str(PLANNING_POLICY.get("concept_planner_replan_rules") or "")
            if replan_mode
            else str(PLANNING_POLICY.get("concept_planner_initial_rule") or "")
        )
        prompt = ChatPromptTemplate.from_template(
            str(PLANNING_POLICY.get("concept_planner_prompt_template") or "")
        )
        structured_llm = self.llm.with_structured_output(ConceptPlannerOutput)
        try:
            prompt_value = prompt.invoke(
                {
                    "allowed_operations": ", ".join(allowed_operations),
                    "intent_cues": json.dumps(intent_cues, ensure_ascii=False),
                    "concept_catalog": "\n".join(concept_lines),
                    "planning_mode": "replan" if replan_mode else "initial",
                    "planner_feedback": planner_feedback or "-",
                    "existing_tasks": "\n".join(existing_task_lines) or "-",
                    "mode_specific_rules": mode_specific_rules,
                    "query": query,
                    "topic": topic,
                    "intent": intent,
                    "report_scope": json.dumps(report_scope, ensure_ascii=False),
                }
            )
            planned: ConceptPlannerOutput = structured_llm.invoke(prompt_value)
        except Exception as exc:
            logger.warning("[concept_llm_plan] structured planner failed: %s", exc)
            return None

        raw_tasks = list(planned.tasks or [])
        if not raw_tasks:
            return None

        validated_raw_tasks: List[Any] = []
        validation_notes: List[str] = []
        for index, raw_task in enumerate(raw_tasks, start=1):
            is_valid, note = self._validate_concept_planner_task(
                raw_task,
                ontology,
                allowed_concept_keys=allowed_concept_keys,
                concept_specs_by_key=concept_spec_by_key,
                support_text=concept_seed_query,
                require_surface_contract_match=used_full_catalog_fallback,
            )
            if not is_valid:
                validation_notes.append(f"invalid_task_{index}:{note}")
                continue
            validated_raw_tasks.append(raw_task)
        if not validated_raw_tasks:
            logger.info("[concept_llm_plan] all candidate tasks rejected by lightweight validator: %s", validation_notes)
            return None

        concept_by_key = {
            str(spec.get("concept") or "").strip(): dict(spec)
            for spec in ontology.all_concept_specs()
        }
        planner_tasks: List[Dict[str, Any]] = []
        for index, raw_task in enumerate(validated_raw_tasks, start=1):
            operation_family = str(raw_task.operation_family or "").strip().lower()
            if operation_family not in allowed_operations:
                continue

            resolved_specs: List[Dict[str, Any]] = []
            for raw_operand in list(raw_task.operands or []):
                concept_key = str(raw_operand.concept or "").strip()
                concept_spec = concept_by_key.get(concept_key)
                if not concept_spec:
                    continue
                resolved_spec = dict(concept_spec)
                resolved_spec["role"] = str(raw_operand.role or "").strip()
                resolved_specs.append(resolved_spec)

            if not resolved_specs:
                continue

            raw_metric_label = str(raw_task.metric_label or "").strip()
            if operation_family in {"lookup", "single_value"} and raw_metric_label and len(resolved_specs) == 1:
                metric_spec = _infer_generic_concept_spec(raw_metric_label, ontology)
                metric_concept = _normalise_spaces(str(metric_spec.get("concept") or ""))
                operand_concept = _normalise_spaces(str(resolved_specs[0].get("concept") or ""))
                if metric_concept and operand_concept and metric_concept != operand_concept:
                    validation_notes.append(
                        f"lookup_metric_operand_mismatch:{raw_metric_label}:{operand_concept}->{metric_concept}"
                    )
                    continue

            resolved_specs = _apply_segment_labels_to_llm_resolved_specs(
                query=query,
                metric_label=raw_metric_label,
                operation_family=operation_family,
                report_scope=report_scope,
                resolved_specs=resolved_specs,
            )

            normalized_operands = _build_concept_required_operands(
                query,
                report_scope,
                resolved_specs,
                operation_family,
            )
            if not normalized_operands:
                continue

            metric_label = raw_metric_label or _build_concept_metric_label(
                query,
                resolved_specs,
                operation_family,
            )
            preferred_statement_types: List[str] = []
            preferred_sections: List[str] = []
            query_statement_types, query_sections = _infer_statement_and_section_hints(query)
            preferred_statement_types.extend(query_statement_types)
            preferred_sections.extend(query_sections)
            for operand in normalized_operands:
                preferred_statement_types.extend(operand.get("preferred_statement_types") or [])
                preferred_sections.extend(operand.get("preferred_sections") or [])
            preferred_statement_types = list(dict.fromkeys(item for item in preferred_statement_types if str(item).strip()))
            preferred_sections = list(dict.fromkeys(item for item in preferred_sections if str(item).strip()))
            constraints = _build_concept_task_constraints(
                query,
                report_scope,
                ontology,
                operand_specs=normalized_operands,
                operation_family=operation_family,
            )
            retrieval_queries = _build_generic_retrieval_queries(
                query=query,
                metric_label=metric_label,
                operand_specs=normalized_operands,
                preferred_sections=preferred_sections,
                report_scope=report_scope,
                constraints=constraints,
            )
            task_query = _build_metric_task_query(
                original_query=query,
                metric_label=metric_label,
                constraints=constraints,
                operand_specs=normalized_operands,
                report_scope=report_scope,
            )
            planner_tasks.append(
                {
                    "task_id": f"task_{index}",
                    "metric_family": f"concept_{operation_family}",
                    "metric_label": metric_label,
                    "query": task_query,
                    "operation_family": operation_family,
                    "result_unit": _infer_concept_ratio_result_unit(query, metric_label, operation_family),
                    "required_operands": normalized_operands,
                    "preferred_statement_types": preferred_statement_types,
                    "preferred_sections": preferred_sections,
                    "retrieval_queries": retrieval_queries,
                    "constraints": constraints,
                }
            )

        if not planner_tasks:
            return None

        execution_tasks = _annotate_task_dependencies(
            planner_tasks,
            report_scope=report_scope,
        )
        planner_tasks = _project_logical_tasks_from_execution_tasks(
            planner_tasks,
            execution_tasks,
        )

        companies, years = self._align_scope_hints(
            companies=list(planned.companies or []),
            years=list(planned.years or []),
            report_scope=report_scope,
        )
        topic_text = _normalise_spaces(str(planned.topic or topic or query))
        section_filter = _normalise_spaces(str(planned.section_filter or "")) or None

        return {
            "status": "concept_fallback",
            "fallback_to_general_search": False,
            "companies": companies,
            "years": years,
            "topic": topic_text,
            "section_filter": section_filter,
            "planned_metric_families": [
                str(task.get("metric_family") or "").strip()
                for task in planner_tasks
                if str(task.get("metric_family") or "").strip()
            ],
            "tasks": planner_tasks,
            "planner_notes": [
                "concept_llm_planner",
                *(["planner_replan"] if replan_mode else []),
                *validation_notes,
                str(planned.rationale or "").strip(),
            ],
        }

    def _validate_concept_planner_task(
        self,
        raw_task: Any,
        ontology: Any,
        allowed_concept_keys: Optional[set[str]] = None,
        concept_specs_by_key: Optional[Dict[str, Dict[str, Any]]] = None,
        support_text: str = "",
        require_surface_contract_match: bool = False,
    ) -> tuple[bool, str]:
        """Perform a tiny contract check on planner output before runtime uses it.

        This is intentionally narrow: it validates shape and ontology membership,
        not financial correctness.
        """
        operation_family = str(getattr(raw_task, "operation_family", "") or "").strip().lower()
        allowed_operations = {"lookup", "sum", "difference", "ratio", "growth_rate", "single_value"}
        if operation_family not in allowed_operations:
            return False, f"unsupported_operation:{operation_family or '-'}"

        raw_operands = list(getattr(raw_task, "operands", []) or [])
        if not raw_operands:
            return False, "missing_operands"

        roles = [str(getattr(item, "role", "") or "").strip() for item in raw_operands]
        for item in raw_operands:
            concept_key = str(getattr(item, "concept", "") or "").strip()
            if not concept_key or not ontology.has_concept_key(concept_key):
                return False, f"unknown_concept:{concept_key or '-'}"
            if allowed_concept_keys and concept_key not in allowed_concept_keys:
                return False, f"concept_not_available:{concept_key}"
            if require_surface_contract_match:
                spec = dict((concept_specs_by_key or {}).get(concept_key) or {})
                surface_contract = dict(spec.get("surface_contract") or {})
                positive_terms = [
                    _normalise_spaces(str(term or ""))
                    for term in (surface_contract.get("positive") or [])
                    if _normalise_spaces(str(term or ""))
                ]
                normalized_support = _normalise_spaces(support_text)
                if positive_terms and not any(term in normalized_support for term in positive_terms):
                    return False, f"surface_contract_missing:{concept_key}"

        if operation_family == "ratio":
            if not any(role.startswith("numerator") for role in roles):
                return False, "ratio_missing_numerator"
            if not any(role.startswith("denominator") for role in roles):
                return False, "ratio_missing_denominator"
            invalid_role = next(
                (role for role in roles if role and not (role.startswith("numerator") or role.startswith("denominator"))),
                "",
            )
            if invalid_role:
                return False, f"ratio_invalid_role:{invalid_role}"
        elif operation_family == "sum":
            invalid_role = next((role for role in roles if role and not role.startswith("addend")), "")
            if invalid_role:
                return False, f"sum_invalid_role:{invalid_role}"
        elif operation_family == "difference":
            if len(raw_operands) != 2:
                return False, "difference_requires_two_operands"
            valid_roles = {"", "minuend", "subtrahend", "current_period", "prior_period"}
            invalid_role = next((role for role in roles if role not in valid_roles), "")
            if invalid_role:
                return False, f"difference_invalid_role:{invalid_role}"
        elif operation_family == "growth_rate":
            if len(raw_operands) != 2:
                return False, "growth_rate_requires_two_operands"
            valid_roles = {"", "current_period", "prior_period"}
            invalid_role = next((role for role in roles if role not in valid_roles), "")
            if invalid_role:
                return False, f"growth_rate_invalid_role:{invalid_role}"

        return True, "ok"

    def _planner_task_signature(self, task: Dict[str, Any]) -> tuple:
        required_operands = tuple(
            (
                str(item.get("concept") or "").strip(),
                str(item.get("role") or "").strip(),
                str(item.get("label") or "").strip(),
            )
            for item in (task.get("required_operands") or [])
        )
        constraints = dict(task.get("constraints") or {})
        return (
            str(task.get("metric_family") or "").strip(),
            str(task.get("metric_label") or "").strip(),
            str(task.get("operation_family") or "").strip(),
            required_operands,
            str(constraints.get("consolidation_scope") or "").strip(),
            str(constraints.get("period_focus") or "").strip(),
            str(constraints.get("entity_scope") or "").strip(),
            str(constraints.get("segment_scope") or "").strip(),
        )

    def _next_planner_task_index(self, tasks: List[Dict[str, Any]]) -> int:
        max_index = 0
        for task in tasks:
            match = re.match(r"task_(\d+)$", str(task.get("task_id") or "").strip())
            if match:
                max_index = max(max_index, int(match.group(1)))
        return max_index + 1

    def _append_replanned_tasks(
        self,
        existing_tasks: List[Dict[str, Any]],
        patch_tasks: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        merged_tasks = [dict(task) for task in existing_tasks]
        accepted_patch_tasks: List[Dict[str, Any]] = []
        seen_signatures = {
            self._planner_task_signature(task)
            for task in merged_tasks
        }
        next_index = self._next_planner_task_index(merged_tasks)
        for task in patch_tasks:
            signature = self._planner_task_signature(task)
            if signature in seen_signatures:
                continue
            accepted = dict(task)
            accepted["task_id"] = f"task_{next_index}"
            next_index += 1
            merged_tasks.append(accepted)
            accepted_patch_tasks.append(accepted)
            seen_signatures.add(signature)
        return merged_tasks, accepted_patch_tasks

    def _plan_semantic_numeric_tasks(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Build calculation subtasks or explicitly fall back to general search.

        This is the hand-off point between generic QA and the structured
        numeric pipeline. Downstream phases treat `active_subtask` as the
        current unit of calculation work when tasks are present.
        """
        intent = state.get("intent") or state.get("query_type", "qa")
        query = state["query"]
        topic = state.get("topic") or query
        report_scope = dict(state.get("report_scope") or {})
        planner_feedback = _normalise_spaces(str(state.get("planner_feedback") or ""))
        planner_mode = "replan" if str(state.get("planner_mode") or "").strip() == "replan" or planner_feedback else "initial"
        plan_loop_count = int(state.get("plan_loop_count") or 0)
        target_metric_family = str(
            state.get("target_metric_family_hint")
            or state.get("target_metric_family")
            or ""
        )

        if intent not in {"comparison", "trend", "numeric_fact"}:
            return {
                "semantic_plan": {
                    "status": "fallback_general_search",
                    "fallback_to_general_search": True,
                    "planned_metric_families": [],
                    "tasks": [],
                    "planner_notes": ["non_numeric_intent"],
                },
                "planner_mode": "initial",
                "planner_feedback": "",
                "plan_loop_count": plan_loop_count,
                "calc_subtasks": [],
                "planned_metric_families": [],
                "retrieval_queries": [query],
                "active_subtask_index": 0,
                "active_subtask": {},
                "subtask_results": [],
                "subtask_debug_trace": {"reason": "non_numeric_intent"},
                "subtask_loop_complete": False,
                "tasks": list(state.get("tasks") or []),
                "artifacts": list(state.get("artifacts") or []),
            }

        if planner_mode == "replan":
            existing_execution_tasks = [dict(task) for task in (state.get("calc_subtasks") or [])]
            existing_tasks = [
                dict(task)
                for task in (dict(state.get("semantic_plan") or {}).get("tasks") or existing_execution_tasks)
            ]
            existing_subtask_results = [dict(item) for item in (state.get("subtask_results") or [])]
            existing_plan = dict(state.get("semantic_plan") or {})
            llm_plan = self._build_llm_concept_numeric_plan(
                query=query,
                topic=topic,
                intent=intent,
                report_scope=report_scope,
                planner_feedback=planner_feedback,
                existing_tasks=existing_tasks,
                replan_mode=True,
            )
            patch_tasks = [dict(task) for task in (llm_plan or {}).get("tasks", [])]
            merged_tasks, appended_tasks = self._append_replanned_tasks(existing_tasks, patch_tasks)
            merged_tasks = _append_hybrid_narrative_task(
                merged_tasks,
                query=query,
                intent=intent,
                report_scope=report_scope,
            )
            execution_tasks = _annotate_task_dependencies(
                merged_tasks,
                report_scope=report_scope,
            )
            execution_tasks = _push_narrative_tasks_after_numeric(execution_tasks)
            semantic_plan_tasks = _project_logical_tasks_from_execution_tasks(
                merged_tasks,
                execution_tasks,
            )
            appended_task_ids = {
                str(task.get("task_id") or "").strip()
                for task in appended_tasks
                if str(task.get("task_id") or "").strip()
            }
            appended_execution_ids = _dependency_closure_task_ids(execution_tasks, list(appended_task_ids))
            completed_task_ids = {
                str(item.get("task_id") or "").strip()
                for item in existing_subtask_results
                if str(item.get("task_id") or "").strip()
            }
            replanned_execution_tasks = [
                dict(task)
                for task in execution_tasks
                if str(task.get("task_id") or "").strip() in appended_execution_ids
            ]
            pending_execution_tasks = [
                dict(task)
                for task in replanned_execution_tasks
                if str(task.get("task_id") or "").strip() not in completed_task_ids
            ]
            planned_metric_families = [
                str(task.get("metric_family") or "").strip()
                for task in semantic_plan_tasks
                if str(task.get("metric_family") or "").strip()
            ]
            planner_notes = list(dict.fromkeys([
                *list(existing_plan.get("planner_notes") or []),
                "planner_replan",
                *(list((llm_plan or {}).get("planner_notes") or [])),
                *(["planner_replan_no_patch"] if not appended_tasks else []),
            ]))
            retrieval_queries = [query]
            for task in pending_execution_tasks or replanned_execution_tasks:
                retrieval_queries.extend(
                    str(item).strip()
                    for item in (task.get("retrieval_queries") or [])
                    if str(item).strip()
                )
            retrieval_queries = list(dict.fromkeys(item for item in retrieval_queries if item))
            active_subtask = dict((pending_execution_tasks or replanned_execution_tasks or [dict(state.get("active_subtask") or {})])[0])
            if pending_execution_tasks or replanned_execution_tasks:
                active_subtask_index = next(
                    (index for index, task in enumerate(execution_tasks) if str(task.get("task_id") or "") == str(active_subtask.get("task_id") or "")),
                    len(existing_execution_tasks),
                )
            else:
                active_subtask_index = int(state.get("active_subtask_index") or 0)
            plan_status = str((llm_plan or {}).get("status") or existing_plan.get("status") or "concept_fallback")
            semantic_plan = {
                "status": plan_status,
                "fallback_to_general_search": False,
                "planned_metric_families": planned_metric_families,
                "tasks": semantic_plan_tasks,
                "planner_notes": planner_notes,
            }
            companies, years = self._align_scope_hints(
                companies=list((llm_plan or {}).get("companies") or state.get("companies") or []),
                years=list((llm_plan or {}).get("years") or state.get("years") or []),
                report_scope=report_scope,
            )
            topic_text = _normalise_spaces(
                str((llm_plan or {}).get("topic") or state.get("topic") or query)
            )
            section_filter = (
                _normalise_spaces(str((llm_plan or {}).get("section_filter") or ""))
                or state.get("section_filter")
            )
            task_records = list(state.get("tasks") or [])
            artifacts = list(state.get("artifacts") or [])
            semantic_artifact_id = f"semantic_plan:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=semantic_artifact_id,
                task_id=str(active_subtask.get("task_id") or "semantic_plan"),
                kind=ArtifactKind.SEMANTIC_PLAN,
                status=plan_status,
                summary=f"replanned {len(appended_tasks)} additional numeric task(s)",
                payload={
                    "semantic_plan": semantic_plan,
                    "retrieval_queries": retrieval_queries,
                    "planner_feedback": planner_feedback,
                    "base_task_count": len(existing_tasks),
                    "appended_task_count": len(appended_tasks),
                    "execution_task_count": len(execution_tasks),
                },
            )
            for task in pending_execution_tasks or replanned_execution_tasks:
                task_records = _upsert_task(
                    task_records,
                    task_id=str(task.get("task_id") or ""),
                    kind=TaskKind.CALCULATION,
                    label=str(task.get("metric_label") or task.get("metric_family") or "calculation"),
                    status=TaskStatus.PENDING,
                    query=str(task.get("query") or ""),
                    metric_family=str(task.get("metric_family") or ""),
                    constraints=dict(task.get("constraints") or {}),
                    artifact_id=semantic_artifact_id,
                )
            logger.info(
                "[semantic_plan_replan] base_tasks=%s appended=%s retrieval_queries=%s feedback=%s",
                len(existing_tasks),
                len(replanned_execution_tasks),
                len(retrieval_queries),
                planner_feedback,
            )
            return {
                "semantic_plan": semantic_plan,
                "planner_mode": "initial",
                "planner_feedback": "",
                "plan_loop_count": plan_loop_count + 1,
                "companies": companies,
                "years": years,
                "topic": topic_text,
                "section_filter": section_filter,
                "calc_subtasks": execution_tasks,
                "planned_metric_families": planned_metric_families,
                "retrieval_queries": retrieval_queries,
                "active_subtask_index": active_subtask_index,
                "active_subtask": active_subtask,
                "subtask_results": existing_subtask_results,
                "subtask_debug_trace": {
                    **dict(state.get("subtask_debug_trace") or {}),
                    "status": plan_status,
                    "task_count": len(execution_tasks),
                    "planner_notes": planner_notes,
                    "planner_feedback": planner_feedback,
                    "planner_replan": True,
                    "appended_task_count": len(replanned_execution_tasks),
                },
                "subtask_loop_complete": False if replanned_execution_tasks else bool(state.get("subtask_loop_complete", False)),
                "planner_debug_trace": {
                    **dict(state.get("planner_debug_trace") or {}),
                    "planner_replan": True,
                    "planner_feedback": planner_feedback,
                    "base_task_count": len(existing_tasks),
                    "appended_task_count": len(replanned_execution_tasks),
                },
                "tasks": task_records,
                "artifacts": artifacts,
            }

        plan = _build_semantic_numeric_plan(
            query=query,
            topic=topic,
            intent=intent,
            report_scope=report_scope,
            target_metric_family=target_metric_family,
        )
        if str(plan.get("status") or "") in {"concept_fallback", "heuristic_fallback", "fallback_general_search"}:
            llm_plan = self._build_llm_concept_numeric_plan(
                query=query,
                topic=topic,
                intent=intent,
                report_scope=report_scope,
            )
            if llm_plan:
                if _llm_plan_preserves_segment_sum_shape(plan, llm_plan) and _llm_plan_preserves_analysis_shape(plan, llm_plan):
                    plan = llm_plan
                else:
                    planner_notes = list(plan.get("planner_notes") or [])
                    planner_notes.append("concept_llm_plan_rejected_shape")
                    plan["planner_notes"] = list(dict.fromkeys(planner_notes))
        logical_tasks = [dict(task) for task in (plan.get("tasks") or [])]
        logical_tasks = _append_hybrid_narrative_task(
            logical_tasks,
            query=query,
            intent=intent,
            report_scope=report_scope,
        )
        tasks = _annotate_task_dependencies(
            logical_tasks,
            report_scope=report_scope,
        )
        tasks = _push_narrative_tasks_after_numeric(tasks)
        plan["tasks"] = _project_logical_tasks_from_execution_tasks(logical_tasks, tasks)
        planned_metric_families = [
            str(task.get("metric_family") or "").strip()
            for task in (plan.get("tasks") or [])
            if str(task.get("metric_family") or "").strip()
        ]
        plan["planned_metric_families"] = planned_metric_families
        companies, years = self._align_scope_hints(
            companies=list(plan.get("companies") or state.get("companies") or []),
            years=list(plan.get("years") or state.get("years") or []),
            report_scope=report_scope,
        )
        topic_text = _normalise_spaces(str(plan.get("topic") or topic or query))
        section_filter = _normalise_spaces(str(plan.get("section_filter") or "")) or state.get("section_filter")
        retrieval_queries = [query]
        for task in tasks:
            retrieval_queries.extend(str(item).strip() for item in (task.get("retrieval_queries") or []) if str(item).strip())
        retrieval_queries = list(dict.fromkeys(item for item in retrieval_queries if item))
        active_subtask = dict(tasks[0]) if tasks else {}
        task_records = list(state.get("tasks") or [])
        artifacts = list(state.get("artifacts") or [])
        semantic_artifact_id = f"semantic_plan:{len(artifacts) + 1:03d}"
        artifacts = _append_artifact(
            artifacts,
            artifact_id=semantic_artifact_id,
            task_id=str(active_subtask.get("task_id") or "semantic_plan"),
            kind=ArtifactKind.SEMANTIC_PLAN,
            status=str(plan.get("status") or "ok"),
            summary=f"planned {len(tasks)} numeric task(s)",
            payload={"semantic_plan": plan, "retrieval_queries": retrieval_queries},
        )
        for task in tasks:
            task_records = _upsert_task(
                task_records,
                task_id=str(task.get("task_id") or ""),
                kind=TaskKind.CALCULATION,
                label=str(task.get("metric_label") or task.get("metric_family") or "calculation"),
                status=TaskStatus.PENDING,
                query=str(task.get("query") or ""),
                metric_family=str(task.get("metric_family") or ""),
                constraints=dict(task.get("constraints") or {}),
                artifact_id=semantic_artifact_id,
            )
        logger.info(
            "[semantic_plan] status=%s tasks=%s retrieval_queries=%s",
            plan.get("status"),
            len(tasks),
            len(retrieval_queries),
        )
        return {
            "semantic_plan": plan,
            "planner_mode": "initial",
            "planner_feedback": "",
            "plan_loop_count": plan_loop_count,
            "companies": companies,
            "years": years,
            "topic": topic_text,
            "section_filter": section_filter,
            "calc_subtasks": tasks,
            "planned_metric_families": planned_metric_families,
            "retrieval_queries": retrieval_queries,
            "active_subtask_index": 0,
            "active_subtask": active_subtask,
            "subtask_results": [],
            "subtask_debug_trace": {
                "status": plan.get("status"),
                "task_count": len(tasks),
                "planner_notes": list(plan.get("planner_notes") or []),
            },
            "subtask_loop_complete": False,
            "tasks": task_records,
            "artifacts": artifacts,
        }

    def _calc_query(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        return str(active_subtask.get("query") or state["query"])

    def _calc_topic(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        return str(
            active_subtask.get("metric_label")
            or active_subtask.get("query")
            or state.get("topic")
            or state["query"]
        )

    def _calc_metric_family(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        return str(active_subtask.get("metric_family") or "")

    def _build_aggregate_calculation_projection(
        self,
        ordered_results: List[Dict[str, Any]],
        final_answer: str,
    ) -> Dict[str, Any]:
        aggregate_projection = _build_aggregate_calculation_projection(ordered_results, final_answer)
        aggregate_evidence: List[Dict[str, Any]] = []
        seen_evidence_ids: set[str] = set()

        for row in ordered_results:
            for evidence in list(row.get("runtime_evidence") or []):
                evidence_row = dict(evidence)
                evidence_id = str(evidence_row.get("evidence_id") or "").strip()
                dedupe_key = evidence_id or _normalise_spaces(
                    " ".join(
                        part
                        for part in [
                            str(evidence_row.get("source_anchor") or "").strip(),
                            str(evidence_row.get("quote_span") or "").strip(),
                            str(evidence_row.get("raw_row_text") or "").strip(),
                            str(evidence_row.get("claim") or "").strip(),
                        ]
                        if part
                    )
                )
                if dedupe_key and dedupe_key in seen_evidence_ids:
                    continue
                if dedupe_key:
                    seen_evidence_ids.add(dedupe_key)
                aggregate_evidence.append(evidence_row)
        return {
            "calculation_operands": aggregate_projection["calculation_operands"],
            "calculation_plan": aggregate_projection["calculation_plan"],
            "calculation_result": aggregate_projection["calculation_result"],
            "evidence_items": aggregate_evidence,
        }

    def _project_legacy_calculation_fields(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Project ledger-backed traces into the legacy flat calculation view."""
        return _resolve_runtime_calculation_trace(dict(state))

    def _nested_subtask_rows(self, calculation_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []

        def _walk(current: Dict[str, Any]) -> None:
            for child in list(current.get("subtask_results") or []):
                if not isinstance(child, dict):
                    continue
                child_row = dict(child)
                rows.append(child_row)
                child_result = dict(child_row.get("calculation_result") or {})
                if child_result:
                    _walk(child_result)

        _walk(dict(calculation_result or {}))
        return rows

    def _subtask_row_has_material(self, row: Dict[str, Any]) -> bool:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        for slot_name in ("primary_value", "current_value", "prior_value", "delta_value"):
            if _slot_has_material(dict(answer_slots.get(slot_name) or {})):
                return True
        if str(calculation_result.get("rendered_value") or row.get("answer") or "").strip():
            return True
        return bool(list(calculation_result.get("source_row_ids") or []))

    def _subtask_row_operation_family(self, row: Dict[str, Any]) -> str:
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
        self,
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
        operation_family = self._subtask_row_operation_family(row)
        status = _normalise_spaces(
            str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
        ).lower()

        if active_task_id and task_id and active_task_id != task_id:
            return (0, 0, 0, 0, 0, 0)

        status_rank = {"ok": 4, "partial": 2, "ready": 2}.get(status, 0)
        material_rank = 1 if self._subtask_row_has_material(row) else 0
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

    def _promote_nested_subtask_result_if_more_specific(
        self,
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
        for row in self._nested_subtask_rows(calculation_result):
            score = self._subtask_row_specificity_score(row, active_subtask=active_subtask)
            if score[:2] == (0, 0):
                continue
            candidates.append((score, row))
        if not candidates:
            return answer, status, calculation_result

        candidates.sort(key=lambda item: item[0], reverse=True)
        best_score, best_row = candidates[0]
        current_material = self._subtask_row_has_material(
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
        if not best_result or self._subtask_row_operation_family(best_row) == "aggregate_subtasks":
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

    def _capture_current_subtask_result(self, state: FinancialAgentState) -> Dict[str, Any]:
        active_subtask = dict(state.get("active_subtask") or {})
        if not active_subtask:
            return {}
        projected = _project_task_trace_from_state(state, str(active_subtask.get("task_id") or ""))
        calculation_operands = list(projected.get("calculation_operands") or [])
        calculation_plan = dict(projected.get("calculation_plan") or {})
        calculation_result = dict(projected.get("calculation_result") or {})
        reconciliation_result = dict(projected.get("reconciliation_result") or {})
        runtime_evidence = [dict(item) for item in (state.get("evidence_items") or [])]
        answer = _normalise_spaces(str(state.get("answer") or state.get("compressed_answer") or ""))
        selected_claim_ids = list(state.get("selected_claim_ids") or [])
        status = str(
            calculation_result.get("status")
            or reconciliation_result.get("status")
            or ("ok" if answer else "unknown")
        )
        answer, status, calculation_result = self._promote_nested_subtask_result_if_more_specific(
            active_subtask=active_subtask,
            answer=answer,
            status=status,
            calculation_result=calculation_result,
        )
        if str(active_subtask.get("operation_family") or "").strip().lower() == "narrative_summary" and runtime_evidence:
            deterministic_dividend_answer = self._compose_dividend_policy_hybrid_answer(
                query=str(active_subtask.get("query") or state["query"]),
                evidence_items=runtime_evidence,
            )
            if deterministic_dividend_answer:
                answer = _normalise_spaces(str(deterministic_dividend_answer.get("answer") or "")) or answer
                selected_claim_ids = list(deterministic_dividend_answer.get("supporting_claim_ids") or []) or selected_claim_ids
                if answer and str(calculation_result.get("status") or "").strip().lower() in {"", "partial", "unknown"}:
                    calculation_result = {
                        **calculation_result,
                        "status": "ok",
                        "rendered_value": answer,
                        "formatted_result": answer,
                        "operation_family": "narrative_summary",
                    }
        primary_before_synthesis = dict((calculation_result.get("answer_slots") or {}).get("primary_value") or {})
        active_operation = _normalise_spaces(str(active_subtask.get("operation_family") or "")).lower()
        active_metric_family = _normalise_spaces(str(active_subtask.get("metric_family") or "")).lower()
        lookup_subtask_in_loop = active_metric_family == "concept_lookup" and len(list(state.get("calc_subtasks") or [])) > 1
        if (
            not _slot_has_material(primary_before_synthesis)
            and calculation_operands
            and (active_operation in {"lookup", "single_value"} or lookup_subtask_in_loop)
        ):
            matching_operands = [
                dict(operand)
                for operand in calculation_operands
                if _lookup_operand_matches_active_task(dict(operand), active_subtask)
            ]
            operand_row = dict(matching_operands[0]) if matching_operands else {}
        else:
            operand_row = {}
        if operand_row:
            source_ids = _clean_source_row_ids([
                operand_row.get("source_row_id"),
                operand_row.get("source_row_ids"),
            ])
            primary_slot_from_operand = {
                "status": "ok",
                "role": "primary_value",
                "label": _normalise_spaces(
                    str(operand_row.get("label") or operand_row.get("matched_operand_label") or active_subtask.get("metric_label") or "")
                ),
                "concept": _normalise_spaces(
                    str(operand_row.get("concept") or operand_row.get("matched_operand_concept") or "")
                ),
                "period": _normalise_spaces(str(operand_row.get("period") or operand_row.get("period_hint") or "")),
                "raw_value": _normalise_spaces(str(operand_row.get("raw_value") or operand_row.get("value") or "")),
                "raw_unit": _normalise_spaces(str(operand_row.get("raw_unit") or "")),
                "normalized_value": operand_row.get("normalized_value"),
                "normalized_unit": _normalise_spaces(str(operand_row.get("normalized_unit") or "UNKNOWN")).upper()
                or "UNKNOWN",
                "rendered_value": _normalise_spaces(str(operand_row.get("rendered_value") or "")),
                "source_row_id": source_ids[0] if source_ids else "",
                "source_row_ids": list(dict.fromkeys(source_ids)),
                "source_anchor": _normalise_spaces(str(operand_row.get("source_anchor") or "")),
                "source_claim_ids": list(operand_row.get("source_claim_ids") or []),
            }
            rendered_value = _normalise_spaces(str(primary_slot_from_operand.get("rendered_value") or ""))
            calculation_result = {
                **calculation_result,
                "status": "ok",
                "operation_family": "lookup",
                "rendered_value": rendered_value,
                "formatted_result": answer or rendered_value,
                "source_row_ids": primary_slot_from_operand["source_row_ids"],
                "answer_slots": validate_answer_slots_payload(
                    {
                        **dict(calculation_result.get("answer_slots") or {}),
                        "operation_family": "lookup",
                        "primary_value": primary_slot_from_operand,
                    }
                ),
            }
            primary_before_synthesis = primary_slot_from_operand
        if (
            not _slot_has_material(primary_before_synthesis)
            and (not calculation_operands or not operand_row)
            and (active_operation in {"lookup", "single_value"} or lookup_subtask_in_loop)
        ):
            calculation_result = _synthesize_lookup_answer_slot_from_prose(
                active_subtask=active_subtask,
                answer=answer,
                calculation_result=calculation_result,
                selected_claim_ids=selected_claim_ids,
            )
        primary_slot = dict((calculation_result.get("answer_slots") or {}).get("primary_value") or {})
        if primary_slot and _slot_has_material(primary_slot):
            primary_source_ids = set(_clean_source_row_ids([
                primary_slot.get("source_row_id"),
                primary_slot.get("source_row_ids"),
            ]))
            slot_evidence = next(
                (
                    dict(item)
                    for item in runtime_evidence
                    if str(item.get("evidence_id") or "").strip() in primary_source_ids
                ),
                None,
            )
            if not slot_evidence:
                slot_evidence = _lookup_slot_supporting_doc_evidence(
                active_subtask=active_subtask,
                slot=primary_slot,
                docs=list(state.get("retrieved_docs", []) or []) + list(state.get("seed_retrieved_docs", []) or []),
                )
            if slot_evidence:
                evidence_id = str(slot_evidence.get("evidence_id") or "").strip()
                existing_ids = {
                    str(item.get("evidence_id") or "").strip()
                    for item in runtime_evidence
                    if isinstance(item, dict)
                }
                if evidence_id:
                    slot_source_ids = _clean_source_row_ids([
                        primary_slot.get("source_row_id"),
                        primary_slot.get("source_row_ids"),
                        evidence_id,
                    ])
                    primary_slot["source_row_id"] = slot_source_ids[0] if slot_source_ids else evidence_id
                    primary_slot["source_row_ids"] = slot_source_ids or [evidence_id]
                    if not _normalise_spaces(str(primary_slot.get("source_anchor") or "")):
                        primary_slot["source_anchor"] = _normalise_spaces(str(slot_evidence.get("source_anchor") or ""))
                    primary_slot = _refine_lookup_slot_unit_from_evidence(primary_slot, slot_evidence)
                    if calculation_operands:
                        refined_operands: List[Dict[str, Any]] = []
                        primary_ids = set(_clean_source_row_ids([primary_slot.get("source_row_ids")]))
                        for operand in calculation_operands:
                            operand_row = dict(operand)
                            operand_ids = set(_clean_source_row_ids([
                                operand_row.get("source_row_id"),
                                operand_row.get("source_row_ids"),
                            ]))
                            if (
                                _normalise_spaces(str(operand_row.get("raw_value") or ""))
                                == _normalise_spaces(str(primary_slot.get("raw_value") or ""))
                                and (not primary_ids or not operand_ids or bool(primary_ids & operand_ids))
                            ):
                                operand_row["raw_unit"] = _normalise_spaces(str(primary_slot.get("raw_unit") or ""))
                                operand_row["normalized_value"] = primary_slot.get("normalized_value")
                                operand_row["normalized_unit"] = _normalise_spaces(
                                    str(primary_slot.get("normalized_unit") or "UNKNOWN")
                                ).upper()
                                operand_row["rendered_value"] = _normalise_spaces(
                                    str(primary_slot.get("rendered_value") or "")
                                )
                                if not _normalise_spaces(str(operand_row.get("source_anchor") or "")):
                                    operand_row["source_anchor"] = _normalise_spaces(str(primary_slot.get("source_anchor") or ""))
                            refined_operands.append(operand_row)
                        calculation_operands = refined_operands
                    if evidence_id not in existing_ids:
                        runtime_evidence.append(slot_evidence)
                    if evidence_id not in selected_claim_ids:
                        selected_claim_ids.append(evidence_id)
                calculation_result["answer_slots"]["primary_value"] = primary_slot
                calculation_result["source_row_ids"] = list(primary_slot.get("source_row_ids") or [])
                if primary_slot.get("rendered_value"):
                    calculation_result["rendered_value"] = _normalise_spaces(str(primary_slot.get("rendered_value") or ""))
        if primary_slot and not calculation_operands:
            calculation_operands = [
                {
                    "operand_id": _normalise_spaces(str(primary_slot.get("role") or "primary_value")) or "primary_value",
                    "matched_operand_role": _normalise_spaces(str(primary_slot.get("role") or "primary_value")) or "primary_value",
                    "label": _normalise_spaces(str(primary_slot.get("label") or active_subtask.get("metric_label") or "")),
                    "concept": _normalise_spaces(str(primary_slot.get("concept") or active_subtask.get("metric_family") or "")),
                    "period": _normalise_spaces(str(primary_slot.get("period") or "")),
                    "raw_value": _normalise_spaces(str(primary_slot.get("raw_value") or "")),
                    "raw_unit": _normalise_spaces(str(primary_slot.get("raw_unit") or "")),
                    "normalized_value": primary_slot.get("normalized_value"),
                    "normalized_unit": _normalise_spaces(str(primary_slot.get("normalized_unit") or "UNKNOWN")),
                    "rendered_value": _normalise_spaces(str(primary_slot.get("rendered_value") or "")),
                    "source_row_id": _normalise_spaces(str(primary_slot.get("source_row_id") or "")),
                    "source_row_ids": _clean_source_row_ids([primary_slot.get("source_row_ids")]),
                    "source_anchor": _normalise_spaces(str(primary_slot.get("source_anchor") or "")),
                    "source_claim_ids": list(primary_slot.get("source_claim_ids") or []),
                }
            ]
        status = str(
            calculation_result.get("status")
            or reconciliation_result.get("status")
            or status
            or ("ok" if answer else "unknown")
        )
        return {
            "task_id": str(active_subtask.get("task_id") or ""),
            "metric_family": str(active_subtask.get("metric_family") or ""),
            "metric_label": str(active_subtask.get("metric_label") or ""),
            "query": str(active_subtask.get("query") or state["query"]),
            "answer": answer,
            "status": status,
            "artifact_ids": list(projected.get("artifact_ids") or []),
            "selected_claim_ids": selected_claim_ids,
            "runtime_evidence": runtime_evidence,
            "calculation_operands": calculation_operands,
            "calculation_plan": calculation_plan,
            "calculation_result": calculation_result,
            "reconciliation_result": reconciliation_result,
        }

    def _upsert_subtask_result(
        self,
        existing: List[Dict[str, Any]],
        current: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not current:
            return list(existing or [])
        current_task_id = str(current.get("task_id") or "").strip()
        rows: List[Dict[str, Any]] = []
        replaced = False
        for row in existing or []:
            row_task_id = str(row.get("task_id") or "").strip()
            if current_task_id and row_task_id == current_task_id:
                rows.append(current)
                replaced = True
            else:
                rows.append(row)
        if not replaced:
            rows.append(current)
        return rows

