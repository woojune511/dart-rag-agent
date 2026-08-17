"""
Semantic planning and reconciliation helper functions for the financial graph
agent.

This module still owns the cross-cutting task planning and candidate scoring
logic. Narrower runtime primitives such as text normalization, retrieval hints,
surface contracts, row parsing, structured-cell scoring, and scope policy live
in dedicated owner modules and are imported here only when the planning or
reconciliation helpers need them directly.
"""

from functools import lru_cache
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.config import get_financial_ontology
from src.config.retrieval_policy import (
    CONSOLIDATION_SCOPE_POLICY,
    EXPLICIT_RATIO_DEFINITION_POLICY,
    CONCEPT_METRIC_LABEL_POLICY,
    GENERIC_METRIC_ALIAS_SUBSTITUTIONS,
    GENERIC_OPERAND_LABEL_POLICY,
    GENERIC_PERIOD_OPERAND_POLICY,
    GENERIC_UNIT_FAMILY_POLICY,
    HELPER_RUNTIME_POLICY,
    KOREAN_PERIOD_COMPARISON_RE_FRAGMENT,
    KOREAN_PERIOD_PREFIX_RE_FRAGMENT,
    KOREAN_PERIOD_RATE_METRIC_SUFFIX_RE_FRAGMENT,
    KOREAN_SEGMENT_LABEL_ANCHORS,
    KOREAN_SEGMENT_LABEL_BLOCKED_EXACT_LABELS,
    KOREAN_SEGMENT_LABEL_BLOCKED_TOKENS,
    KOREAN_SEGMENT_LABEL_BOUNDARIES,
    KOREAN_SEGMENT_LABEL_MARKERS,
    KOREAN_SEGMENT_LABEL_PAREN_RE_FRAGMENT,
    KOREAN_SEGMENT_LABEL_PERIOD_PREFIX_RE_FRAGMENT,
    KOREAN_SEGMENT_LABEL_PERIOD_RE_FRAGMENT,
    KOREAN_SEGMENT_LABEL_REPORT_TERMS,
    KOREAN_SEGMENT_LABEL_SCOPE_TOKENS,
    KOREAN_SEGMENT_LABEL_SPLIT_RE_FRAGMENT,
    KOREAN_SEGMENT_LABEL_TOKEN_PATTERNS,
    KOREAN_SEGMENT_LABEL_TRAILING_PERIOD_RE_FRAGMENT,
    METRIC_TASK_QUERY_POLICY,
    NARRATIVE_BASE_RETRIEVAL_SUFFIXES,
    OPERATION_FAMILY_QUERY_POLICIES,
    PLANNING_POLICY,
    TASK_CONSTRAINT_POLICY,
    active_narrative_policies,
    narrative_policy_preferred_sections,
    narrative_policy_query_suffixes,
    narrative_policy_slot_groups,
    narrative_policy_terms,
)
from src.agent.financial_graph_calculation_rendering import infer_concept_ratio_result_unit
from src.agent.financial_runtime_normalization import _normalise_spaces
from src.agent.financial_retrieval_hints import (
    _infer_statement_and_section_hints,
    _matched_ontology_concept_specs,
    query_component_match_count,
    query_mentions_metric,
)
from src.agent.financial_surface_contracts import (
    operand_segment_label,
    operand_surface_contract,
    text_has_negative_surface,
    binding_policy_allows_candidate_shape,
    candidate_matches_segment_binding,
    is_balance_sheet_aggregate_operand,
    is_capex_total_operand,
)
from src.agent.financial_row_surfaces import (
    extract_table_row_label,
    format_structured_candidate_row_text,
    parse_unstructured_table_row_cells,
    strip_financial_label_annotations,
    aggregate_like_row_role,
    aggregate_like_row_stage,
    candidate_has_segment_local_binding,
    candidate_sibling_surface_hit_count,
    column_candidate_label,
)
from src.agent.financial_structured_cells import (
    candidate_selected_cell_for_operand,
    score_structured_cell,
    select_aggregate_structured_cell,
)
from src.agent.financial_scope_policies import (
    _desired_consolidation_scope,
    _extract_year_tokens,
    candidate_matches_target_report_scope,
    has_single_report_scope,
    operand_period_focus,
    operand_target_years,
    query_period_focus,
    task_period_focus_from_operands,
)
from src.agent.financial_operation_policies import (
    is_percent_point_difference_query,
    label_implies_percent_metric,
    is_ratio_percent_query,
    is_single_metric_period_comparison,
    query_requests_narrative_context,
)
from src.agent.financial_operand_resolution import (
    candidate_is_canonical_statement_winner,
    candidate_direct_family_signature,
    candidate_is_direct_grounding_candidate,
    candidate_direct_logical_signature,
    candidate_matches_operand,
    direct_candidate_semantic_priority,
    lookup_canonical_statement_preferences,
    lookup_prefers_canonical_statement_rows,
    lookup_query_surface_preferences,
    candidate_satisfies_direct_acceptance_contract,
    score_operand_candidate,
)
from src.routing import default_format_preference

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_REPORT_ROOT = _PROJECT_ROOT / "data" / "reports"
_UNIT_HINT_HTML_PATTERN = re.compile(r"\(\s*단위\s*:\s*([^)]+?)\s*\)")

# ---------------------------------------------------------------------------
# Text and ledger utilities
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Semantic planning helpers
# ---------------------------------------------------------------------------


def llm_plan_preserves_segment_sum_shape(base_plan: Dict[str, Any], llm_plan: Dict[str, Any]) -> bool:
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


def llm_plan_preserves_analysis_shape(base_plan: Dict[str, Any], llm_plan: Dict[str, Any]) -> bool:
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


def apply_segment_labels_to_llm_resolved_specs(
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


def align_scope_hints(
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
        if has_single_report_scope(report_scope):
            normalized_companies = [scope_company]
        elif not normalized_companies:
            normalized_companies = [scope_company]
        elif scope_company not in normalized_companies:
            normalized_companies = [scope_company, *normalized_companies]

    if scope_year is not None:
        if not normalized_years:
            normalized_years = [scope_year]
        elif scope_year not in normalized_years:
            normalized_years = [scope_year, *normalized_years]

    return normalized_companies, normalized_years


def validate_concept_planner_task(
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


def _is_narrative_summary_task(task: Dict[str, Any]) -> bool:
    operation_family = _normalise_spaces(str(task.get("operation_family") or "")).lower()
    metric_family = _normalise_spaces(str(task.get("metric_family") or "")).lower()
    return operation_family == "narrative_summary" or metric_family == "narrative_summary"


def _needs_hybrid_narrative_subtask(query: str, intent: str) -> bool:
    return intent in {"comparison", "trend", "numeric_fact"} and query_requests_narrative_context(query)


def build_hybrid_narrative_subtask(
    *,
    query: str,
    intent: str = "qa",
    report_scope: Dict[str, Any],
    next_task_id: str,
) -> Dict[str, Any]:
    consolidation_scope = _desired_consolidation_scope(query, report_scope)
    period_focus = query_period_focus(query, "unknown")
    active_policies = active_narrative_policies(query)
    active_slot_groups = [
        group
        for group in narrative_policy_slot_groups(active_policies)
        if any(str(term).strip() and str(term).strip() in query for term in (group.get("query_terms") or []))
    ]
    policy_format_preference = next(
        (
            str(policy.get("format_preference_override") or "").strip().lower()
            for policy in active_policies
            if str(policy.get("format_preference_override") or "").strip().lower() in {"paragraph", "table"}
        ),
        "",
    )
    format_preference_override = policy_format_preference or (
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


def append_hybrid_narrative_task(
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
        build_hybrid_narrative_subtask(
            query=query,
            intent=intent,
            report_scope=report_scope,
            next_task_id=f"task_{next_index}",
        )
    )
    return base_tasks


def push_narrative_tasks_after_numeric(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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


def exclusive_narrative_task_policy_active(query: str) -> bool:
    return any(
        bool(policy.get("exclusive_narrative_task"))
        for policy in active_narrative_policies(query)
    )


_QUOTED_METRIC_RE = re.compile(r"""['"“”‘’「」『』](?P<label>[^'"“”‘’「」『』]+)['"“”‘’「」『』]""")
_GENERIC_RATIO_SHARE_RE = re.compile(
    r"(?P<denominator>[가-힣A-Za-z0-9·/&\-\s\(\)]+?)\s*중\s*"
    r"(?P<numerator>[가-힣A-Za-z0-9·/&\-\s\(\)]+?)\s*"
    r"(?:(?:이|가)\s*차지하는\s*)?(?:의\s*)?"
    r"(?:비중|비율)"
)
_GENERIC_PERIOD_COMPARISON_METRIC_RE = re.compile(
    r"(?:20\d{2}년\s*)?"
    r"(?P<label>[가-힣A-Za-z0-9·/&\-\s\(\)]{2,80}?)의\s*"
    rf"{KOREAN_PERIOD_COMPARISON_RE_FRAGMENT}\s*"
    rf"{KOREAN_PERIOD_RATE_METRIC_SUFFIX_RE_FRAGMENT}"
)


def _clean_metric_label(label: str) -> str:
    text = _normalise_spaces(str(label or ""))
    label_policy = dict(GENERIC_OPERAND_LABEL_POLICY)
    text = re.sub(str(label_policy.get("leading_year_pattern") or r"$^"), "", text)
    for boundary in label_policy.get("cleanup_boundaries") or ():
        if boundary in text:
            text = text.rsplit(boundary, 1)[-1].strip()
    text = re.sub(str(label_policy.get("cleanup_suffix_pattern") or r"$^"), "", text).strip()
    return text


def _extract_quoted_metric_labels(query: str) -> List[str]:
    labels: List[str] = []
    for match in _QUOTED_METRIC_RE.finditer(str(query or "")):
        cleaned = _clean_metric_label(match.group("label"))
        if cleaned:
            labels.append(cleaned)
    return list(dict.fromkeys(labels))


def _ontology_operand_surface_candidates(spec: Mapping[str, Any]) -> List[str]:
    surface_contract = dict(spec.get("surface_contract") or {})
    candidates: List[str] = [str(spec.get("name") or "").strip()]
    candidates.extend(str(item).strip() for item in (spec.get("aliases") or []) if str(item).strip())
    candidates.extend(str(item).strip() for item in (spec.get("keywords") or []) if str(item).strip())
    candidates.extend(
        str(item).strip()
        for item in (surface_contract.get("positive") or [])
        if str(item).strip()
    )
    return list(dict.fromkeys(item for item in candidates if item))


def _surface_visible_in_text(surface: str, text: str) -> bool:
    normalized_surface = _normalise_spaces(surface)
    if not normalized_surface:
        return False
    normalized_text = _normalise_spaces(text)
    if normalized_surface in normalized_text:
        return True
    compact_surface = re.sub(r"\s+", "", normalized_surface)
    compact_text = re.sub(r"\s+", "", normalized_text)
    return bool(compact_surface and compact_surface in compact_text)


def _drop_redundant_parenthetical_alias_labels(labels: Sequence[str]) -> List[str]:
    normalized = list(dict.fromkeys(label for label in labels if label))
    parenthetical_aliases: set[str] = set()
    for label in normalized:
        for match in re.finditer(r"\(([^()]+)\)", label):
            alias = _normalise_spaces(match.group(1))
            if alias:
                parenthetical_aliases.add(alias)
    if not parenthetical_aliases:
        retained = normalized
    else:
        retained = [
            label
            for label in normalized
            if _normalise_spaces(label) not in parenthetical_aliases
        ]

    deduped: List[str] = []
    compact_seen: set[str] = set()
    for label in retained:
        compact = re.sub(r"\s+", "", _normalise_spaces(label))
        if compact in compact_seen:
            continue
        compact_seen.add(compact)
        deduped.append(label)

    compact_by_label = {
        label: re.sub(r"\s+", "", _normalise_spaces(label))
        for label in deduped
    }
    return [
        label
        for label, compact in compact_by_label.items()
        if not any(
            compact
            and compact != other_compact
            and compact in other_compact
            for other_label, other_compact in compact_by_label.items()
            if other_label != label
        )
    ]


def _extract_generic_operand_labels(query: str) -> List[str]:
    text = str(query or "")
    labels: List[str] = []

    for expansion in GENERIC_OPERAND_LABEL_POLICY.get("compound_label_expansions") or ():
        markers = tuple(str(item) for item in (dict(expansion).get("markers") or ()) if str(item))
        if any(marker in text for marker in markers):
            labels.extend(str(item) for item in (dict(expansion).get("labels") or ()) if str(item))

    labels.extend(_extract_quoted_metric_labels(text))
    for spec in _matched_ontology_concept_specs(query):
        if bool(spec.get("is_group")):
            continue
        visible_surfaces: List[str] = []
        for surface in _ontology_operand_surface_candidates(spec):
            if _surface_visible_in_text(surface, text):
                cleaned = _clean_metric_label(surface)
                if cleaned:
                    visible_surfaces.append(cleaned)
        concept_name = _clean_metric_label(str(spec.get("name") or "").strip())
        if concept_name and not any(re.search(r"[가-힣]", item) for item in visible_surfaces):
            labels.append(concept_name)
        labels.extend(visible_surfaces)
    for match in _GENERIC_PERIOD_COMPARISON_METRIC_RE.finditer(text):
        cleaned = _clean_metric_label(match.group("label"))
        if cleaned:
            labels.append(cleaned)

    normalized = _drop_redundant_parenthetical_alias_labels(labels)
    derived_labels = {str(item) for item in (GENERIC_OPERAND_LABEL_POLICY.get("derived_labels_to_drop") or ())}
    normalized = [item for item in normalized if item not in derived_labels]
    return normalized


def _extract_generic_ratio_operand_specs(query: str) -> List[Dict[str, Any]]:
    text = _normalise_spaces(query)
    if not text:
        return []

    match = _GENERIC_RATIO_SHARE_RE.search(text)
    if not match:
        return []

    denominator = _clean_metric_label(match.group("denominator"))
    numerator = _clean_metric_label(match.group("numerator"))
    if not denominator or not numerator or denominator == numerator:
        return []

    return [
        {
            "label": numerator,
            "role": "numerator_1",
            "required": True,
        },
        {
            "label": denominator,
            "role": "denominator_1",
            "required": True,
        },
    ]


def _infer_generic_unit_family(label: str) -> str:
    normalized = _normalise_spaces(str(label or ""))
    if not normalized:
        return ""
    if label_implies_percent_metric(normalized):
        return "PERCENT"
    compact = re.sub(r"\s+", "", normalized)
    unit_policy = dict(GENERIC_UNIT_FAMILY_POLICY)
    count_markers = tuple(str(item) for item in (unit_policy.get("count_markers") or ()) if str(item))
    if any(token in compact for token in count_markers):
        return "COUNT"
    return ""


def _build_generic_metric_aliases(label: str) -> List[str]:
    base = str(label or "").strip()
    if not base:
        return []
    aliases = [base]
    without_parens = _normalise_spaces(re.sub(r"\([^)]*\)", " ", base))
    if without_parens and without_parens != base:
        aliases.append(without_parens)
    for inner in re.findall(r"\(([^)]*)\)", base):
        cleaned_inner = _normalise_spaces(inner)
        if cleaned_inner:
            aliases.append(cleaned_inner)
    for substitution in GENERIC_METRIC_ALIAS_SUBSTITUTIONS:
        source = str(substitution.get("source") or "")
        target = str(substitution.get("target") or "")
        blocked = tuple(str(item) for item in (substitution.get("blocked_if_present") or ()) if str(item))
        if source and target and source in base and not any(token in base for token in blocked):
            aliases.append(base.replace(source, target))
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _infer_generic_concept_spec(
    label: str,
    ontology: Any,
) -> Dict[str, Any]:
    cleaned = _clean_metric_label(label)
    normalized = _normalise_spaces(cleaned)
    if not normalized:
        return {}

    exact_matches: List[Dict[str, Any]] = []
    fuzzy_matches: List[Dict[str, Any]] = []
    for spec in list(getattr(ontology, "all_concept_specs", lambda: [])() or []):
        if bool(spec.get("is_group")):
            continue
        alias_values = [
            str(spec.get("name") or "").strip(),
            *(spec.get("aliases") or []),
            *(spec.get("keywords") or []),
        ]
        normalized_aliases = [
            _normalise_spaces(alias)
            for alias in alias_values
            if _normalise_spaces(alias)
        ]
        if not normalized_aliases:
            continue
        if normalized in normalized_aliases:
            exact_matches.append(dict(spec))
            continue
        if any(normalized in alias or alias in normalized for alias in normalized_aliases):
            fuzzy_matches.append(dict(spec))

    if exact_matches:
        exact_matches.sort(
            key=lambda spec: max(
                (
                    len(_normalise_spaces(alias))
                    for alias in [
                        str(spec.get("name") or "").strip(),
                        *(spec.get("aliases") or []),
                    ]
                    if _normalise_spaces(alias)
                ),
                default=0,
            ),
            reverse=True,
        )
        return exact_matches[0]
    if fuzzy_matches:
        return fuzzy_matches[0]

    matched_specs = [
        dict(spec)
        for spec in list(ontology.concept_specs(cleaned, cleaned, "comparison") or [])
        if not bool(spec.get("is_group"))
    ]
    return matched_specs[0] if matched_specs else {}


def _augment_generic_operand_with_concept(
    operand: Dict[str, Any],
    *,
    concept_spec: Dict[str, Any],
) -> Dict[str, Any]:
    if not concept_spec:
        return dict(operand)

    updated = dict(operand)
    updated["concept"] = str(concept_spec.get("concept") or "").strip()
    updated["aliases"] = list(
        dict.fromkeys(
            [
                *(updated.get("aliases") or []),
                str(concept_spec.get("name") or "").strip(),
                *(concept_spec.get("aliases") or []),
            ]
        )
    )
    updated["keywords"] = list(
        dict.fromkeys(
            [
                *(updated.get("keywords") or []),
                *(concept_spec.get("keywords") or []),
            ]
        )
    )
    updated["preferred_sections"] = list(
        dict.fromkeys(
            [
                *(updated.get("preferred_sections") or []),
                *(concept_spec.get("preferred_sections") or []),
            ]
        )
    )
    updated["preferred_statement_types"] = list(
        dict.fromkeys(
            [
                *(updated.get("preferred_statement_types") or []),
                *(concept_spec.get("preferred_statement_types") or []),
            ]
        )
    )
    binding_policy = dict(concept_spec.get("binding_policy") or {})
    role = str(updated.get("role") or "").strip()
    if role == "current_period" and not str(binding_policy.get("prefer_period_focus") or "").strip():
        binding_policy["prefer_period_focus"] = "current"
    elif role == "prior_period" and not str(binding_policy.get("prefer_period_focus") or "").strip():
        binding_policy["prefer_period_focus"] = "prior"
    updated["binding_policy"] = binding_policy
    updated["surface_contract"] = dict(concept_spec.get("surface_contract") or {})
    if not str(updated.get("unit_family") or "").strip():
        updated["unit_family"] = str(concept_spec.get("unit_family") or "").strip()
    return updated


def _build_generic_required_operands(
    query: str,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    ontology = get_financial_ontology()
    ratio_operand_specs = _extract_generic_ratio_operand_specs(query)
    if ratio_operand_specs:
        preferred_statement_types, preferred_sections = _infer_statement_and_section_hints(query)
        rows: List[Dict[str, Any]] = []
        for spec in ratio_operand_specs:
            label = str(spec.get("label") or "").strip()
            aliases = _build_generic_metric_aliases(label)
            concept_spec = _infer_generic_concept_spec(label, ontology)
            role = str(spec.get("role") or "").strip()
            binding_policy: Dict[str, Any] = {}
            if role.startswith("denominator"):
                binding_policy = {
                    "prefer_value_roles": ["aggregate"],
                    "prefer_aggregation_stages": ["final", "subtotal", "direct"],
                }
            rows.append(
                _augment_generic_operand_with_concept(
                    {
                        "label": label,
                        "aliases": list(dict.fromkeys(alias for alias in aliases if alias)),
                        "role": role,
                        "required": True,
                        "unit_family": _infer_generic_unit_family(label),
                        "preferred_statement_types": list(preferred_statement_types),
                        "preferred_sections": list(preferred_sections),
                        "binding_policy": binding_policy,
                    },
                    concept_spec=concept_spec,
                )
            )
        if rows:
            return rows

    operand_labels = _extract_generic_operand_labels(query)
    if is_single_metric_period_comparison(query, operand_labels):
        period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
        current_hint = str(period_policy.get("current_period_hint") or "current")
        prior_hint = str(period_policy.get("prior_period_hint") or "prior")
        year_label_template = str(period_policy.get("year_label_template") or "{year} {label}")
        current_label_template = str(period_policy.get("current_label_template") or "{period_hint} {label}")
        prior_label_template = str(period_policy.get("prior_label_template") or "{period_hint} {label}")
        base_label = operand_labels[0] if operand_labels else _infer_generic_metric_label(query, "")
        aliases = _build_generic_metric_aliases(base_label)
        unit_family = _infer_generic_unit_family(base_label)
        concept_spec = _infer_generic_concept_spec(base_label, ontology)
        year_tokens = _extract_year_tokens(query, report_scope)
        if year_tokens:
            current_year = year_tokens[0]
            prior_year = year_tokens[1] if len(year_tokens) > 1 else current_year - 1
            return [
                _augment_generic_operand_with_concept(
                    {
                        "label": year_label_template.format(year=current_year, label=base_label),
                        "aliases": aliases,
                        "role": "current_period",
                        "required": True,
                        "period_hint": str(current_year),
                        "unit_family": unit_family,
                    },
                    concept_spec=concept_spec,
                ),
                _augment_generic_operand_with_concept(
                    {
                        "label": year_label_template.format(year=prior_year, label=base_label),
                        "aliases": aliases,
                        "role": "prior_period",
                        "required": True,
                        "period_hint": str(prior_year),
                        "unit_family": unit_family,
                    },
                    concept_spec=concept_spec,
                ),
            ]
        return [
            _augment_generic_operand_with_concept(
                {
                    "label": current_label_template.format(period_hint=current_hint, label=base_label),
                    "aliases": aliases,
                    "role": "current_period",
                    "required": True,
                    "period_hint": current_hint,
                    "unit_family": unit_family,
                },
                concept_spec=concept_spec,
            ),
            _augment_generic_operand_with_concept(
                {
                    "label": prior_label_template.format(period_hint=prior_hint, label=base_label),
                    "aliases": aliases,
                    "role": "prior_period",
                    "required": True,
                    "period_hint": prior_hint,
                    "unit_family": unit_family,
                },
                concept_spec=concept_spec,
            ),
        ]

    rows: List[Dict[str, Any]] = []
    for label in operand_labels:
        aliases = _build_generic_metric_aliases(label)
        concept_spec = _infer_generic_concept_spec(label, ontology)
        rows.append(
            _augment_generic_operand_with_concept(
                {
                    "label": label,
                    "aliases": list(dict.fromkeys(alias for alias in aliases if alias)),
                    "role": "",
                    "required": True,
                    "unit_family": _infer_generic_unit_family(label),
                },
                concept_spec=concept_spec,
            )
        )
    return rows


def _infer_generic_metric_label(query: str, topic: str) -> str:
    quoted = _extract_quoted_metric_labels(query)
    if len(quoted) == 1:
        return quoted[0]
    operand_labels = _extract_generic_operand_labels(query)
    if operand_labels:
        return operand_labels[0]
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    return _clean_metric_label(topic) or str(period_policy.get("fallback_metric_label") or "")


def _build_generic_retrieval_queries(
    query: str,
    metric_label: str,
    operand_specs: List[Dict[str, Any]],
    preferred_sections: List[str],
    report_scope: Dict[str, Any],
    constraints: Optional[Dict[str, str]] = None,
) -> List[str]:
    def _collapse_duplicate_query_tokens(raw: str) -> str:
        pieces = [piece for piece in _normalise_spaces(raw).split(" ") if piece]
        collapsed: List[str] = []
        for piece in pieces:
            if collapsed and collapsed[-1] == piece:
                continue
            collapsed.append(piece)
        return " ".join(collapsed).strip()

    def _strip_leading_period_prefix(text: str) -> str:
        return _normalise_spaces(re.sub(rf"^{KOREAN_PERIOD_PREFIX_RE_FRAGMENT}\s+", "", _normalise_spaces(text or "")))

    def _surface_query_variants(text: str) -> List[str]:
        normalized = _strip_leading_period_prefix(text)
        if not normalized:
            return []
        variants = [normalized]
        tokens = normalized.split()
        if len(tokens) >= 2:
            variants.append(" ".join(tokens[:-1]))
        for candidate in list(variants):
            if re.search(r"[가-힣]", candidate) and " " in candidate:
                variants.append(re.sub(r"\s+", "", candidate))
        return list(dict.fromkeys(item for item in variants if item))

    def _query_surfaces_for_operand(operand: Dict[str, Any]) -> List[str]:
        label = str(operand.get("label") or "").strip()
        surfaces: List[str] = []
        surfaces.extend(_surface_query_variants(label))
        for alias in list(operand.get("aliases") or [])[:3]:
            surfaces.extend(_surface_query_variants(str(alias).strip()))
        for surface in lookup_query_surface_preferences(operand):
            surfaces.extend(_surface_query_variants(surface))
        return list(dict.fromkeys(surface for surface in surfaces if surface))

    queries = [query]
    year = str(report_scope.get("year") or "").strip()
    year_prefix = f"{year}년 " if year else ""
    fallback_period_focus = str((constraints or {}).get("period_focus") or "unknown").strip()

    def _year_for_operand(operand: Dict[str, Any]) -> str:
        period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
        prior_period_hints = set(str(item) for item in (period_policy.get("prior_period_hints") or ()) if str(item))
        if not year.isdigit():
            return year
        role = str(operand.get("role") or "").strip()
        period_hint = str(operand.get("period_hint") or "").strip()
        if role == "prior_period" or period_hint in prior_period_hints:
            return str(int(year) - 1)
        if role == "current_period":
            return year
        if fallback_period_focus == "prior":
            return str(int(year) - 1)
        return year

    def _prefix_for_operand(operand: Dict[str, Any]) -> str:
        period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
        year_suffix_template = str(period_policy.get("year_suffix_template") or "{year}")
        current_hint = str(period_policy.get("current_period_hint") or "current")
        prior_hint = str(period_policy.get("prior_period_hint") or "prior")
        operand_year = _year_for_operand(operand)
        pieces: List[str] = []
        if operand_year:
            pieces.append(year_suffix_template.format(year=operand_year))
        period_hint = str(operand.get("period_hint") or "").strip()
        role = str(operand.get("role") or "").strip()
        if not period_hint:
            if role == "current_period":
                period_hint = current_hint
            elif role == "prior_period":
                period_hint = prior_hint
        normalized_period_hint = _normalise_spaces(period_hint)
        if operand_year and normalized_period_hint in {operand_year, year_suffix_template.format(year=operand_year)}:
            period_hint = ""
        if period_hint:
            pieces.append(period_hint)
        return _normalise_spaces(" ".join(pieces))

    if len(operand_specs) == 2:
        left = dict(operand_specs[0] or {})
        right = dict(operand_specs[1] or {})
        left_role = str(left.get("role") or "").strip()
        right_role = str(right.get("role") or "").strip()
        left_concept = str(left.get("concept") or "").strip()
        right_concept = str(right.get("concept") or "").strip()
        left_label_base = _strip_leading_period_prefix(str(left.get("label") or ""))
        right_label_base = _strip_leading_period_prefix(str(right.get("label") or ""))
        same_metric_pair = bool(
            (left_concept and left_concept == right_concept)
            or (left_label_base and left_label_base == right_label_base)
        )
        if (
            {left_role, right_role} == {"current_period", "prior_period"}
            and same_metric_pair
        ):
            left_year = _year_for_operand(left)
            right_year = _year_for_operand(right)
            alias_candidates = [str(item).strip() for item in (left.get("aliases") or []) if str(item).strip()]
            shared_label = _strip_leading_period_prefix(alias_candidates[0] if alias_candidates else "") or _strip_leading_period_prefix(
                str(left.get("label") or "")
            )
            if shared_label:
                year_suffix_template = str(dict(GENERIC_PERIOD_OPERAND_POLICY).get("year_suffix_template") or "{year}")
                compact_bits = [
                    bit
                    for bit in (
                        year_suffix_template.format(year=left_year) if left_year else "",
                        year_suffix_template.format(year=right_year) if right_year else "",
                        shared_label,
                    )
                    if bit
                ]
                queries.append(_collapse_duplicate_query_tokens(" ".join(compact_bits)))
                for section in preferred_sections[:2]:
                    queries.append(_collapse_duplicate_query_tokens(f"{' '.join(compact_bits)} {section}"))
                for alias in list(left.get("aliases") or [])[:2]:
                    alias_text = _strip_leading_period_prefix(str(alias).strip())
                    if alias_text and alias_text != shared_label:
                        alias_bits = [
                            bit
                            for bit in (
                                year_suffix_template.format(year=left_year) if left_year else "",
                                year_suffix_template.format(year=right_year) if right_year else "",
                                alias_text,
                            )
                            if bit
                        ]
                        queries.append(_collapse_duplicate_query_tokens(" ".join(alias_bits)))
                        for section in preferred_sections[:2]:
                            queries.append(_collapse_duplicate_query_tokens(f"{' '.join(alias_bits)} {section}"))
        else:
            numerator = left if left_role.startswith("numerator") else right if right_role.startswith("numerator") else {}
            denominator = left if left_role.startswith("denominator") else right if right_role.startswith("denominator") else {}
            if numerator and denominator:
                numerator_label = _strip_leading_period_prefix(str(numerator.get("label") or ""))
                denominator_label = _strip_leading_period_prefix(str(denominator.get("label") or ""))
                pair_queries = [
                    _collapse_duplicate_query_tokens(" ".join(bit for bit in (year_prefix.strip(), denominator_label, numerator_label) if bit)),
                    _collapse_duplicate_query_tokens(" ".join(bit for bit in (year_prefix.strip(), numerator_label, denominator_label) if bit)),
                ]
                for pair_query in pair_queries:
                    if pair_query:
                        queries.append(pair_query)
                        for section in preferred_sections[:3]:
                            queries.append(_collapse_duplicate_query_tokens(f"{pair_query} {section}"))

    metric_query_surfaces = _surface_query_variants(metric_label)
    if metric_query_surfaces:
        queries.append(_collapse_duplicate_query_tokens(f"{year_prefix}{metric_query_surfaces[0]}"))
        for section in preferred_sections[:4]:
            queries.append(_collapse_duplicate_query_tokens(f"{year_prefix}{metric_query_surfaces[0]} {section}"))
        for surface in metric_query_surfaces[1:]:
            queries.append(_collapse_duplicate_query_tokens(f"{year_prefix}{surface}"))
            for section in preferred_sections[:2]:
                queries.append(_collapse_duplicate_query_tokens(f"{year_prefix}{surface} {section}"))
    for operand in operand_specs:
        label = str(operand.get("label") or "").strip()
        if not label:
            continue
        operand_prefix = _prefix_for_operand(operand) or year_prefix.strip()
        segment_label = operand_segment_label(operand)
        normalized_label = _strip_leading_period_prefix(label)
        queries.append(_collapse_duplicate_query_tokens(f"{operand_prefix} {normalized_label or label}"))
        for surface in _query_surfaces_for_operand(operand):
            normalized_surface = surface
            if segment_label and normalized_surface and segment_label not in normalized_surface:
                normalized_surface = _normalise_spaces(f"{segment_label} {normalized_surface}")
            queries.append(_collapse_duplicate_query_tokens(f"{operand_prefix} {normalized_surface}"))
            for section in preferred_sections[:2]:
                queries.append(_collapse_duplicate_query_tokens(f"{operand_prefix} {normalized_surface} {section}"))
        for section in preferred_sections[:2]:
            queries.append(_collapse_duplicate_query_tokens(f"{operand_prefix} {normalized_label or label} {section}"))
    return list(dict.fromkeys(item for item in queries if item))


def _planner_intent_cues(ontology: Any, operation_family: str) -> List[str]:
    guidance = dict(getattr(ontology, "planner_guidance", {}) or {})
    intent_cues = dict(guidance.get("intent_cues") or {})
    return [
        str(item).strip()
        for item in (intent_cues.get(operation_family) or [])
        if str(item).strip()
    ]


def _infer_operation_family_from_query(query: str, ontology: Any) -> str:
    text = _normalise_spaces(query).lower()
    if not text:
        return "single_value"

    generic_operand_labels = _extract_generic_operand_labels(query)
    for policy in OPERATION_FAMILY_QUERY_POLICIES:
        markers = tuple(str(marker).lower() for marker in (policy.get("markers") or ()) if str(marker))
        if any(marker in text for marker in markers):
            return str(policy.get("operation_family") or "single_value")
    if is_percent_point_difference_query(query):
        return "difference"
    if is_single_metric_period_comparison(query, generic_operand_labels):
        return "difference"
    if is_ratio_percent_query(query):
        return "ratio"
    if any(cue.lower() in text for cue in _planner_intent_cues(ontology, "growth_rate")):
        return "growth_rate"
    if any(cue.lower() in text for cue in _planner_intent_cues(ontology, "ratio")):
        return "ratio"
    if any(cue.lower() in text for cue in _planner_intent_cues(ontology, "difference")):
        return "difference"
    if any(cue.lower() in text for cue in _planner_intent_cues(ontology, "sum")):
        return "sum"
    return "single_value"


def _concept_alias_position(spec: Dict[str, Any], text: str) -> float:
    haystack = _normalise_spaces(text).lower()
    positions: List[int] = []
    aliases = [
        str(spec.get("name") or "").strip(),
        *(spec.get("aliases") or []),
        *(spec.get("keywords") or []),
    ]
    for alias in aliases:
        needle = _normalise_spaces(alias).lower()
        if not needle:
            continue
        position = haystack.find(needle)
        if position >= 0:
            positions.append(position)
    return float(min(positions)) if positions else math.inf


def _order_concept_specs_by_query(concept_specs: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    indexed: List[tuple[float, int, Dict[str, Any]]] = []
    for index, spec in enumerate(concept_specs):
        indexed.append((_concept_alias_position(spec, query), index, spec))
    indexed.sort(key=lambda item: (item[0], item[1]))
    return [spec for _position, _index, spec in indexed]


def _expand_group_concept_specs(
    concept_specs: List[Dict[str, Any]],
    role_hints: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    expanded: List[Dict[str, Any]] = []
    role_hints = list(role_hints or [])
    for index, spec in enumerate(concept_specs):
        current_role = role_hints[index] if index < len(role_hints) else str(spec.get("role") or "").strip()
        member_specs = list(spec.get("member_specs") or [])
        if member_specs:
            for member_spec in member_specs:
                expanded_spec = dict(member_spec)
                if current_role and not str(expanded_spec.get("role") or "").strip():
                    expanded_spec["role"] = current_role
                expanded.append(expanded_spec)
            continue
        expanded_spec = dict(spec)
        if current_role and not str(expanded_spec.get("role") or "").strip():
            expanded_spec["role"] = current_role
        expanded.append(expanded_spec)

    deduped: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for spec in expanded:
        concept_key = str(spec.get("concept") or "").strip()
        role = str(spec.get("role") or "").strip()
        dedupe_key = (concept_key, role)
        if concept_key and dedupe_key in seen:
            continue
        if concept_key:
            seen.add(dedupe_key)
        deduped.append(spec)
    return deduped


def _normalize_operation_roles(operation_family: str, roles: List[str]) -> List[str]:
    normalized = list(roles)
    if operation_family == "ratio":
        counters = {"numerator": 0, "denominator": 0}
        for index, role in enumerate(normalized):
            if role.startswith("numerator"):
                counters["numerator"] += 1
                normalized[index] = f"numerator_{counters['numerator']}"
            elif role.startswith("denominator"):
                counters["denominator"] += 1
                normalized[index] = f"denominator_{counters['denominator']}"
    elif operation_family == "sum":
        counter = 0
        for index, role in enumerate(normalized):
            if role.startswith("addend"):
                counter += 1
                normalized[index] = f"addend_{counter}"
    return normalized


def _build_concept_period_operands(
    spec: Dict[str, Any],
    query: str,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    current_hint = str(period_policy.get("current_period_hint") or "current")
    prior_hint = str(period_policy.get("prior_period_hint") or "prior")
    year_label_template = str(period_policy.get("year_label_template") or "{year} {label}")
    current_label_template = str(period_policy.get("current_label_template") or "{period_hint} {label}")
    prior_label_template = str(period_policy.get("prior_label_template") or "{period_hint} {label}")
    label = str(spec.get("name") or "").strip()
    concept = str(spec.get("concept") or "").strip()
    aliases = list(dict.fromkeys([label, *(spec.get("aliases") or [])]))
    keywords = list(dict.fromkeys(spec.get("keywords") or []))
    preferred_sections = list(dict.fromkeys(spec.get("preferred_sections") or []))
    preferred_statement_types = list(dict.fromkeys(spec.get("preferred_statement_types") or []))
    binding_policy = dict(spec.get("binding_policy") or {})
    surface_contract = dict(spec.get("surface_contract") or {})
    year_tokens = _extract_year_tokens(query, report_scope)
    if year_tokens:
        current_year = year_tokens[0]
        prior_year = year_tokens[1] if len(year_tokens) > 1 else current_year - 1
        return [
            {
                "label": year_label_template.format(year=current_year, label=label),
                "concept": concept,
                "aliases": aliases,
                "keywords": keywords,
                "role": "current_period",
                "required": True,
                "period_hint": str(current_year),
                "preferred_sections": preferred_sections,
                "preferred_statement_types": preferred_statement_types,
                "binding_policy": binding_policy,
                "unit_family": str(spec.get("unit_family") or "").strip(),
                "surface_contract": surface_contract,
            },
            {
                "label": year_label_template.format(year=prior_year, label=label),
                "concept": concept,
                "aliases": aliases,
                "keywords": keywords,
                "role": "prior_period",
                "required": True,
                "period_hint": str(prior_year),
                "preferred_sections": preferred_sections,
                "preferred_statement_types": preferred_statement_types,
                "binding_policy": binding_policy,
                "unit_family": str(spec.get("unit_family") or "").strip(),
                "surface_contract": surface_contract,
            },
        ]
    return [
        {
            "label": current_label_template.format(period_hint=current_hint, label=label),
            "concept": concept,
            "aliases": aliases,
            "keywords": keywords,
            "role": "current_period",
            "required": True,
            "period_hint": current_hint,
            "preferred_sections": preferred_sections,
            "preferred_statement_types": preferred_statement_types,
            "binding_policy": binding_policy,
            "unit_family": str(spec.get("unit_family") or "").strip(),
            "surface_contract": surface_contract,
        },
        {
            "label": prior_label_template.format(period_hint=prior_hint, label=label),
            "concept": concept,
            "aliases": aliases,
            "keywords": keywords,
            "role": "prior_period",
            "required": True,
            "period_hint": prior_hint,
            "preferred_sections": preferred_sections,
            "preferred_statement_types": preferred_statement_types,
            "binding_policy": binding_policy,
            "unit_family": str(spec.get("unit_family") or "").strip(),
            "surface_contract": surface_contract,
        },
    ]


def _assign_ratio_roles_to_concepts(query: str, concept_specs: List[Dict[str, Any]]) -> List[str]:
    ordered = _order_concept_specs_by_query(concept_specs, query)
    roles = [""] * len(ordered)

    def _assign(indices: List[int], prefix: str) -> None:
        for offset, index in enumerate(indices, start=1):
            roles[index] = f"{prefix}_{offset}"

    def _candidate_score(spec: Dict[str, Any], target_label: str) -> tuple[int, int, float]:
        normalized_target = _normalise_spaces(target_label)
        alias_values = [
            str(spec.get("name") or "").strip(),
            *(spec.get("aliases") or []),
            *(spec.get("keywords") or []),
        ]
        normalized_aliases = [
            _normalise_spaces(alias)
            for alias in alias_values
            if _normalise_spaces(alias)
        ]
        exact = any(normalized_target == alias for alias in normalized_aliases)
        overlap = any(
            normalized_target in alias or alias in normalized_target
            for alias in normalized_aliases
        )
        if not exact and not overlap:
            return (0, 0, math.inf)
        best_position = _concept_alias_position(spec, target_label)
        best_alias_length = max((len(alias) for alias in normalized_aliases), default=0)
        return (2 if exact else 1, best_alias_length, best_position)

    share_specs = _extract_generic_ratio_operand_specs(query)
    if share_specs:
        assigned: set[int] = set()
        for share_spec in share_specs:
            target_label = str(share_spec.get("label") or "").strip()
            target_role = str(share_spec.get("role") or "").strip()
            candidates: List[tuple[int, int, float, int]] = []
            for index, spec in enumerate(ordered):
                if index in assigned:
                    continue
                score = _candidate_score(spec, target_label)
                if score[0] <= 0:
                    continue
                candidates.append((*score, index))
            if not candidates:
                continue
            candidates.sort(key=lambda item: (item[0], item[1], -item[2]), reverse=True)
            chosen_index = candidates[0][3]
            roles[chosen_index] = target_role
            assigned.add(chosen_index)
        if any(role.startswith("numerator") for role in roles) and any(role.startswith("denominator") for role in roles):
            return roles

    text = str(query or "")
    if "대비" in text:
        before_text, after_text = text.split("대비", 1)
        denominator_indices = [
            index
            for index, spec in enumerate(ordered)
            if _concept_alias_position(spec, before_text) < math.inf
        ]
        numerator_indices = [
            index
            for index, spec in enumerate(ordered)
            if _concept_alias_position(spec, after_text) < math.inf
        ]
        if denominator_indices and numerator_indices:
            _assign(numerator_indices, "numerator")
            _assign(denominator_indices, "denominator")
            return roles

    if "/" in text:
        left_text, right_text = text.split("/", 1)
        numerator_indices = [
            index
            for index, spec in enumerate(ordered)
            if _concept_alias_position(spec, left_text) < math.inf
        ]
        denominator_indices = [
            index
            for index, spec in enumerate(ordered)
            if _concept_alias_position(spec, right_text) < math.inf
        ]
        if numerator_indices and denominator_indices:
            _assign(numerator_indices, "numerator")
            _assign(denominator_indices, "denominator")
            return roles

    if len(ordered) == 2:
        roles[0] = "numerator_1"
        roles[1] = "denominator_1"
    return roles


def _extract_segment_labels_from_query(query: str, report_scope: Dict[str, Any]) -> List[str]:
    text = _normalise_spaces(query)
    if not text:
        return []

    blocked_tokens = {
        str(report_scope.get("company") or "").strip(),
        str(report_scope.get("report_type") or "").strip(),
        *KOREAN_SEGMENT_LABEL_REPORT_TERMS,
        *KOREAN_SEGMENT_LABEL_SCOPE_TOKENS,
        *KOREAN_SEGMENT_LABEL_BLOCKED_TOKENS,
    }
    blocked_exact_labels = set(KOREAN_SEGMENT_LABEL_BLOCKED_EXACT_LABELS)

    def _valid_label(label: str) -> str:
        normalized = _normalise_spaces(label)
        normalized = _normalise_spaces(re.sub(KOREAN_SEGMENT_LABEL_PERIOD_PREFIX_RE_FRAGMENT, "", normalized))
        normalized = _normalise_spaces(re.sub(KOREAN_SEGMENT_LABEL_TRAILING_PERIOD_RE_FRAGMENT, "", normalized))
        if not normalized:
            return ""
        if normalized in blocked_tokens:
            return ""
        if normalized in blocked_exact_labels:
            return ""
        if any(marker in normalized for marker in KOREAN_SEGMENT_LABEL_MARKERS if marker != "segment"):
            return ""
        if any(token in normalized for token in KOREAN_SEGMENT_LABEL_REPORT_TERMS):
            return ""
        if re.fullmatch(KOREAN_SEGMENT_LABEL_PERIOD_RE_FRAGMENT, normalized):
            return ""
        if len(normalized) > 40:
            return ""
        return normalized

    labels: List[str] = []

    if any(marker in text for marker in KOREAN_SEGMENT_LABEL_MARKERS):
        for match in re.finditer(KOREAN_SEGMENT_LABEL_PAREN_RE_FRAGMENT, text, flags=re.IGNORECASE):
            normalized = _valid_label(match.group(1))
            if normalized:
                labels.append(normalized)
        segment_anchor = ""
        for marker in KOREAN_SEGMENT_LABEL_ANCHORS:
            if marker in text:
                segment_anchor = marker
                break
        if segment_anchor:
            prefix = text.split(segment_anchor, 1)[0].strip()
            for boundary in KOREAN_SEGMENT_LABEL_BOUNDARIES:
                if boundary in prefix:
                    prefix = prefix.rsplit(boundary, 1)[-1].strip()
            prefix = re.sub(r"\b20\d{2}\b", " ", prefix)
            raw_parts = re.split(KOREAN_SEGMENT_LABEL_SPLIT_RE_FRAGMENT, prefix)
            for part in raw_parts:
                normalized = _valid_label(part)
                if normalized:
                    labels.append(normalized)

    for pattern in KOREAN_SEGMENT_LABEL_TOKEN_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            normalized = _valid_label(match.group(1))
            if normalized:
                labels.append(normalized)

    return list(dict.fromkeys(label for label in labels if label))


def _expand_segment_sum_specs(
    ordered_specs: List[Dict[str, Any]],
    query: str,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if len(ordered_specs) != 1:
        return ordered_specs

    segment_labels = _extract_segment_labels_from_query(query, report_scope)
    if len(segment_labels) < 2:
        return ordered_specs

    base_spec = dict(ordered_specs[0])
    base_name = str(base_spec.get("name") or "").strip()
    expanded: List[Dict[str, Any]] = []
    for index, segment_label in enumerate(segment_labels, start=1):
        spec = dict(base_spec)
        spec["name"] = f"{segment_label} {base_name}".strip()
        aliases = list(spec.get("aliases") or [])
        spec["aliases"] = list(dict.fromkeys([spec["name"], segment_label, base_name, *aliases]))
        binding_policy = dict(spec.get("binding_policy") or {})
        binding_policy["segment_label"] = segment_label
        spec["binding_policy"] = binding_policy
        spec["role"] = f"addend_{index}"
        expanded.append(spec)
    return expanded


def _build_concept_required_operands(
    query: str,
    report_scope: Dict[str, Any],
    concept_specs: List[Dict[str, Any]],
    operation_family: str,
) -> List[Dict[str, Any]]:
    ordered_specs = list(concept_specs)
    if not ordered_specs:
        return []

    raw_explicit_roles = [str(spec.get("role") or "").strip() for spec in ordered_specs]
    preserve_planner_order = False
    if operation_family == "ratio":
        preserve_planner_order = any(role.startswith("numerator") for role in raw_explicit_roles) and any(
            role.startswith("denominator") for role in raw_explicit_roles
        )
    elif operation_family == "sum":
        preserve_planner_order = any(role.startswith("addend") for role in raw_explicit_roles)
    elif operation_family == "difference":
        preserve_planner_order = any(role in {"minuend", "subtrahend", "current_period", "prior_period"} for role in raw_explicit_roles)
    elif operation_family == "growth_rate":
        preserve_planner_order = any(role in {"current_period", "prior_period"} for role in raw_explicit_roles)

    if not preserve_planner_order:
        ordered_specs = _order_concept_specs_by_query(concept_specs, query)
        raw_explicit_roles = [str(spec.get("role") or "").strip() for spec in ordered_specs]

    if len(ordered_specs) == 1 and operation_family in {"difference", "growth_rate"}:
        expanded_single = _expand_group_concept_specs(ordered_specs, raw_explicit_roles)
        if len(expanded_single) == 1:
            return _build_concept_period_operands(expanded_single[0], query, report_scope)
        return []


    role_hints = raw_explicit_roles
    if operation_family == "ratio":
        if any(role.startswith("numerator") for role in raw_explicit_roles) and any(role.startswith("denominator") for role in raw_explicit_roles):
            role_hints = raw_explicit_roles
        else:
            role_hints = _assign_ratio_roles_to_concepts(query, ordered_specs)
        if not any(role.startswith("numerator") for role in role_hints) or not any(role.startswith("denominator") for role in role_hints):
            return []
        if _extract_generic_ratio_operand_specs(query) and any(not role for role in role_hints):
            paired = [
                (spec, role)
                for spec, role in zip(ordered_specs, role_hints)
                if role.startswith("numerator") or role.startswith("denominator")
            ]
            if paired:
                ordered_specs = [spec for spec, _role in paired]
                role_hints = [role for _spec, role in paired]

    if operation_family == "sum" and len(ordered_specs) == 1:
        ordered_specs = _expand_segment_sum_specs(ordered_specs, query, report_scope)
        role_hints = [str(spec.get("role") or "").strip() for spec in ordered_specs]

    ordered_specs = _expand_group_concept_specs(ordered_specs, role_hints)
    if not ordered_specs:
        return []

    explicit_roles = _normalize_operation_roles(
        operation_family,
        [str(spec.get("role") or "").strip() for spec in ordered_specs],
    )
    if operation_family == "ratio":
        if not any(role.startswith("numerator") for role in explicit_roles) or not any(role.startswith("denominator") for role in explicit_roles):
            return []

    if operation_family in {"ratio", "sum"}:
        deduped_specs: List[Dict[str, Any]] = []
        deduped_roles: List[str] = []
        seen_keys: set[Any] = set()
        for spec, role in zip(ordered_specs, explicit_roles):
            concept_key = str(spec.get("concept") or "").strip()
            dedupe_key: Any = concept_key
            if operation_family in {"ratio", "sum"}:
                # Sum and ratio tasks can legitimately use the same concept more than
                # once when operands differ by role family, segment, or scope (for
                # example, segment operating income / company operating income).
                # Collapse group/member duplicate matches that land in the same role
                # family, but preserve numerator-vs-denominator distinctions.
                binding_policy = dict(spec.get("binding_policy") or {})
                normalized_role = str(role or "").strip()
                if operation_family == "ratio":
                    if normalized_role.startswith("numerator"):
                        normalized_role = "numerator"
                    elif normalized_role.startswith("denominator"):
                        normalized_role = "denominator"
                dedupe_key = (
                    concept_key,
                    normalized_role,
                    _normalise_spaces(str(binding_policy.get("segment_label") or "")),
                )
            if concept_key and dedupe_key in seen_keys:
                continue
            if concept_key:
                seen_keys.add(dedupe_key)
            deduped_specs.append(spec)
            deduped_roles.append(role)
        ordered_specs = deduped_specs
        explicit_roles = _normalize_operation_roles(operation_family, deduped_roles)

    operands: List[Dict[str, Any]] = []
    for index, spec in enumerate(ordered_specs, start=1):
        role = ""
        if operation_family == "ratio":
            role = explicit_roles[index - 1]
        elif operation_family == "sum":
            role = explicit_roles[index - 1] or f"addend_{index}"
        elif operation_family == "difference" and len(ordered_specs) >= 2:
            role = explicit_roles[index - 1] or ("minuend" if index == 1 else "subtrahend")
        elif operation_family == "growth_rate" and len(ordered_specs) >= 2:
            role = explicit_roles[index - 1] or ("current_period" if index == 1 else "prior_period")
        elif operation_family in {"lookup", "single_value"}:
            role = explicit_roles[index - 1]
        operands.append(
            {
                "label": str(spec.get("name") or "").strip(),
                "concept": str(spec.get("concept") or "").strip(),
                "aliases": list(dict.fromkeys([str(spec.get("name") or "").strip(), *(spec.get("aliases") or [])])),
                "keywords": list(dict.fromkeys(spec.get("keywords") or [])),
                "role": role,
                "required": True,
                "preferred_sections": list(dict.fromkeys(spec.get("preferred_sections") or [])),
                "preferred_statement_types": list(dict.fromkeys(spec.get("preferred_statement_types") or [])),
                "binding_policy": dict(spec.get("binding_policy") or {}),
                "unit_family": str(spec.get("unit_family") or "").strip(),
                "surface_contract": dict(spec.get("surface_contract") or {}),
            }
        )
    return operands


def _build_concept_metric_label(
    query: str,
    concept_specs: List[Dict[str, Any]],
    operation_family: str,
) -> str:
    ordered_specs = _order_concept_specs_by_query(concept_specs, query)
    labels = [
        str(spec.get("name") or spec.get("label") or "").strip()
        for spec in ordered_specs
        if str(spec.get("name") or spec.get("label") or "").strip()
    ]
    label_policy = dict(CONCEPT_METRIC_LABEL_POLICY)
    templates = dict(label_policy.get("operation_templates") or {})
    label_joiner = str(label_policy.get("label_joiner") or " + ")
    labels_joined = label_joiner.join(labels)
    if operation_family == "ratio" and labels:
        return str(templates.get("ratio") or "{labels_joined}").format(labels_joined=labels_joined)
    if operation_family == "sum" and labels:
        return str(templates.get("sum") or "{labels_joined}").format(labels_joined=labels_joined)
    if operation_family == "difference" and labels:
        if len(labels) >= 2:
            return str(templates.get("difference_two") or "{first_label} {second_label}").format(
                first_label=labels[0],
                second_label=labels[1],
            )
        return str(templates.get("difference_one") or "{label}").format(label=labels[0])
    if operation_family == "growth_rate" and labels:
        return str(templates.get("growth_rate") or "{label}").format(label=labels[0])
    if labels:
        return labels[0]
    return _clean_metric_label(query) or str(label_policy.get("fallback_label") or "")


def _build_concept_task_constraints(
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    operand_specs: Optional[List[Dict[str, Any]]] = None,
    operation_family: str = "",
) -> Dict[str, str]:
    guidance = dict(getattr(ontology, "planner_guidance", {}) or {})
    defaults = dict(guidance.get("dimension_defaults") or {})
    consolidation_scope = _desired_consolidation_scope(query, report_scope)
    if consolidation_scope == "unknown":
        consolidation_scope = str(defaults.get("consolidation_scope") or "unknown")
    period_focus = query_period_focus(query, str(defaults.get("period_focus") or "unknown"))
    if operand_specs:
        period_focus = task_period_focus_from_operands(operation_family, operand_specs, period_focus)
    constraint_policy = dict(TASK_CONSTRAINT_POLICY)
    segment_markers = tuple(str(item) for item in (constraint_policy.get("segment_markers") or ()) if str(item))
    normalized_query = _normalise_spaces(query)
    return {
        "consolidation_scope": str(consolidation_scope or "unknown"),
        "period_focus": str(period_focus or "unknown"),
        "entity_scope": str(defaults.get("entity_scope") or "company"),
        "segment_scope": "segment" if any(marker in normalized_query for marker in segment_markers) else "none",
    }


def _build_explicit_ratio_definition_task(
    *,
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    concept_specs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    text = _normalise_spaces(query)
    compact_text = re.sub(r"\s+", "", text)
    ratio_policy = dict(EXPLICIT_RATIO_DEFINITION_POLICY)
    definition_marker = str(ratio_policy.get("definition_marker") or "")
    ratio_markers = tuple(str(item) for item in (ratio_policy.get("ratio_markers") or ()) if str(item))
    if not compact_text or not definition_marker or definition_marker not in compact_text:
        return None
    if not any(marker in compact_text for marker in ratio_markers):
        return None

    mentions: List[Dict[str, Any]] = []
    seen_mentions: set[tuple[str, int, int]] = set()
    for spec in concept_specs:
        concept_key = _normalise_spaces(str(spec.get("concept") or ""))
        if not concept_key:
            continue
        base_label = str(spec.get("name") or "").strip()
        for surface in _metric_scope_surfaces(spec, base_label):
            compact_surface = re.sub(r"\s+", "", _normalise_spaces(surface))
            if len(compact_surface) < 2:
                continue
            for match in re.finditer(re.escape(compact_surface), compact_text, flags=re.IGNORECASE):
                key = (concept_key, match.start(), match.end())
                if key in seen_mentions:
                    continue
                seen_mentions.add(key)
                mentions.append(
                    {
                        "start": match.start(),
                        "end": match.end(),
                        "length": match.end() - match.start(),
                        "spec": dict(spec),
                    }
                )
    if len(mentions) < 2:
        return None

    for ratio_match in re.finditer(re.escape(definition_marker), compact_text):
        marker_start = ratio_match.start()
        marker_end = ratio_match.end()
        next_ratio_terms = [
            index
            for term in ratio_markers
            for index in [compact_text.find(term, marker_end)]
            if index >= 0
        ]
        ratio_end = min(next_ratio_terms) if next_ratio_terms else len(compact_text)
        left_candidates = [item for item in mentions if int(item["end"]) <= marker_start]
        right_candidates = [
            item
            for item in mentions
            if int(item["start"]) >= marker_end and int(item["start"]) <= ratio_end
        ]
        if not left_candidates or not right_candidates:
            continue
        right_concepts = {
            _normalise_spaces(str(dict(item.get("spec") or {}).get("concept") or ""))
            for item in right_candidates
            if _normalise_spaces(str(dict(item.get("spec") or {}).get("concept") or ""))
        }
        if len(right_concepts) > 1:
            # Multi-component right-hand sides need the generic operand builder so
            # sums such as "A 대비 B, C, D 비중" keep every required numerator.
            continue
        left = sorted(
            left_candidates,
            key=lambda item: (marker_start - int(item["end"]), -int(item["length"])),
        )[0]
        right = sorted(
            right_candidates,
            key=lambda item: (int(item["start"]) - marker_end, -int(item["length"])),
        )[0]
        left_spec = dict(left.get("spec") or {})
        right_spec = dict(right.get("spec") or {})
        if _normalise_spaces(str(left_spec.get("concept") or "")) == _normalise_spaces(
            str(right_spec.get("concept") or "")
        ):
            continue

        denominator = {**left_spec, "role": "denominator_1"}
        numerator = {**right_spec, "role": "numerator_1"}
        operand_specs = _build_concept_required_operands(
            query,
            report_scope,
            [denominator, numerator],
            "ratio",
        )
        if not operand_specs:
            continue
        denominator_label = str(denominator.get("name") or "").strip()
        numerator_label = str(numerator.get("name") or "").strip()
        metric_label = (
            str(ratio_policy.get("metric_label_template") or "").format(
                denominator_label=denominator_label,
                numerator_label=numerator_label,
            )
            if denominator_label and numerator_label
            else _build_concept_metric_label(query, [numerator, denominator], "ratio")
        )
        task = _compose_concept_numeric_task(
            query=query,
            report_scope=report_scope,
            ontology=ontology,
            metric_label=metric_label,
            operation_family="ratio",
            operand_specs=operand_specs,
        )
        if task:
            task["planner_evidence"] = {
                "ratio_definition_marker": definition_marker,
                "denominator_concept": str(denominator.get("concept") or "").strip(),
                "numerator_concept": str(numerator.get("concept") or "").strip(),
            }
            return task
    return None


def _build_concept_numeric_task(
    *,
    query: str,
    topic: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    concept_specs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    explicit_ratio_task = _build_explicit_ratio_definition_task(
        query=query,
        report_scope=report_scope,
        ontology=ontology,
        concept_specs=concept_specs,
    )
    if explicit_ratio_task:
        return explicit_ratio_task
    analysis_task = _build_concept_analysis_task(
        query=query,
        report_scope=report_scope,
        ontology=ontology,
        concept_specs=concept_specs,
    )
    if analysis_task:
        return analysis_task
    group_decomposition_task = _build_group_decomposition_task(
        query=query,
        report_scope=report_scope,
        ontology=ontology,
        concept_specs=concept_specs,
    )
    if group_decomposition_task:
        return group_decomposition_task
    operation_family = _infer_operation_family_from_query(query, ontology)
    operand_specs = _build_concept_required_operands(query, report_scope, concept_specs, operation_family)
    if not operand_specs:
        return None
    metric_label = _build_concept_metric_label(query, operand_specs, operation_family)
    return _compose_concept_numeric_task(
        query=query,
        report_scope=report_scope,
        ontology=ontology,
        metric_label=metric_label,
        operation_family=operation_family,
        operand_specs=operand_specs,
    )


def _metric_scope_surfaces(concept_spec: Dict[str, Any], base_label: str) -> List[str]:
    surfaces: List[str] = []
    for value in (
        base_label,
        str(concept_spec.get("name") or "").strip(),
        *(concept_spec.get("aliases") or []),
        *(concept_spec.get("keywords") or []),
    ):
        normalized = _normalise_spaces(str(value or ""))
        if normalized:
            surfaces.append(normalized)
        compact = re.sub(r"\s+", "", normalized)
        if compact and compact != normalized:
            surfaces.append(compact)
    return list(dict.fromkeys(surface for surface in surfaces if surface))


def _query_clause_spans(text: str) -> List[tuple[int, int]]:
    spans: List[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"(?:[,.;:?!]|\b(?:and|then)\b|그리고|또한|하며|하고)\s*", text, flags=re.IGNORECASE):
        end = match.start()
        if end > start:
            spans.append((start, end))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans or [(0, len(text))]


def _segment_label_shares_metric_clause(query: str, label: str, metric_surfaces: List[str]) -> bool:
    text = _normalise_spaces(query)
    normalized_label = _normalise_spaces(label)
    if not text or not normalized_label or not metric_surfaces:
        return False
    compact_text = re.sub(r"\s+", "", text)
    compact_label = re.sub(r"\s+", "", normalized_label)
    normalized_surfaces = [
        _normalise_spaces(surface)
        for surface in metric_surfaces
        if _normalise_spaces(surface)
    ]
    compact_surfaces = [
        re.sub(r"\s+", "", surface)
        for surface in normalized_surfaces
        if re.sub(r"\s+", "", surface)
    ]

    for start, end in _query_clause_spans(text):
        clause = text[start:end]
        clause_compact = re.sub(r"\s+", "", clause)
        label_in_clause = normalized_label in clause or (compact_label and compact_label in clause_compact)
        if not label_in_clause:
            continue
        if any(surface in clause for surface in normalized_surfaces):
            return True
        if any(surface and surface in clause_compact for surface in compact_surfaces):
            return True

    label_positions = [match.start() for match in re.finditer(re.escape(normalized_label), text, flags=re.IGNORECASE)]
    if not label_positions and compact_label:
        label_positions = [match.start() for match in re.finditer(re.escape(compact_label), compact_text, flags=re.IGNORECASE)]
    if not label_positions:
        return False
    for surface in normalized_surfaces:
        for surface_match in re.finditer(re.escape(surface), text, flags=re.IGNORECASE):
            if any(abs(surface_match.start() - label_pos) <= 24 for label_pos in label_positions):
                return True
    for surface in compact_surfaces:
        for surface_match in re.finditer(re.escape(surface), compact_text, flags=re.IGNORECASE):
            if any(abs(surface_match.start() - label_pos) <= 24 for label_pos in label_positions):
                return True
    return False


def _build_entity_scoped_concept_specs(
    *,
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    operation_family: str,
) -> List[Dict[str, Any]]:
    labels = _extract_segment_labels_from_query(query, report_scope)
    if not labels:
        return []
    if operation_family in {"sum", "difference"} and len(labels) < 2:
        return []
    if operation_family in {"growth_rate", "lookup", "single_value"} and len(labels) < 1:
        return []

    default_metric_policy = dict(HELPER_RUNTIME_POLICY.get("entity_scoped_default_metric") or {})
    default_metric_terms = tuple(str(item) for item in (default_metric_policy.get("query_terms") or ()) if str(item))
    default_metric_label = str(default_metric_policy.get("label") or "").strip()
    normalized_query = _normalise_spaces(query)
    base_label = (
        default_metric_label
        if default_metric_label and any(term in normalized_query for term in default_metric_terms)
        else _infer_generic_metric_label(query, "")
    )
    concept_spec = _infer_generic_concept_spec(base_label, ontology)
    if not concept_spec:
        return []
    metric_surfaces = _metric_scope_surfaces(concept_spec, base_label)
    labels = [
        label
        for label in labels
        if _segment_label_shares_metric_clause(query, label, metric_surfaces)
    ]
    if not labels:
        return []
    if operation_family in {"sum", "difference"} and len(labels) < 2:
        return []

    specs: List[Dict[str, Any]] = []
    for index, label in enumerate(labels, start=1):
        spec = dict(concept_spec)
        spec["name"] = f"{label} {str(concept_spec.get('name') or base_label).strip()}".strip()
        spec["aliases"] = list(
            dict.fromkeys(
                [
                    spec["name"],
                    label,
                    str(concept_spec.get("name") or "").strip(),
                    *(concept_spec.get("aliases") or []),
                ]
            )
        )
        binding_policy = dict(spec.get("binding_policy") or {})
        binding_policy["segment_label"] = label
        spec["binding_policy"] = binding_policy
        if operation_family == "sum":
            spec["role"] = f"addend_{index}"
        elif operation_family == "difference":
            spec["role"] = "minuend" if index == 1 else "subtrahend"
        elif operation_family in {"lookup", "single_value"}:
            spec["role"] = ""
        specs.append(spec)
        if operation_family == "difference" and len(specs) >= 2:
            break
        if operation_family in {"growth_rate", "lookup", "single_value"}:
            break
    return specs


def _build_heuristic_numeric_task(
    *,
    query: str,
    topic: str,
    intent: str,
    report_scope: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    metric_label = _infer_generic_metric_label(query, topic)
    operand_specs = _build_generic_required_operands(query, report_scope)
    preferred_statement_types, preferred_sections = _infer_statement_and_section_hints(query)
    for spec in operand_specs:
        preferred_statement_types.extend(spec.get("preferred_statement_types") or [])
        preferred_sections.extend(spec.get("preferred_sections") or [])
    preferred_statement_types = list(dict.fromkeys(item for item in preferred_statement_types if str(item).strip()))
    preferred_sections = list(dict.fromkeys(item for item in preferred_sections if str(item).strip()))
    operation_family = _infer_operation_family_from_query(query, get_financial_ontology())
    constraints = {
        "consolidation_scope": _desired_consolidation_scope(query, report_scope),
        "period_focus": query_period_focus(query, "unknown"),
        "entity_scope": "company",
        "segment_scope": (
            "segment"
            if any(
                str(marker) and str(marker) in _normalise_spaces(query)
                for marker in (TASK_CONSTRAINT_POLICY.get("segment_markers") or ())
            )
            else "none"
        ),
    }
    constraints["period_focus"] = task_period_focus_from_operands(
        operation_family,
        operand_specs,
        str(constraints.get("period_focus") or "unknown"),
    )
    retrieval_queries = _build_generic_retrieval_queries(
        query=query,
        metric_label=metric_label,
        operand_specs=operand_specs,
        preferred_sections=preferred_sections,
        report_scope=report_scope,
        constraints=constraints,
    )
    if not retrieval_queries:
        return None
    return {
        "task_id": "task_1",
        "metric_family": "generic_numeric",
        "metric_label": metric_label,
        "query": query,
        "operation_family": operation_family,
        "required_operands": operand_specs,
        "preferred_statement_types": preferred_statement_types,
        "preferred_sections": preferred_sections,
        "retrieval_queries": retrieval_queries,
        "constraints": constraints,
    }


def _task_dependency_query_years(task: Dict[str, Any], report_scope: Dict[str, Any]) -> List[int]:
    query_text = " ".join(
        part
        for part in [
            str(task.get("query") or "").strip(),
            str(task.get("metric_label") or "").strip(),
        ]
        if part
    )
    years = _extract_year_tokens(query_text, report_scope)
    if not years:
        scope_year_raw = report_scope.get("year")
        try:
            if scope_year_raw not in (None, ""):
                years = [int(scope_year_raw)]
        except (TypeError, ValueError):
            years = []
    return years


def _task_binding_period_hint(
    operand: Dict[str, Any],
    *,
    task: Dict[str, Any],
    report_scope: Dict[str, Any],
) -> str:
    query_years = _task_dependency_query_years(task, report_scope)
    target_years = operand_target_years(operand, query_years)
    if target_years:
        return str(target_years[0])
    period_hint = _normalise_spaces(str(operand.get("period_hint") or ""))
    if period_hint:
        return period_hint
    label_match = re.search(r"(20\d{2})", str(operand.get("label") or ""))
    if label_match:
        return str(label_match.group(1))
    return ""


def _task_output_slots_for_dependency(
    task: Dict[str, Any],
    *,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    operation_family = str(task.get("operation_family") or "").strip().lower()
    if operation_family not in {"lookup", "single_value"}:
        return []
    outputs: List[Dict[str, Any]] = []
    for operand in list(task.get("required_operands") or []):
        concept = _normalise_spaces(str(operand.get("concept") or ""))
        if not concept:
            continue
        outputs.append(
            {
                "slot": "primary_value",
                "role": _normalise_spaces(str(operand.get("role") or "")) or "primary_value",
                "concept": concept,
                "period": _task_binding_period_hint(dict(operand), task=task, report_scope=report_scope),
                "label": _normalise_spaces(str(operand.get("label") or task.get("metric_label") or "")),
                "segment_label": operand_segment_label(dict(operand)),
                "binding_policy": dict(operand.get("binding_policy") or {}),
            }
        )
    return outputs


def _task_input_bindings_for_dependency(
    task: Dict[str, Any],
    *,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    operation_family = str(task.get("operation_family") or "").strip().lower()
    if operation_family not in {"difference", "growth_rate", "ratio", "sum"}:
        return []
    bindings: List[Dict[str, Any]] = []
    for operand in list(task.get("required_operands") or []):
        concept = _normalise_spaces(str(operand.get("concept") or ""))
        if not concept:
            continue
        bindings.append(
            {
                "role": _normalise_spaces(str(operand.get("role") or "")),
                "concept": concept,
                "period": _task_binding_period_hint(dict(operand), task=task, report_scope=report_scope),
                "label": _normalise_spaces(str(operand.get("label") or "")),
                "preferred_task_id": "",
                "source_slot": "primary_value",
                "source_preference": ["retrieval"],
                "segment_label": operand_segment_label(dict(operand)),
                "binding_policy": dict(operand.get("binding_policy") or {}),
            }
        )
    return bindings


def _next_dependency_task_id(tasks: List[Dict[str, Any]]) -> int:
    max_index = 0
    for task in tasks:
        match = re.match(r"task_(\d+)$", str(task.get("task_id") or "").strip())
        if match:
            max_index = max(max_index, int(match.group(1)))
    return max_index + 1


def _dependency_metric_label(binding: Dict[str, Any]) -> str:
    label = _normalise_spaces(str(binding.get("label") or ""))
    period = _normalise_spaces(str(binding.get("period") or ""))
    if period and label and period not in label:
        return f"{period}년 {label}" if re.fullmatch(r"20\d{2}", period) else f"{period} {label}"
    return label or (f"{period} 값" if period else "조회값")


def _lookup_constraint_from_binding(binding: Dict[str, Any], base_constraints: Dict[str, Any]) -> Dict[str, str]:
    constraints = dict(base_constraints or {})
    role = _normalise_spaces(str(binding.get("role") or ""))
    if role == "current_period":
        constraints["period_focus"] = "current"
    elif role == "prior_period":
        constraints["period_focus"] = "prior"
    else:
        constraints["period_focus"] = str(constraints.get("period_focus") or "unknown")
    return constraints


def _concept_spec_for_key(ontology: Any, key: str) -> Dict[str, Any]:
    concept_key = _normalise_spaces(str(key or ""))
    if not concept_key:
        return {}
    for spec in list(getattr(ontology, "all_concept_specs", lambda: [])() or []):
        if bool(spec.get("is_group")):
            continue
        if _normalise_spaces(str(spec.get("concept") or "")) == concept_key:
            return dict(spec)
    return {}


def _spec_mentions_query(spec: Dict[str, Any], query: str) -> bool:
    text = _normalise_spaces(query)
    if not text:
        return False
    values = [
        str(spec.get("name") or "").strip(),
        *(spec.get("aliases") or []),
        *(spec.get("keywords") or []),
    ]
    return any(
        _normalise_spaces(value) in text
        for value in values
        if _normalise_spaces(value)
    )


def _group_decomposition_query_matches(
    *,
    query: str,
    group_spec: Dict[str, Any],
    hints: Dict[str, Any],
    ontology: Any,
) -> bool:
    text = _normalise_spaces(query)
    if not text:
        return False

    any_of = [
        _normalise_spaces(str(token))
        for token in (hints.get("query_any_of") or [])
        if _normalise_spaces(str(token))
    ]
    all_of = [
        _normalise_spaces(str(token))
        for token in (hints.get("query_all_of") or [])
        if _normalise_spaces(str(token))
    ]
    if any_of and not any(token in text for token in any_of):
        return False
    if all_of and not all(token in text for token in all_of):
        return False

    member_specs = [dict(spec) for spec in (group_spec.get("member_specs") or []) if dict(spec)]
    if bool(hints.get("require_all_member_mentions", False)) and any(
        not _spec_mentions_query(spec, query) for spec in member_specs
    ):
        return False

    denominator_concepts = [
        str(item).strip()
        for item in (hints.get("denominator_concepts") or [])
        if str(item).strip()
    ]
    denominator_specs = [_concept_spec_for_key(ontology, key) for key in denominator_concepts]
    denominator_specs = [spec for spec in denominator_specs if spec]
    if bool(hints.get("require_denominator_mentions", False)) and any(
        not _spec_mentions_query(spec, query) for spec in denominator_specs
    ):
        return False
    return True


def _build_group_decomposition_task(
    *,
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    concept_specs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    for group_spec in _order_concept_specs_by_query(concept_specs, query):
        if not bool(group_spec.get("is_group")):
            continue
        hints = dict(group_spec.get("decomposition_hints") or {})
        if not hints:
            continue
        if not _group_decomposition_query_matches(
            query=query,
            group_spec=group_spec,
            hints=hints,
            ontology=ontology,
        ):
            continue

        operation_family = str(hints.get("preferred_operation") or "").strip() or _infer_operation_family_from_query(query, ontology)
        member_role_prefix = str(hints.get("member_role_prefix") or "numerator").strip() or "numerator"
        member_roles = [
            str(item).strip()
            for item in (hints.get("member_roles") or [])
            if str(item).strip()
        ]
        numerator_specs = [
            {
                **dict(spec),
                "role": member_roles[index - 1] if index <= len(member_roles) else f"{member_role_prefix}_{index}",
            }
            for index, spec in enumerate((group_spec.get("member_specs") or []), start=1)
            if dict(spec)
        ]
        denominator_specs: List[Dict[str, Any]] = []
        for index, concept_key in enumerate((hints.get("denominator_concepts") or []), start=1):
            concept_spec = _concept_spec_for_key(ontology, str(concept_key).strip())
            if not concept_spec:
                continue
            denominator_specs.append({**concept_spec, "role": f"denominator_{index}"})

        denominator_concept_keys = [
            str(item).strip()
            for item in (hints.get("denominator_concepts") or [])
            if str(item).strip()
        ]
        if not numerator_specs:
            continue
        if denominator_concept_keys and not denominator_specs:
            continue

        ordered_specs = [*numerator_specs, *denominator_specs]
        operand_specs = _build_concept_required_operands(
            query,
            report_scope,
            ordered_specs,
            operation_family,
        )
        if not operand_specs:
            continue

        metric_label = str(hints.get("metric_label") or "").strip() or _build_concept_metric_label(
            query,
            ordered_specs,
            operation_family,
        )
        task = _compose_concept_numeric_task(
            query=query,
            report_scope=report_scope,
            ontology=ontology,
            metric_label=metric_label,
            operation_family=operation_family,
            operand_specs=operand_specs,
        )
        if task and hints:
            task["decomposition_hints"] = dict(hints)
        return task
    return None


def _build_concept_analysis_task(
    *,
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    concept_specs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    text = _normalise_spaces(query)
    if not text:
        return None

    specs_by_concept = {
        _normalise_spaces(str(spec.get("concept") or "")): dict(spec)
        for spec in concept_specs
        if _normalise_spaces(str(spec.get("concept") or ""))
    }
    for numerator_spec in _order_concept_specs_by_query(concept_specs, query):
        hints = dict(numerator_spec.get("analysis_hints") or {})
        if not hints:
            continue
        query_any_of = [
            _normalise_spaces(str(token))
            for token in (hints.get("query_any_of") or [])
            if _normalise_spaces(str(token))
        ]
        if query_any_of and not any(token in text for token in query_any_of):
            continue

        operation_family = str(hints.get("preferred_operation") or "ratio").strip().lower()
        if operation_family != "ratio":
            continue
        for denominator_index, denominator_key in enumerate((hints.get("denominator_concepts") or []), start=1):
            denominator_spec = specs_by_concept.get(_normalise_spaces(str(denominator_key or "")))
            if not denominator_spec:
                continue
            numerator = {**dict(numerator_spec), "role": "numerator_1"}
            denominator = {**denominator_spec, "role": f"denominator_{denominator_index}"}
            operand_specs = _build_concept_required_operands(
                query,
                report_scope,
                [numerator, denominator],
                operation_family,
            )
            if not operand_specs:
                continue
            metric_label = str(hints.get("metric_label") or "").strip() or _build_concept_metric_label(
                query,
                [numerator, denominator],
                operation_family,
            )
            task = _compose_concept_numeric_task(
                query=query,
                report_scope=report_scope,
                ontology=ontology,
                metric_label=metric_label,
                operation_family=operation_family,
                operand_specs=operand_specs,
            )
            if task:
                task["analysis_hints"] = dict(hints)
                return task
    return None


def _compose_concept_numeric_task(
    *,
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    metric_label: str,
    operation_family: str,
    operand_specs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not operand_specs:
        return None
    preferred_statement_types: List[str] = []
    preferred_sections: List[str] = []
    query_statement_types, query_sections = _infer_statement_and_section_hints(query)
    preferred_statement_types.extend(query_statement_types)
    preferred_sections.extend(query_sections)
    for spec in operand_specs:
        preferred_statement_types.extend(spec.get("preferred_statement_types") or [])
        preferred_sections.extend(spec.get("preferred_sections") or [])
    preferred_statement_types = list(dict.fromkeys(item for item in preferred_statement_types if str(item).strip()))
    preferred_sections = list(dict.fromkeys(item for item in preferred_sections if str(item).strip()))
    constraints = _build_concept_task_constraints(
        query,
        report_scope,
        ontology,
        operand_specs=operand_specs,
        operation_family=operation_family,
    )
    retrieval_queries = _build_generic_retrieval_queries(
        query=query,
        metric_label=metric_label,
        operand_specs=operand_specs,
        preferred_sections=preferred_sections,
        report_scope=report_scope,
        constraints=constraints,
    )
    task_query = _build_metric_task_query(
        original_query=query,
        metric_label=metric_label,
        constraints=constraints,
        operand_specs=operand_specs,
        report_scope=report_scope,
    )
    result_unit = infer_concept_ratio_result_unit(query, metric_label, operation_family)
    return {
        "task_id": "task_1",
        "metric_family": f"concept_{operation_family}",
        "metric_label": metric_label,
        "query": task_query,
        "operation_family": operation_family,
        "result_unit": result_unit,
        "required_operands": operand_specs,
        "preferred_statement_types": preferred_statement_types,
        "preferred_sections": preferred_sections,
        "retrieval_queries": retrieval_queries,
        "constraints": constraints,
    }


def _split_multi_lookup_concept_task(
    task: Dict[str, Any],
    *,
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
) -> List[Dict[str, Any]]:
    operation_family = _normalise_spaces(str(task.get("operation_family") or "")).lower()
    if operation_family not in {"lookup", "single_value"}:
        return [dict(task)]
    operand_specs = [dict(item) for item in (task.get("required_operands") or [])]
    if len(operand_specs) <= 1:
        return [dict(task)]

    sibling_surfaces_by_index: Dict[int, List[str]] = {}
    for index, current_operand in enumerate(operand_specs):
        current_surfaces: List[str] = []
        for other_index, operand in enumerate(operand_specs):
            if other_index == index:
                continue
            surface_contract = dict(operand.get("surface_contract") or {})
            current_surfaces.extend(
                str(item).strip()
                for item in (
                    [operand.get("label")]
                    + list(operand.get("aliases") or [])
                    + list(surface_contract.get("positive") or [])
                )
                if str(item or "").strip()
            )
        sibling_surfaces_by_index[index] = list(dict.fromkeys(current_surfaces))

    split_tasks: List[Dict[str, Any]] = []
    for zero_based_index, operand in enumerate(operand_specs):
        index = zero_based_index + 1
        metric_label = str(operand.get("label") or task.get("metric_label") or "").strip()
        constraints = _build_concept_task_constraints(
            query,
            report_scope,
            ontology,
            operand_specs=[operand],
            operation_family="lookup",
        )
        preferred_statement_types = list(
            dict.fromkeys(
                [
                    *list(operand.get("preferred_statement_types") or []),
                    *list(task.get("preferred_statement_types") or []),
                ]
            )
        )
        preferred_sections = list(
            dict.fromkeys(
                [
                    *list(operand.get("preferred_sections") or []),
                    *list(task.get("preferred_sections") or []),
                ]
            )
        )
        retrieval_queries = _build_generic_retrieval_queries(
            query=query,
            metric_label=metric_label,
            operand_specs=[operand],
            preferred_sections=preferred_sections,
            report_scope=report_scope,
            constraints=constraints,
        )
        task_query = _build_metric_task_query(
            original_query=query,
            metric_label=metric_label,
            constraints=constraints,
            operand_specs=[operand],
            report_scope=report_scope,
        )
        sibling_lookup_surfaces = list(
            dict.fromkeys(
                [
                    *list(task.get("sibling_lookup_surfaces") or []),
                    *sibling_surfaces_by_index.get(zero_based_index, []),
                ]
            )
        )
        split_tasks.append(
            {
                **dict(task),
                "task_id": f"task_{index}",
                "metric_family": "concept_lookup",
                "metric_label": metric_label,
                "query": task_query,
                "operation_family": "lookup",
                "result_unit": "",
                "required_operands": [operand],
                "preferred_statement_types": preferred_statement_types,
                "preferred_sections": preferred_sections,
                "retrieval_queries": retrieval_queries,
                "constraints": constraints,
                "sibling_lookup_surfaces": sibling_lookup_surfaces,
            }
        )
    return split_tasks


def _build_lookup_producer_task_from_binding(
    *,
    binding: Dict[str, Any],
    consumer_task: Dict[str, Any],
    next_task_id: str,
    report_scope: Dict[str, Any],
) -> Dict[str, Any]:
    consumer_operands = [dict(item) for item in (consumer_task.get("required_operands") or [])]
    source_operand = next(
        (
            dict(item)
            for item in consumer_operands
            if _normalise_spaces(str(item.get("role") or "")) == _normalise_spaces(str(binding.get("role") or ""))
            and _normalise_spaces(str(item.get("concept") or "")) == _normalise_spaces(str(binding.get("concept") or ""))
        ),
        {},
    )
    operand = dict(source_operand or {})
    operand["label"] = _dependency_metric_label(binding)
    operand["period_hint"] = _normalise_spaces(str(binding.get("period") or operand.get("period_hint") or ""))
    operand["role"] = _normalise_spaces(str(binding.get("role") or operand.get("role") or ""))
    binding_concept = _normalise_spaces(str(binding.get("concept") or operand.get("concept") or ""))
    if binding_concept:
        operand["concept"] = binding_concept
        concept_spec = _concept_spec_for_key(get_financial_ontology(), binding_concept)
        if concept_spec:
            operand = _augment_generic_operand_with_concept(operand, concept_spec=concept_spec)
    explicit_binding_policy = dict(binding.get("binding_policy") or {})
    binding_policy = dict(operand.get("binding_policy") or {})
    if explicit_binding_policy:
        binding_policy.update(explicit_binding_policy)
    elif lookup_prefers_canonical_statement_rows(operand):
        # Canonical statement-row lookups should be free to bind to the statement
        # row itself when only concept-default aggregate preferences are present.
        binding_policy.pop("prefer_value_roles", None)
        binding_policy.pop("prefer_aggregation_stages", None)
    binding_segment = _normalise_spaces(str(binding.get("segment_label") or ""))
    if binding_segment:
        binding_policy["segment_label"] = binding_segment
    operand["binding_policy"] = binding_policy
    lookup_query_surfaces = lookup_query_surface_preferences(operand)
    if lookup_query_surfaces:
        existing_aliases = [str(item).strip() for item in (operand.get("aliases") or []) if str(item).strip()]
        operand["aliases"] = list(dict.fromkeys([*lookup_query_surfaces, *existing_aliases]))

    constraints = _lookup_constraint_from_binding(
        binding,
        dict(consumer_task.get("constraints") or {}),
    )
    preferred_sections = list(
        dict.fromkeys(
            [
                *list(consumer_task.get("preferred_sections") or []),
                *list(operand.get("preferred_sections") or []),
            ]
        )
    )
    preferred_statement_types = list(
        dict.fromkeys(
            [
                *list(operand.get("preferred_statement_types") or []),
                *list(consumer_task.get("preferred_statement_types") or []),
            ]
        )
    )
    if lookup_prefers_canonical_statement_rows(operand):
        canonical_types, canonical_sections = lookup_canonical_statement_preferences(operand)
        # For producer lookup tasks that explicitly prefer canonical statement
        # rows, keep retrieval focused on those statement types/sections instead
        # of widening back out to note sections from downstream consumers.
        if canonical_types:
            preferred_statement_types = list(dict.fromkeys(canonical_types))
        if canonical_sections:
            preferred_sections = list(dict.fromkeys(canonical_sections))
        operand["preferred_statement_types"] = list(preferred_statement_types)
        operand["preferred_sections"] = list(preferred_sections)
    retrieval_queries = _build_generic_retrieval_queries(
        query=str(consumer_task.get("query") or consumer_task.get("metric_label") or ""),
        metric_label=str(operand.get("label") or ""),
        operand_specs=[operand],
        preferred_sections=preferred_sections,
        report_scope=report_scope,
        constraints=constraints,
    )
    task_query = _build_metric_task_query(
        original_query=str(consumer_task.get("query") or consumer_task.get("metric_label") or ""),
        metric_label=str(operand.get("label") or ""),
        constraints=constraints,
        operand_specs=[operand],
        report_scope=report_scope,
    )
    return {
        "task_id": next_task_id,
        "metric_family": "concept_lookup" if _normalise_spaces(str(binding.get("concept") or "")) else "generic_numeric",
        "metric_label": str(operand.get("label") or ""),
        "query": task_query,
        "operation_family": "lookup",
        "required_operands": [operand],
        "preferred_statement_types": preferred_statement_types,
        "preferred_sections": preferred_sections,
        "retrieval_queries": retrieval_queries,
        "constraints": constraints,
    }


def _synthesize_missing_lookup_dependency_tasks(
    tasks: List[Dict[str, Any]],
    *,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    base_tasks = [dict(task) for task in (tasks or [])]
    producer_catalog: List[tuple[str, Dict[str, Any]]] = []
    for task in base_tasks:
        producer_task_id = _normalise_spaces(str(task.get("task_id") or ""))
        if not producer_task_id:
            continue
        for output in _task_output_slots_for_dependency(task, report_scope=report_scope):
            producer_catalog.append((producer_task_id, dict(output)))

    next_index = _next_dependency_task_id(base_tasks)
    created_keys: set[tuple[str, str, str]] = set()
    synthetic_tasks: List[Dict[str, Any]] = []
    for task in base_tasks:
        operation_family = _normalise_spaces(str(task.get("operation_family") or "")).lower()
        if operation_family not in {"difference", "growth_rate", "ratio", "sum"}:
            continue
        for binding in _task_input_bindings_for_dependency(task, report_scope=report_scope):
            if any(_dependency_binding_matches_output(binding, output) for _task_id, output in producer_catalog):
                continue
            binding_key = (
                _normalise_spaces(str(binding.get("concept") or "")),
                _normalise_spaces(str(binding.get("period") or "")),
                _normalise_spaces(str(binding.get("segment_label") or "")),
            )
            if not binding_key[0] or binding_key in created_keys:
                continue
            synthetic_task = _build_lookup_producer_task_from_binding(
                binding=binding,
                consumer_task=task,
                next_task_id=f"task_{next_index}",
                report_scope=report_scope,
            )
            next_index += 1
            synthetic_tasks.append(synthetic_task)
            created_keys.add(binding_key)
            producer_catalog.append(
                (
                    str(synthetic_task.get("task_id") or "").strip(),
                    {
                        "slot": "primary_value",
                        "role": _normalise_spaces(str(binding.get("role") or "")) or "primary_value",
                        "concept": _normalise_spaces(str(binding.get("concept") or "")),
                        "period": _normalise_spaces(str(binding.get("period") or "")),
                        "label": _normalise_spaces(str(binding.get("label") or "")),
                        "segment_label": _normalise_spaces(str(binding.get("segment_label") or "")),
                    },
                )
            )
    return base_tasks + synthetic_tasks


def _dependency_binding_matches_output(
    binding: Dict[str, Any],
    output: Dict[str, Any],
) -> bool:
    if _normalise_spaces(str(binding.get("concept") or "")) != _normalise_spaces(str(output.get("concept") or "")):
        return False
    binding_period = _normalise_spaces(str(binding.get("period") or ""))
    output_period = _normalise_spaces(str(output.get("period") or ""))
    if binding_period and output_period and binding_period != output_period:
        return False
    binding_segment = _normalise_spaces(str(binding.get("segment_label") or ""))
    output_segment = _normalise_spaces(str(output.get("segment_label") or ""))
    if binding_segment and output_segment and binding_segment != output_segment:
        return False
    if binding_segment and not output_segment:
        label_text = _normalise_spaces(str(output.get("label") or "")).lower()
        if binding_segment.lower() not in label_text:
            return False
    return True


def _topologically_order_dependency_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    task_ids = [str(task.get("task_id") or "").strip() for task in tasks]
    if not task_ids:
        return tasks
    indegree: Dict[str, int] = {task_id: 0 for task_id in task_ids if task_id}
    adjacency: Dict[str, List[str]] = {task_id: [] for task_id in indegree}
    original_index = {task_id: index for index, task_id in enumerate(task_ids) if task_id}
    task_by_id = {str(task.get("task_id") or "").strip(): dict(task) for task in tasks if str(task.get("task_id") or "").strip()}

    for task in tasks:
        task_id = str(task.get("task_id") or "").strip()
        if not task_id:
            continue
        for dependency in list(task.get("depends_on") or []):
            dependency_id = _normalise_spaces(str(dependency or ""))
            if not dependency_id or dependency_id not in indegree or dependency_id == task_id:
                continue
            indegree[task_id] += 1
            adjacency[dependency_id].append(task_id)

    ready = sorted(
        [task_id for task_id, count in indegree.items() if count == 0],
        key=lambda value: original_index.get(value, 10_000),
    )
    ordered_ids: List[str] = []
    while ready:
        task_id = ready.pop(0)
        ordered_ids.append(task_id)
        for child in sorted(adjacency.get(task_id, []), key=lambda value: original_index.get(value, 10_000)):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort(key=lambda value: original_index.get(value, 10_000))

    if len(ordered_ids) != len(indegree):
        return [dict(task) for task in tasks]
    return [task_by_id[task_id] for task_id in ordered_ids]


def _annotate_task_dependencies(
    tasks: List[Dict[str, Any]],
    *,
    report_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    annotated_tasks = _synthesize_missing_lookup_dependency_tasks(
        tasks,
        report_scope=report_scope,
    )
    producer_catalog: List[tuple[str, Dict[str, Any]]] = []

    for task in annotated_tasks:
        outputs = _task_output_slots_for_dependency(task, report_scope=report_scope)
        task["produces"] = outputs
        producer_task_id = _normalise_spaces(str(task.get("task_id") or ""))
        if not producer_task_id:
            continue
        for output in outputs:
            producer_catalog.append((producer_task_id, dict(output)))

    for task in annotated_tasks:
        inputs = _task_input_bindings_for_dependency(task, report_scope=report_scope)
        dependencies: List[str] = []
        for binding in inputs:
            for producer_task_id, output in producer_catalog:
                if producer_task_id == _normalise_spaces(str(task.get("task_id") or "")):
                    continue
                if not _dependency_binding_matches_output(binding, output):
                    continue
                binding["preferred_task_id"] = producer_task_id
                binding["source_preference"] = ["task_output", "retrieval"]
                if producer_task_id not in dependencies:
                    dependencies.append(producer_task_id)
                break
        task["inputs"] = inputs
        task["depends_on"] = dependencies

    return _topologically_order_dependency_tasks(annotated_tasks)


def _build_task_constraints(
    query: str,
    report_scope: Dict[str, Any],
    ontology: Any,
    metric_key: str,
) -> Dict[str, str]:
    defaults = dict(ontology.default_constraints_for_metric(metric_key) or {})
    defaults["consolidation_scope"] = _desired_consolidation_scope(query, report_scope)
    defaults["period_focus"] = query_period_focus(query, str(defaults.get("period_focus") or "unknown"))
    return {
        "consolidation_scope": str(defaults.get("consolidation_scope") or "unknown"),
        "period_focus": str(defaults.get("period_focus") or "unknown"),
        "entity_scope": str(defaults.get("entity_scope") or "unknown"),
        "segment_scope": str(defaults.get("segment_scope") or "none"),
    }


def _build_retrieval_query_bundle(
    query: str,
    topic: str,
    metric_key: str,
    ontology: Any,
) -> List[str]:
    metric = ontology.metric_family(metric_key) or {}
    display_name = str(metric.get("display_name") or "").strip()
    keywords = ontology.retrieval_keywords_for_metric(metric_key)
    preferred_sections = ontology.preferred_sections(display_name or query, topic, "comparison")
    primary_bits = [query, display_name]
    primary_bits.extend(keywords[:4])
    if preferred_sections:
        primary_bits.extend(preferred_sections[:2])
    primary = _normalise_spaces(" ".join(primary_bits))

    bundles = [primary] if primary else []
    for operand in ontology.build_operand_spec(metric_key):
        operand_bits = [query, display_name, str(operand.get("label") or "")]
        operand_bits.extend(list(operand.get("aliases") or [])[:2])
        operand_bits.extend(list(operand.get("preferred_sections") or [])[:1])
        operand_query = _normalise_spaces(" ".join(operand_bits))
        if operand_query:
            bundles.append(operand_query)
    return list(dict.fromkeys(item for item in bundles if item))


def _build_metric_task_query(
    *,
    original_query: str,
    metric_label: str,
    constraints: Dict[str, str],
    operand_specs: List[Dict[str, Any]],
    report_scope: Dict[str, Any],
) -> str:
    query_text = _normalise_spaces(original_query)
    year = report_scope.get("year")
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    year_suffix_template = str(period_policy.get("year_suffix_template") or "{year}")
    year_text = f"{year_suffix_template.format(year=year)} " if str(year or "").strip() else ""
    consolidation_scope = str((constraints or {}).get("consolidation_scope") or "unknown").strip()
    consolidation_text = ""
    scope_prefix_labels = dict(CONSOLIDATION_SCOPE_POLICY.get("query_prefix_labels") or {})
    if consolidation_scope == "consolidated":
        consolidation_text = f"{scope_prefix_labels.get('consolidated') or ''} "
    elif consolidation_scope == "separate":
        consolidation_text = f"{scope_prefix_labels.get('separate') or ''} "

    query_policy = dict(METRIC_TASK_QUERY_POLICY)
    operand_labels = [str(spec.get("label") or "").strip() for spec in operand_specs if str(spec.get("label") or "").strip()]
    operand_joiner = str(query_policy.get("operand_joiner") or "/")
    operand_hint = (
        str(query_policy.get("operand_hint_template") or "{labels}").format(labels=operand_joiner.join(operand_labels))
        if len(operand_labels) >= 2
        else ""
    )
    canonical_query = _normalise_spaces(
        str(query_policy.get("canonical_query_template") or "{metric_label}").format(
            year_text=year_text,
            consolidation_text=consolidation_text,
            metric_label=metric_label,
            operand_hint=operand_hint,
        )
    )
    if canonical_query:
        return canonical_query
    return query_text or metric_label


def _build_semantic_numeric_plan(
    query: str,
    topic: str,
    intent: str,
    report_scope: Dict[str, Any],
    target_metric_family: str,
) -> Dict[str, Any]:
    """Translate a query into one or more numeric subtasks.

    This is the main pure planning entrypoint. It prefers ontology-backed tasks
    and falls back to heuristic generic-numeric tasks when no clean ontology
    match is available.
    """
    ontology = get_financial_ontology()
    matches = ontology.match_metric_families(query, topic, intent)
    operation_family = _infer_operation_family_from_query(query, ontology)
    concept_specs = ontology.concept_specs(query, topic, intent)
    planner_notes: List[str] = [
        f"planner_input_intent:{str(intent or 'unknown').strip() or 'unknown'}",
        f"planner_inferred_operation:{operation_family or 'unknown'}",
        f"planner_ontology_matches:{len(matches)}",
        f"planner_concept_specs:{len(concept_specs)}",
    ]
    matched_metric_keys = {
        str(item.get("key") or "").strip()
        for item in matches
        if str(item.get("key") or "").strip()
    }
    strong_metric_keys = [
        str(item.get("key") or "").strip()
        for item in matches
        if str(item.get("key") or "").strip()
        and query_mentions_metric(query, item)
        and (
            str(item.get("formula_family") or "").strip().lower() == operation_family
            or (
                operation_family in {"lookup", "single_value"}
                and str(item.get("formula_family") or "").strip().lower()
                in {"sum", "difference", "ratio", "growth_rate"}
            )
        )
    ]
    strong_metric_keys = list(dict.fromkeys(strong_metric_keys))
    metric_keys: List[str] = []
    entity_scoped_specs = _build_entity_scoped_concept_specs(
        query=query,
        report_scope=report_scope,
        ontology=ontology,
        operation_family=operation_family,
    )
    planner_notes.append(f"planner_entity_scoped_specs:{len(entity_scoped_specs)}")
    concept_specs_have_segment_binding = any(
        _normalise_spaces(str(dict(spec.get("binding_policy") or {}).get("segment_label") or ""))
        for spec in concept_specs
    )
    if entity_scoped_specs and (
        not concept_specs
        or (
            operation_family in {"sum", "difference"}
            and len(concept_specs) == 1
            and len(entity_scoped_specs) >= 2
        )
        or (
            operation_family in {"growth_rate", "lookup", "single_value"}
            and not concept_specs_have_segment_binding
        )
    ):
        concept_specs = entity_scoped_specs
        planner_notes.append("entity_scoped_concept_fallback")
    if concept_specs and operation_family in {"lookup", "single_value"}:
        retained_metric_keys: List[str] = []
        for metric_key in strong_metric_keys:
            metric = ontology.metric_family(metric_key) or {}
            formula_family = str(metric.get("formula_family") or "").strip().lower()
            if formula_family == operation_family or bool(metric.get("direct_lookup_preferred")):
                retained_metric_keys.append(metric_key)
                continue
            planner_notes.append(f"drop_composite_metric_for_concept_lookup:{metric_key}")
        strong_metric_keys = retained_metric_keys
    if strong_metric_keys and concept_specs:
        planner_notes.append("metric_match_preferred_over_concept")
    if not target_metric_family and concept_specs and strong_metric_keys and _extract_generic_ratio_operand_specs(query):
        concept_task = _build_concept_numeric_task(
            query=query,
            topic=topic,
            report_scope=report_scope,
            ontology=ontology,
            concept_specs=concept_specs,
        )
        if concept_task:
            concept_tasks = _split_multi_lookup_concept_task(
                concept_task,
                query=query,
                report_scope=report_scope,
                ontology=ontology,
            )
            return {
                "status": "concept_fallback",
                "fallback_to_general_search": False,
                "planned_metric_families": [
                    str(task.get("metric_family") or "").strip()
                    for task in concept_tasks
                    if str(task.get("metric_family") or "").strip()
                ],
                "tasks": concept_tasks,
                "planner_notes": planner_notes
                + ["explicit_ratio_concept_preferred", "planner_fallback:explicit_ratio_concept_preferred"],
            }
    if not target_metric_family and concept_specs and not strong_metric_keys:
        concept_task = _build_concept_numeric_task(
            query=query,
            topic=topic,
            report_scope=report_scope,
            ontology=ontology,
            concept_specs=concept_specs,
        )
        if concept_task:
            concept_tasks = _split_multi_lookup_concept_task(
                concept_task,
                query=query,
                report_scope=report_scope,
                ontology=ontology,
            )
            return {
                "status": "concept_fallback",
                "fallback_to_general_search": False,
                "planned_metric_families": [
                    str(task.get("metric_family") or "").strip()
                    for task in concept_tasks
                    if str(task.get("metric_family") or "").strip()
                ],
                "tasks": concept_tasks,
                "planner_notes": planner_notes + ["concept_first_preferred", "planner_fallback:concept_first_preferred"],
            }
    if target_metric_family:
        planner_notes.append(f"planner_target_metric:{target_metric_family}")
        target_metric = ontology.metric_family(target_metric_family) or {}
        target_operand_specs = ontology.build_operand_spec(target_metric_family) if target_metric else []
        component_match_count = query_component_match_count(query, target_operand_specs)
        if target_metric and (
            query_mentions_metric(query, target_metric)
            or (
                target_metric_family in matched_metric_keys
                and component_match_count >= 2
            )
        ):
            metric_keys.append(target_metric_family)
        else:
            planner_notes.append(f"drop_weak_target:{target_metric_family}")
    metric_keys.extend(strong_metric_keys)
    metric_keys = list(dict.fromkeys(metric_keys))

    tasks: List[Dict[str, Any]] = []
    if not metric_keys:
        planner_notes.append("planner_no_metric_keys")
        concept_task = _build_concept_numeric_task(
            query=query,
            topic=topic,
            report_scope=report_scope,
            ontology=ontology,
            concept_specs=concept_specs,
        )
        if concept_task:
            concept_tasks = _split_multi_lookup_concept_task(
                concept_task,
                query=query,
                report_scope=report_scope,
                ontology=ontology,
            )
            return {
                "status": "concept_fallback",
                "fallback_to_general_search": False,
                "planned_metric_families": [
                    str(task.get("metric_family") or "").strip()
                    for task in concept_tasks
                    if str(task.get("metric_family") or "").strip()
                ],
                "tasks": concept_tasks,
                "planner_notes": planner_notes + ["concept_numeric_task", "planner_fallback:concept_numeric_task"],
            }
        heuristic_task = _build_heuristic_numeric_task(
            query=query,
            topic=topic,
            intent=intent,
            report_scope=report_scope,
        )
        if heuristic_task:
            return {
                "status": "heuristic_fallback",
                "fallback_to_general_search": False,
                "planned_metric_families": [str(heuristic_task.get("metric_family") or "").strip()],
                "tasks": [heuristic_task],
                "planner_notes": planner_notes + ["heuristic_numeric_task", "planner_fallback:heuristic_numeric_task"],
            }
        return {
            "status": "fallback_general_search",
            "fallback_to_general_search": True,
            "planned_metric_families": [],
            "tasks": [],
            "planner_notes": planner_notes + ["ontology_match_missing", "planner_fallback:general_search"],
        }

    for index, metric_key in enumerate(metric_keys, start=1):
        metric = ontology.metric_family(metric_key) or {}
        if not metric:
            continue
        display_name = str(metric.get("display_name") or metric_key).strip()
        if matches and not query_mentions_metric(query, metric) and metric_key != target_metric_family:
            # Avoid over-expanding to weak secondary matches unless explicitly targeted.
            planner_notes.append(f"skip_weak_match:{metric_key}")
            continue
        constraints = _build_task_constraints(query, report_scope, ontology, metric_key)
        direct_lookup_preferred = bool(metric.get("direct_lookup_preferred")) and operation_family in {"lookup", "single_value"}
        if direct_lookup_preferred:
            operand_specs = [
                {
                    "label": display_name,
                    "concept": "",
                    "aliases": list(ontology.aliases_for_metric(metric_key)),
                    "keywords": list(metric.get("retrieval_keywords") or []),
                    "role": "primary_value",
                    "required": True,
                    "period_hint": "",
                    "period_focus": str(constraints.get("period_focus") or ""),
                    "preferred_sections": list(metric.get("preferred_sections") or []),
                    "preferred_statement_types": list(ontology.statement_type_hints_for_metric(metric_key)),
                    "binding_policy": {},
                    "unit_family": str(metric.get("result_unit") or ""),
                    "surface_contract": {},
                }
            ]
        else:
            operand_specs = ontology.build_operand_spec(metric_key)
        retrieval_queries = _build_retrieval_query_bundle(query, topic, metric_key, ontology)
        task_query = _build_metric_task_query(
            original_query=query,
            metric_label=display_name,
            constraints=constraints,
            operand_specs=operand_specs,
            report_scope=report_scope,
        )
        tasks.append(
            {
                "task_id": f"task_{index}",
                "metric_family": metric_key,
                "metric_label": display_name,
                "query": task_query,
                "operation_family": "lookup" if direct_lookup_preferred else str(metric.get("formula_family") or "").strip(),
                "required_operands": [
                    {
                        "label": str(spec.get("label") or ""),
                        "concept": str(spec.get("concept") or ""),
                        "aliases": list(spec.get("aliases") or []),
                        "keywords": list(spec.get("keywords") or []),
                        "role": str(spec.get("role") or ""),
                        "required": bool(spec.get("required", True)),
                        "period_hint": str(spec.get("period_hint") or ""),
                        "period_focus": str(spec.get("period_focus") or ""),
                        "preferred_sections": list(spec.get("preferred_sections") or []),
                        "preferred_statement_types": list(spec.get("preferred_statement_types") or []),
                        "binding_policy": dict(spec.get("binding_policy") or {}),
                        "unit_family": str(spec.get("unit_family") or ""),
                        "surface_contract": dict(spec.get("surface_contract") or {}),
                    }
                    for spec in operand_specs
                    if str(spec.get("label") or "").strip()
                ],
                "preferred_statement_types": list(ontology.statement_type_hints_for_metric(metric_key)),
                "preferred_sections": list(metric.get("preferred_sections") or []),
                "retrieval_queries": retrieval_queries,
                "constraints": constraints,
            }
        )

    if not tasks:
        return {
            "status": "fallback_general_search",
            "fallback_to_general_search": True,
            "planned_metric_families": [],
            "tasks": [],
            "planner_notes": planner_notes or ["no_viable_tasks"],
        }

    return {
        "status": "ok",
        "fallback_to_general_search": False,
        "planned_metric_families": [
            str(task.get("metric_family") or "").strip()
            for task in tasks
            if str(task.get("metric_family") or "").strip()
        ],
        "tasks": tasks,
        "planner_notes": planner_notes,
    }


# ---------------------------------------------------------------------------
# Reconciliation and operand matching helpers
# ---------------------------------------------------------------------------

def _build_reconciliation_candidate(
    *,
    candidate_id: str,
    anchor: str,
    text: str,
    metadata: Dict[str, Any],
    candidate_kind: str = "chunk",
    row_label: str = "",
    row_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Normalize a raw evidence/doc fragment into reconciliation candidate form."""
    candidate_metadata = dict(metadata or {})
    if row_label:
        candidate_metadata["row_label"] = row_label
    if row_index is not None:
        candidate_metadata["row_index"] = row_index
    return {
        "candidate_id": candidate_id,
        "source_anchor": anchor,
        "text": _normalise_spaces(text),
        "metadata": candidate_metadata,
        "candidate_kind": candidate_kind,
    }


def _query_years_from_state(state: Dict[str, Any]) -> List[int]:
    years: List[int] = []
    for value in list(state.get("years") or []):
        try:
            year = int(value)
        except (TypeError, ValueError):
            continue
        if year not in years:
            years.append(year)
    report_scope = dict(state.get("report_scope") or {})
    scope_year_raw = report_scope.get("year")
    try:
        if scope_year_raw not in (None, ""):
            scope_year = int(scope_year_raw)
            if scope_year not in years:
                years.insert(0, scope_year)
    except (TypeError, ValueError):
        pass
    return years


def _build_table_value_reconciliation_candidates(
    *,
    candidate_id_prefix: str,
    anchor: str,
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build value-cell-first candidates from parser-normalized table values."""
    value_records_json = str(metadata.get("table_value_records_json") or "").strip()
    if not value_records_json:
        return []
    try:
        value_records = json.loads(value_records_json)
    except json.JSONDecodeError:
        return []

    header_context = str(metadata.get("table_header_context") or "").strip()
    summary_text = str(metadata.get("table_summary_text") or "").strip()
    local_heading = str(metadata.get("local_heading") or "").strip()
    section_path = str(metadata.get("section_path") or metadata.get("section") or "").strip()
    row_groups: Dict[tuple[Any, str], List[Dict[str, Any]]] = {}
    for record in value_records:
        row_key = (
            record.get("row_index"),
            _normalise_spaces(str(record.get("row_label") or record.get("semantic_label") or "")),
        )
        row_groups.setdefault(row_key, []).append(dict(record))
    for grouped_records in row_groups.values():
        grouped_records.sort(key=lambda current: int(current.get("column_index") or 0))

    candidates: List[Dict[str, Any]] = []
    for idx, record in enumerate(value_records):
        semantic_label = _normalise_spaces(str(record.get("semantic_label") or ""))
        value_text = _normalise_spaces(str(record.get("value_text") or ""))
        if not semantic_label or not value_text or not re.search(r"\d", value_text):
            continue
        period_text = _normalise_spaces(str(record.get("period_text") or ""))
        semantic_aliases = [
            _normalise_spaces(str(item))
            for item in (record.get("semantic_aliases") or [])
            if _normalise_spaces(str(item))
        ]
        row_headers = [
            _normalise_spaces(str(item))
            for item in (record.get("row_headers") or [])
            if _normalise_spaces(str(item))
        ]
        column_headers = [
            _normalise_spaces(str(item))
            for item in (record.get("column_headers") or [])
            if _normalise_spaces(str(item))
        ]
        row_key = (
            record.get("row_index"),
            _normalise_spaces(str(record.get("row_label") or record.get("semantic_label") or "")),
        )
        sibling_records = row_groups.get(row_key) or [dict(record)]
        structured_cell_headers = [period_text] if period_text else list(record.get("period_labels") or []) or column_headers
        sibling_cells: List[Dict[str, Any]] = []
        for sibling in sibling_records:
            sibling_period_text = _normalise_spaces(str(sibling.get("period_text") or ""))
            sibling_column_headers = [
                _normalise_spaces(str(item))
                for item in (sibling.get("column_headers") or [])
                if _normalise_spaces(str(item))
            ]
            sibling_headers = (
                [sibling_period_text]
                if sibling_period_text
                else list(sibling.get("period_labels") or []) or sibling_column_headers
            )
            sibling_cells.append(
                {
                    "column_headers": sibling_headers,
                    "value_text": _normalise_spaces(str(sibling.get("value_text") or "")),
                    "unit_hint": str(sibling.get("unit_hint") or metadata.get("unit_hint") or "").strip(),
                    "value_role": _normalise_spaces(str(sibling.get("value_role") or "")),
                    "aggregation_stage": _normalise_spaces(str(sibling.get("aggregation_stage") or "")),
                    "aggregate_role": _normalise_spaces(str(sibling.get("aggregate_role") or "")),
                    "aggregate_label": _normalise_spaces(str(sibling.get("aggregate_label") or "")),
                }
            )
        composite_text = " ".join(
            part
            for part in (
                semantic_label,
                " ".join(semantic_aliases),
                " ".join(row_headers),
                " ".join(column_headers),
                period_text,
                value_text,
                header_context,
                summary_text,
                local_heading,
                section_path,
                anchor,
            )
            if part
        )
        candidate = _build_reconciliation_candidate(
            candidate_id=f"{candidate_id_prefix}::value:{idx}",
            anchor=anchor,
            text=composite_text,
            metadata=metadata,
            candidate_kind="structured_value",
            row_label=semantic_label,
            row_index=record.get("row_index"),
        )
        candidate["metadata"]["row_headers"] = row_headers
        candidate["metadata"]["column_headers_chain"] = column_headers
        candidate["metadata"]["semantic_label"] = semantic_label
        candidate["metadata"]["semantic_aliases"] = semantic_aliases
        candidate["metadata"]["label_source"] = str(record.get("label_source") or "")
        candidate["metadata"]["value_role"] = _normalise_spaces(str(record.get("value_role") or "detail"))
        candidate["metadata"]["aggregation_stage"] = _normalise_spaces(str(record.get("aggregation_stage") or "none"))
        candidate["metadata"]["aggregate_label"] = _normalise_spaces(str(record.get("aggregate_label") or ""))
        candidate["metadata"]["aggregate_role"] = _normalise_spaces(str(record.get("aggregate_role") or "none"))
        candidate["metadata"]["period_text"] = period_text
        candidate["metadata"]["structured_cells"] = sibling_cells or [
            {
                "column_headers": structured_cell_headers,
                "value_text": value_text,
                "unit_hint": str(record.get("unit_hint") or metadata.get("unit_hint") or "").strip(),
            }
        ]
        candidate["metadata"]["row_text"] = format_structured_candidate_row_text(
            semantic_label,
            row_headers,
            list(candidate["metadata"]["structured_cells"] or []),
        )
        candidates.append(candidate)
    return candidates


def _build_table_column_reconciliation_candidates(
    *,
    candidate_id_prefix: str,
    anchor: str,
    metadata: Dict[str, Any],
    row_records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Transpose row records into column-oriented aggregate candidates.

    This is the complement to row-based reconciliation. Some wide DART tables
    store the metric identity in the merged column header chain while each row
    carries period or range context. In that case we synthesize a candidate per
    meaningful column header and attach the row labels as the per-cell period
    headers so the normal direct structured extraction path can still work.
    """
    grouped: Dict[tuple[str, ...], Dict[str, Any]] = {}
    for record in row_records:
        row_label = _normalise_spaces(str(record.get("row_label") or ""))
        row_headers = [row_label] + [
            _normalise_spaces(str(item))
            for item in (record.get("row_headers") or [])
            if _normalise_spaces(str(item)) and _normalise_spaces(str(item)) != row_label
        ]
        for cell in (record.get("cells") or []):
            value_text = _normalise_spaces(str(cell.get("value_text") or ""))
            if not value_text or not re.search(r"\d", value_text):
                continue
            original_headers = [
                _normalise_spaces(str(item))
                for item in (cell.get("column_headers") or [])
                if _normalise_spaces(str(item))
            ]
            label = column_candidate_label(original_headers)
            if not label:
                continue
            key = tuple(original_headers) or (label,)
            bucket = grouped.setdefault(
                key,
                {
                    "label": label,
                    "column_headers_chain": original_headers,
                    "cells": [],
                },
            )
            transformed_headers = [item for item in row_headers if item]
            if not transformed_headers:
                transformed_headers = [label]
            bucket["cells"].append(
                {
                    "column_headers": transformed_headers,
                    "value_text": value_text,
                    "unit_hint": str(cell.get("unit_hint") or metadata.get("unit_hint") or "").strip(),
                }
            )

    header_context = str(metadata.get("table_header_context") or "").strip()
    summary_text = str(metadata.get("table_summary_text") or "").strip()
    local_heading = str(metadata.get("local_heading") or "").strip()
    section_path = str(metadata.get("section_path") or metadata.get("section") or "").strip()
    candidates: List[Dict[str, Any]] = []
    for idx, bucket in enumerate(grouped.values()):
        cells = [dict(cell) for cell in bucket.get("cells") or [] if dict(cell)]
        if not cells:
            continue
        label = str(bucket.get("label") or "").strip()
        if not label:
            continue
        cell_text = " ".join(
            _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        " / ".join(str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()),
                        str(cell.get("value_text") or "").strip(),
                        str(cell.get("unit_hint") or "").strip(),
                    )
                    if part
                )
            )
            for cell in cells
        )
        full_headers = [str(item).strip() for item in (bucket.get("column_headers_chain") or []) if str(item).strip()]
        composite_text = " ".join(
            part
            for part in (
                label,
                " ".join(full_headers),
                cell_text,
                header_context,
                summary_text,
                local_heading,
                section_path,
                anchor,
            )
            if part
        )
        candidate = _build_reconciliation_candidate(
            candidate_id=f"{candidate_id_prefix}::colrec:{idx}",
            anchor=anchor,
            text=composite_text,
            metadata=metadata,
            candidate_kind="structured_column_value",
            row_label=label,
        )
        candidate["metadata"]["row_headers"] = full_headers
        candidate["metadata"]["column_headers_chain"] = full_headers
        candidate["metadata"]["structured_cells"] = cells
        candidates.append(candidate)
    return candidates


def _build_table_row_reconciliation_candidates(
    *,
    candidate_id_prefix: str,
    anchor: str,
    table_text: str,
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Explode table metadata into row-level reconciliation candidates."""
    header_context = str(metadata.get("table_header_context") or "").strip()
    summary_text = str(metadata.get("table_summary_text") or "").strip()
    local_heading = str(metadata.get("local_heading") or "").strip()
    section_path = str(metadata.get("section_path") or metadata.get("section") or "").strip()
    candidates: List[Dict[str, Any]] = []
    seen_row_texts: set[str] = set()

    value_candidates = _build_table_value_reconciliation_candidates(
        candidate_id_prefix=candidate_id_prefix,
        anchor=anchor,
        metadata=metadata,
    )
    if value_candidates:
        candidates.extend(value_candidates)

    row_records_json = str(metadata.get("table_row_records_json") or "").strip()
    if not row_records_json:
        table_object_json = str(metadata.get("table_object_json") or "").strip()
        if table_object_json:
            try:
                table_object = json.loads(table_object_json)
            except json.JSONDecodeError:
                table_object = {}
            table_rows = table_object.get("rows") if isinstance(table_object, dict) else None
            if isinstance(table_rows, list):
                row_records_json = json.dumps(table_rows, ensure_ascii=False)

    if row_records_json:
        try:
            row_records = json.loads(row_records_json)
        except json.JSONDecodeError:
            row_records = []
        for idx, record in enumerate(row_records):
            row_headers = [str(item).strip() for item in (record.get("row_headers") or []) if str(item).strip()]
            row_label = str(record.get("row_label") or "").strip() or (row_headers[0] if row_headers else "")
            cells = [dict(cell) for cell in (record.get("cells") or []) if dict(cell)]
            if not row_label or not cells:
                continue
            cell_text = " ".join(
                _normalise_spaces(
                    " ".join(
                        part
                        for part in (
                            " / ".join(str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()),
                            str(cell.get("value_text") or "").strip(),
                            str(cell.get("unit_hint") or "").strip(),
                        )
                        if part
                    )
                )
                for cell in cells
            )
            composite_text = " ".join(
                part
                for part in (
                    row_label,
                    " ".join(row_headers),
                    cell_text,
                    header_context,
                    summary_text,
                    local_heading,
                    section_path,
                    anchor,
                )
                if part
            )
            candidate = _build_reconciliation_candidate(
                candidate_id=f"{candidate_id_prefix}::rowrec:{idx}",
                anchor=anchor,
                text=composite_text,
                metadata=metadata,
                candidate_kind="structured_row",
                row_label=row_label,
                row_index=idx,
            )
            candidate["metadata"]["row_headers"] = row_headers
            candidate["metadata"]["semantic_label"] = row_label
            candidate["metadata"]["semantic_aliases"] = [
                item for item in row_headers if _normalise_spaces(item) and _normalise_spaces(item) != _normalise_spaces(row_label)
            ]
            candidate["metadata"]["structured_cells"] = cells
            candidate["metadata"]["row_text"] = format_structured_candidate_row_text(row_label, row_headers, cells)
            row_text = _normalise_spaces(str(candidate["metadata"].get("row_text") or ""))
            if row_text:
                seen_row_texts.add(row_text)
            candidates.append(candidate)
        column_candidates = _build_table_column_reconciliation_candidates(
            candidate_id_prefix=candidate_id_prefix,
            anchor=anchor,
            metadata=metadata,
            row_records=row_records if isinstance(row_records, list) else [],
        )
        for candidate in column_candidates:
            row_text = _normalise_spaces(str((candidate.get("metadata") or {}).get("row_text") or ""))
            if row_text:
                seen_row_texts.add(row_text)
            candidates.append(candidate)

    rows = [_normalise_spaces(row) for row in str(table_text or "").splitlines() if _normalise_spaces(row)]
    if not rows:
        return candidates

    for idx, row_text in enumerate(rows):
        if "|" not in row_text:
            continue
        if row_text in seen_row_texts:
            continue
        row_label = extract_table_row_label(row_text)
        inferred_stage = aggregate_like_row_stage(row_label)
        inferred_role = aggregate_like_row_role(row_label)
        composite_text = " ".join(
            part
            for part in (
                row_label,
                row_text,
                header_context,
                summary_text,
                local_heading,
                section_path,
                anchor,
            )
            if part
        )
        candidates.append(
            _build_reconciliation_candidate(
                candidate_id=f"{candidate_id_prefix}::row:{idx}",
                anchor=anchor,
                text=composite_text,
                metadata={
                    **metadata,
                    "row_text": row_text,
                    "row_context_text": str(table_text or ""),
                    "structured_cells": parse_unstructured_table_row_cells(row_text, metadata),
                    "aggregate_label": row_label if inferred_stage != "none" else str(metadata.get("aggregate_label") or "").strip(),
                    "aggregate_role": (
                        "subtotal"
                        if inferred_stage == "subtotal"
                        else "final_total"
                        if inferred_stage == "final"
                        else str(metadata.get("aggregate_role") or "").strip()
                    ),
                    "value_role": (
                        inferred_role
                        if not str(metadata.get("value_role") or "").strip()
                        else str(metadata.get("value_role") or "").strip()
                    ),
                    "aggregation_stage": (
                        inferred_stage
                        if not str(metadata.get("aggregation_stage") or "").strip()
                        else str(metadata.get("aggregation_stage") or "").strip()
                    ),
                },
                candidate_kind="table_row",
                row_label=row_label,
                row_index=idx,
            )
        )
    return candidates


@lru_cache(maxsize=64)
def _cached_report_text(report_path: str) -> str:
    try:
        return Path(report_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


@lru_cache(maxsize=128)
def _resolve_report_path_from_receipt(receipt_no: str, report_year: str = "") -> str:
    receipt_no = str(receipt_no or "").strip()
    report_year = str(report_year or "").strip()
    if not receipt_no:
        return ""
    pattern = f"*_{receipt_no}.html"
    try:
        candidates = sorted(_REPORT_ROOT.rglob(pattern))
    except OSError:
        return ""
    if report_year:
        for candidate in candidates:
            if candidate.name.startswith(f"{report_year}_"):
                return str(candidate)
    return str(candidates[0]) if candidates else ""


def _resolve_candidate_local_unit_hint(candidate: Dict[str, Any], raw_value: str) -> str:
    metadata = dict(candidate.get("metadata") or {})
    receipt_no = str(metadata.get("rcept_no") or "").strip()
    if not receipt_no:
        chunk_uid = str(metadata.get("chunk_uid") or "").strip()
        if ":" in chunk_uid:
            receipt_no = chunk_uid.split(":", 1)[0].strip()
    report_year = str(metadata.get("year") or "").strip()
    if not receipt_no or not str(raw_value or "").strip():
        return ""

    report_path = _resolve_report_path_from_receipt(receipt_no, report_year)
    if not report_path:
        return ""

    report_text = _cached_report_text(report_path)
    if not report_text:
        return ""

    row_label = str(metadata.get("row_label") or "").strip()
    search_value = str(raw_value or "").strip()
    candidate_positions = [match.start() for match in re.finditer(re.escape(search_value), report_text)]
    if row_label:
        narrowed_positions = [
            position
            for position in candidate_positions
            if row_label in report_text[max(0, position - 500) : position + 100]
        ]
        if narrowed_positions:
            candidate_positions = narrowed_positions
    if not candidate_positions:
        return ""

    position = candidate_positions[0]
    window = report_text[max(0, position - 2500) : position]
    unit_matches = list(_UNIT_HINT_HTML_PATTERN.finditer(window))
    if not unit_matches:
        return ""

    resolved = _normalise_spaces(unit_matches[-1].group(1)).replace(" ", "")
    if not resolved:
        return ""
    return resolved


def _build_reconciliation_retry_queries(
    *,
    active_subtask: Dict[str, Any],
    missing_operands: List[str],
    years: List[int],
) -> List[str]:
    def _strip_leading_period_prefix(text: str) -> str:
        return _normalise_spaces(re.sub(rf"^{KOREAN_PERIOD_PREFIX_RE_FRAGMENT}\s+", "", _normalise_spaces(text or "")))

    def _strip_prefix_overlap(surface: str, prefix_values: List[str]) -> str:
        normalized = _normalise_spaces(surface)
        for prefix in prefix_values:
            normalized_prefix = _normalise_spaces(prefix)
            if normalized_prefix and normalized.startswith(f"{normalized_prefix} "):
                normalized = normalized[len(normalized_prefix) :].strip()
        return normalized

    def _metric_context_for_surface(surface: str, metric: str) -> str:
        normalized_surface = _normalise_spaces(surface)
        normalized_metric = _normalise_spaces(metric)
        if not normalized_surface or not normalized_metric:
            return normalized_metric
        surface_base = _strip_leading_period_prefix(normalized_surface)
        metric_base = _strip_leading_period_prefix(normalized_metric)
        if surface_base and metric_base and (surface_base == metric_base or metric_base in surface_base):
            return ""
        return normalized_metric

    metric_label = str(active_subtask.get("metric_label") or "").strip()
    constraints = dict(active_subtask.get("constraints") or {})
    required_operands = list(active_subtask.get("required_operands") or [])
    operand_map = {str(item.get("label") or "").strip(): item for item in required_operands if str(item.get("label") or "").strip()}

    prefixes: List[str] = []
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    year_suffix_template = str(period_policy.get("year_suffix_template") or "{year}")
    if years:
        prefixes.append(year_suffix_template.format(year=years[0]))
    consolidation_scope = str(constraints.get("consolidation_scope") or "unknown").strip()
    scope_prefix_labels = dict(CONSOLIDATION_SCOPE_POLICY.get("query_prefix_labels") or {})
    if consolidation_scope == "consolidated":
        prefixes.append(str(scope_prefix_labels.get("consolidated") or ""))
    elif consolidation_scope == "separate":
        prefixes.append(str(scope_prefix_labels.get("separate") or ""))

    queries: List[str] = []
    for operand_label in missing_operands:
        spec = dict(operand_map.get(operand_label) or {})
        aliases = [str(item).strip() for item in (spec.get("aliases") or []) if str(item).strip()]
        query_surfaces: List[str] = [
            operand_label,
            *aliases,
            *[
                str(item).strip()
                for item in lookup_query_surface_preferences(spec)
                if str(item).strip()
            ],
        ]
        preferred_sections = [
            str(item).strip()
            for item in (
                *list(spec.get("preferred_sections") or []),
                *list(active_subtask.get("preferred_sections") or []),
            )
            if str(item).strip()
        ]
        if lookup_prefers_canonical_statement_rows(spec):
            canonical_types, canonical_sections = lookup_canonical_statement_preferences(spec)
            del canonical_types  # section-only use here
            preferred_sections = list(dict.fromkeys([*canonical_sections, *preferred_sections]))
        binding_policy = dict(spec.get("binding_policy") or {})
        preferred_value_roles = {
            _normalise_spaces(str(item))
            for item in (binding_policy.get("prefer_value_roles") or [])
            if str(item).strip()
        }
        if "aggregate" in preferred_value_roles:
            aggregate_expansions: List[str] = []
            for surface in list(query_surfaces):
                normalized_surface = strip_financial_label_annotations(surface)
                if not normalized_surface:
                    continue
                aggregate_expansions.extend(
                    [
                        f"{normalized_surface} 합계",
                        f"합계 {normalized_surface}",
                        f"{normalized_surface} 총계",
                    ]
                )
            query_surfaces.extend(aggregate_expansions)
        deduped_surfaces = list(dict.fromkeys(_normalise_spaces(surface) for surface in query_surfaces if _normalise_spaces(surface)))
        for surface in deduped_surfaces[:4]:
            normalized_surface = _strip_prefix_overlap(surface, prefixes)
            metric_context = _metric_context_for_surface(normalized_surface, metric_label)
            base_bits = prefixes + [normalized_surface]
            if metric_context:
                base_bits.append(metric_context)
            base_query = _normalise_spaces(" ".join(base_bits))
            if base_query:
                queries.append(base_query)
            for section in preferred_sections[:2]:
                queries.append(_normalise_spaces(f"{base_query} {section}"))
    return list(dict.fromkeys(item for item in queries if item))


def _deterministic_reconcile_task(
    *,
    active_subtask: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    years: List[int],
    reconciliation_retry_count: int,
    report_scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Match required operands to the best available candidates.

    Output from this function is not yet a final operand set. It is a ranked
    and explainable candidate selection that later calculation stages can
    convert into normalized operand rows.
    """
    if not active_subtask:
        return {
            "status": "ready",
            "task_id": "",
            "matched_operands": [],
            "missing_operands": [],
            "retry_queries": [],
            "notes": ["no_active_subtask"],
        }

    preferred_statement_types = [str(item).strip() for item in (active_subtask.get("preferred_statement_types") or []) if str(item).strip()]
    constraints = dict(active_subtask.get("constraints") or {})
    operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
    required_operands = [dict(item) for item in (active_subtask.get("required_operands") or []) if bool(item.get("required", True))]

    matched_operands: List[Dict[str, Any]] = []
    missing_operands: List[str] = []
    operand_top_candidates: Dict[str, List[Dict[str, Any]]] = {}

    for operand in required_operands:
        label = str(operand.get("label") or "").strip()
        matches = [candidate for candidate in candidates if candidate_matches_operand(candidate, operand)]
        if operand_segment_label(operand):
            segment_local_matches = [
                candidate
                for candidate in matches
                if candidate_has_segment_local_binding(candidate, operand)
            ]
            if segment_local_matches:
                matches = segment_local_matches
        ranked = sorted(
            matches,
            key=lambda candidate: score_operand_candidate(
                candidate,
                operand=operand,
                preferred_statement_types=preferred_statement_types,
                constraints=constraints,
                query_years=years,
                report_scope=report_scope,
            ),
            reverse=True,
        )
        operand_top_candidates[label] = ranked
        requires_direct_grounding = operation_family in {"lookup", "single_value"}
        if ranked:
            direct_candidates: List[Dict[str, Any]] = []
            if requires_direct_grounding:
                period_focus = operand_period_focus(
                    operand,
                    str((constraints or {}).get("period_focus") or "unknown").strip(),
                )
                direct_entries: List[Dict[str, Any]] = []
                for candidate in ranked:
                    selected_cell = candidate_selected_cell_for_operand(
                        candidate,
                        operand=operand,
                        query_years=years,
                        period_focus=period_focus,
                    )
                    if not candidate_satisfies_direct_acceptance_contract(
                        candidate,
                        operand=operand,
                        constraints=constraints,
                        query_years=years,
                        operation_family=operation_family,
                        selected_cell=selected_cell,
                        report_scope=report_scope,
                    ):
                        continue
                    direct_entries.append(
                        {
                            "candidate": candidate,
                            "logical_signature": candidate_direct_logical_signature(
                                candidate,
                                selected_cell=selected_cell,
                            ),
                            "family_signature": candidate_direct_family_signature(
                                candidate,
                                selected_cell=selected_cell,
                            ),
                            "selected_value_text": _normalise_spaces(
                                str((selected_cell or {}).get("value_text") or "")
                            ),
                            "score": score_operand_candidate(
                                candidate,
                                operand=operand,
                                preferred_statement_types=preferred_statement_types,
                                constraints=constraints,
                                query_years=years,
                                report_scope=report_scope,
                            ),
                            "canonical_winner": candidate_is_canonical_statement_winner(
                                candidate,
                                operand=operand,
                                query_years=years,
                            ),
                        }
                    )
                collapsed_entries: List[Dict[str, Any]] = []
                if direct_entries:
                    family_signatures = {
                        tuple(entry.get("family_signature") or ())
                        for entry in direct_entries
                        if tuple(entry.get("family_signature") or ())
                    }
                    distinct_values = {
                        str(entry.get("selected_value_text") or "").strip()
                        for entry in direct_entries
                        if str(entry.get("selected_value_text") or "").strip()
                    }
                    if len(family_signatures) == 1 and len(distinct_values) <= 1:
                        collapsed_entries = sorted(
                            direct_entries,
                            key=lambda entry: (
                                bool(entry.get("canonical_winner")),
                                float(entry.get("score") or 0.0),
                            ),
                            reverse=True,
                        )[:1]
                    else:
                        best_by_signature: Dict[tuple[str, str, str, str], Dict[str, Any]] = {}
                        for entry in direct_entries:
                            signature = tuple(entry.get("logical_signature") or ())
                            existing = best_by_signature.get(signature)
                            if existing is None or (
                                bool(entry.get("canonical_winner")),
                                float(entry.get("score") or 0.0),
                            ) > (
                                bool(existing.get("canonical_winner")),
                                float(existing.get("score") or 0.0),
                                ):
                                    best_by_signature[signature] = entry
                        collapsed_entries = list(best_by_signature.values())
                        sibling_surfaces = [
                            str(item).strip()
                            for item in (active_subtask.get("sibling_lookup_surfaces") or [])
                            if str(item).strip()
                        ]
                        if len(collapsed_entries) > 1 and sibling_surfaces:
                            sibling_ranked_entries = sorted(
                                collapsed_entries,
                                key=lambda entry: (
                                    candidate_sibling_surface_hit_count(
                                        dict(entry.get("candidate") or {}),
                                        sibling_surfaces,
                                    ),
                                    float(entry.get("score") or 0.0),
                                ),
                                reverse=True,
                            )
                            top_sibling_hits = candidate_sibling_surface_hit_count(
                                dict(sibling_ranked_entries[0].get("candidate") or {}),
                                sibling_surfaces,
                            )
                            if top_sibling_hits > 0:
                                collapsed_entries = [
                                    entry
                                    for entry in sibling_ranked_entries
                                    if candidate_sibling_surface_hit_count(
                                        dict(entry.get("candidate") or {}),
                                        sibling_surfaces,
                                    )
                                    == top_sibling_hits
                                ]
                        canonical_entries = [
                            entry for entry in collapsed_entries if bool(entry.get("canonical_winner"))
                        ]
                        if len(canonical_entries) == 1:
                            collapsed_entries = canonical_entries
                        elif len(collapsed_entries) > 1:
                            ranked_by_priority = sorted(
                                collapsed_entries,
                                key=lambda entry: (
                                    direct_candidate_semantic_priority(
                                        dict(entry.get("candidate") or {}),
                                        operand=operand,
                                        preferred_statement_types=preferred_statement_types,
                                        query_years=years,
                                    ),
                                    float(entry.get("score") or 0.0),
                                ),
                                reverse=True,
                            )
                            top_priority = direct_candidate_semantic_priority(
                                dict(ranked_by_priority[0].get("candidate") or {}),
                                operand=operand,
                                preferred_statement_types=preferred_statement_types,
                                query_years=years,
                            )
                            next_priority = direct_candidate_semantic_priority(
                                dict(ranked_by_priority[1].get("candidate") or {}),
                                operand=operand,
                                preferred_statement_types=preferred_statement_types,
                                query_years=years,
                            )
                            if top_priority > next_priority:
                                collapsed_entries = [ranked_by_priority[0]]
                            else:
                                ranked_collapsed = sorted(
                                    collapsed_entries,
                                    key=lambda entry: (
                                        bool(entry.get("canonical_winner")),
                                        float(entry.get("score") or 0.0),
                                    ),
                                    reverse=True,
                                )
                                top_score = float(ranked_collapsed[0].get("score") or 0.0)
                                next_score = float(ranked_collapsed[1].get("score") or 0.0)
                                if top_score >= next_score + 0.75:
                                    collapsed_entries = [ranked_collapsed[0]]
                                else:
                                    collapsed_entries = ranked_collapsed
                direct_candidates = [dict(entry.get("candidate") or {}) for entry in collapsed_entries]
            else:
                direct_candidates = [
                    candidate
                    for candidate in ranked
                    if candidate_is_direct_grounding_candidate(
                        candidate,
                        operand=operand,
                        constraints=constraints,
                        query_years=years,
                        operation_family=operation_family,
                        report_scope=report_scope,
                    )
                ]
            direct_candidate = direct_candidates[0] if len(direct_candidates) == 1 else None
            if direct_candidate:
                direct_candidate_id = str(direct_candidate.get("candidate_id") or "").strip()
                top = [direct_candidate]
                top.extend(
                    candidate
                    for candidate in ranked
                    if str(candidate.get("candidate_id") or "").strip() != direct_candidate_id
                )
                top = top[:3]
                matched_operands.append(
                    {
                        "label": label,
                        "role": str(operand.get("role") or "").strip(),
                        "concept": str(operand.get("concept") or "").strip(),
                        "matched": True,
                        "candidate_ids": [str(item.get("candidate_id") or "") for item in top if str(item.get("candidate_id") or "").strip()],
                            "reason": "matched_direct_candidate" if requires_direct_grounding else "matched_candidates",
                        }
                    )
            else:
                top = direct_candidates[:3] if direct_candidates else ranked[:3]
                if requires_direct_grounding:
                    missing_operands.append(label)
                    matched_operands.append(
                        {
                            "label": label,
                            "role": str(operand.get("role") or "").strip(),
                            "concept": str(operand.get("concept") or "").strip(),
                            "matched": False,
                            "candidate_ids": [str(item.get("candidate_id") or "") for item in top if str(item.get("candidate_id") or "").strip()],
                            "reason": "ambiguous_direct_grounding_candidates" if direct_candidates else "no_direct_grounding_candidate",
                        }
                    )
                else:
                    matched_operands.append(
                        {
                            "label": label,
                            "role": str(operand.get("role") or "").strip(),
                            "concept": str(operand.get("concept") or "").strip(),
                            "matched": True,
                            "candidate_ids": [str(item.get("candidate_id") or "") for item in top if str(item.get("candidate_id") or "").strip()],
                            "reason": "matched_candidates",
                        }
                    )
        else:
            missing_operands.append(label)
            matched_operands.append(
                {
                    "label": label,
                    "role": str(operand.get("role") or "").strip(),
                    "concept": str(operand.get("concept") or "").strip(),
                    "matched": False,
                    "candidate_ids": [],
                    "reason": "no_matching_candidate",
                }
            )

    notes: List[str] = []
    common_table_ids: Optional[set[str]] = None
    for label, ranked in operand_top_candidates.items():
        table_ids = {
            str(item.get("metadata", {}).get("table_source_id") or "").strip()
            for item in ranked[:5]
            if str(item.get("metadata", {}).get("table_source_id") or "").strip()
        }
        if not table_ids:
            continue
        common_table_ids = table_ids if common_table_ids is None else (common_table_ids & table_ids)
    if common_table_ids:
        notes.append("same_table_candidate_available")

    if not missing_operands:
        return {
            "status": "ready",
            "task_id": str(active_subtask.get("task_id") or ""),
            "matched_operands": matched_operands,
            "missing_operands": [],
            "retry_queries": [],
            "notes": notes,
        }

    if reconciliation_retry_count < 1:
        retry_queries = _build_reconciliation_retry_queries(
            active_subtask=active_subtask,
            missing_operands=missing_operands,
            years=years,
        )
        return {
            "status": "retry_retrieval",
            "task_id": str(active_subtask.get("task_id") or ""),
            "matched_operands": matched_operands,
            "missing_operands": missing_operands,
            "retry_queries": retry_queries,
            "notes": notes + ["retry_once_for_missing_operands"],
        }

    return {
        "status": "insufficient_operands",
        "task_id": str(active_subtask.get("task_id") or ""),
        "matched_operands": matched_operands,
        "missing_operands": missing_operands,
        "retry_queries": [],
        "notes": notes + ["retry_exhausted"],
    }
