"""Semantic calculation-program nodes for the financial graph."""

from __future__ import annotations

import json
import hashlib
import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.agent.financial_candidate_matching import (
    build_physical_evidence_bundle_constraints,
    build_candidate_matches,
    narrative_candidate_source_path,
    project_candidate_match,
    project_candidate_fact,
    rank_candidate_matches,
    select_source_defined_physical_row_group,
    summarize_candidate_match_ranking,
)
from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program,
    project_semantic_program_operand,
    semantic_candidate_applicability,
    source_candidate_applicability,
    validate_semantic_calculation_program,
)
from src.agent.financial_compiler_wire import CompilerReferencesV1, compiler_response_model, lower_compiler_response
from src.agent.financial_program_projection import narrative_candidate_ids, narrative_description_only_ids
from src.agent.financial_graph_state import (
    FinancialAgentState, CandidateInput, CompilationInput, CompilationPhase, CompilerAttemptDebugV1,
    NumericExecutionInput, NumericResultPhase,
)
from src.agent.financial_langchain_loaders import chat_prompt_template_from_template
from src.agent.financial_narrative_claims import project_narrative_retry_drafts
from src.agent.financial_compiler_debug import project_compiler_attempt
from src.utils.request_diagnostics import diagnostic_location, diagnostics_enabled, record_diagnostic
from src.agent.financial_request_units import build_request_units, project_request_units, request_unit_errors
from src.agent.financial_source_interpretation import interpretation_axis_sources
from src.agent.financial_output_relationships import output_relationships
from src.agent.financial_compiler_presentation import (
    project_output_responsibility_context,
    project_prompt_cohort, project_prompt_retry_feedback, project_reading_payload,
    project_wire_reading_payload,
)
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    build_semantic_source_candidates,
    semantic_candidate_id_fingerprint,
    semantic_candidate_catalog_fingerprint,
    semantic_candidate_stage_diagnostics,
)
from src.agent.financial_runtime_normalization import _normalise_spaces, resolve_unit_spec
from src.agent.financial_runtime_contracts import (
    CandidateVisibilityV1,
    CompilationEnvelopeV2,
    EvidenceBundleConstraintV1,
)
from src.agent.financial_source_bundles import (
    build_semantic_source_bundles,
    semantic_source_bundle_fingerprint,
    source_bundle_id_by_candidate_id,
)
from src.agent.financial_runtime_trace import resolve_runtime_calculation_trace, runtime_trace_state_update
from src.agent.financial_source_scope import (
    candidate_section_path, has_source_section_constraint,
    source_section_applicability, source_section_requirement_errors,
)
from src.config.retrieval_policy import CALCULATION_PROMPT_POLICY
from src.utils.provider_errors import ProviderAdmissionError


logger = logging.getLogger(__name__)

MAX_SEMANTIC_COMPILATION_ISLANDS = 8


def _compiler_json(value: Any) -> str:
    """Compact framing only: source strings and every provenance field survive."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _semantic_candidate_capacity(
    catalog: Sequence[Mapping[str, Any]], selectable_ids: Sequence[str],
) -> Dict[str, Any]:
    """Charge each selectable source fact once across the entire query."""
    selected = set(selectable_ids)
    kind_by_id = {str(row.get("candidate_id") or ""): row.get("kind") for row in catalog}
    limits = dict(CALCULATION_PROMPT_POLICY.get("semantic_program_prompt_limits") or {})
    numeric = sum(kind_by_id.get(item) == "numeric" for item in selected)
    narrative = sum(kind_by_id.get(item) == "narrative" for item in selected)
    numeric_limit = int(limits.get("numeric_candidates") or 96)
    narrative_limit = int(limits.get("narrative_candidates") or 32)
    return {
        "status": "capacity_exceeded" if numeric > numeric_limit or narrative > narrative_limit else "ok",
        "numeric": numeric, "narrative": narrative,
        "numeric_limit": numeric_limit, "narrative_limit": narrative_limit,
    }

def build_semantic_compilation_islands(
    obligations: Sequence[Mapping[str, Any]],
    *,
    evidence_bundle_constraints: Sequence[Mapping[str, Any]] = (),
    query: str = "",
) -> Dict[str, Any]:
    """Build deterministic dependency/coupling/bundle components."""

    rows = [
        dict(item)
        for item in obligations
        if isinstance(item, Mapping)
        and str(item.get("obligation_id") or "").strip()
    ]
    order = {
        str(item.get("obligation_id") or "").strip(): index
        for index, item in enumerate(rows)
    }
    obligation_by_id = {
        str(item.get("obligation_id") or "").strip(): item
        for item in rows
    }
    adjacency = {obligation_id: set() for obligation_id in order}
    errors_by_id: Dict[str, List[Dict[str, str]]] = {
        obligation_id: [] for obligation_id in order
    }
    for section_error in source_section_requirement_errors(rows, query):
        errors_by_id[section_error["obligation_id"]].append(section_error)
    dependency_edges: List[tuple[str, str]] = []
    for obligation_id, obligation in obligation_by_id.items():
        if obligation.get("kind") == "direct_value" and obligation.get("evidence_requirements"):
            errors_by_id[obligation_id].append({
                "code": "evidence_requirement_on_unsupported_obligation", "obligation_id": obligation_id,
                "owner_id": obligation_id, "candidate_id": "",
                "location": "obligation.evidence_requirements", "repair_action": "repair_requirements",
                "detail": "",
            })
        declared_unit = _normalise_spaces(str(obligation.get("display_unit") or ""))
        if declared_unit and declared_unit.upper() != "UNKNOWN" and resolve_unit_spec(declared_unit) is None:
            errors_by_id[obligation_id].append({
                "code": "invalid_obligation_unit", "obligation_id": obligation_id,
                "owner_id": obligation_id, "candidate_id": "",
                "location": "obligation.display_unit", "repair_action": "repair_requirements",
                "detail": declared_unit,
            })
        for raw_dependency in obligation.get("depends_on") or []:
            dependency_id = str(raw_dependency or "").strip()
            if not dependency_id:
                continue
            if dependency_id == obligation_id:
                errors_by_id[obligation_id].append(
                    {
                        "code": "self_dependency",
                        "obligation_id": obligation_id,
                        "detail": dependency_id,
                    }
                )
                continue
            if dependency_id not in obligation_by_id:
                errors_by_id[obligation_id].append(
                    {
                        "code": "unknown_dependency",
                        "obligation_id": obligation_id,
                        "detail": dependency_id,
                    }
                )
                continue
            dependency_edges.append((obligation_id, dependency_id))
            adjacency[obligation_id].add(dependency_id)
            adjacency[dependency_id].add(obligation_id)

    relationships, relationship_errors = output_relationships(rows, query)
    for issue in relationship_errors:
        errors_by_id[issue["obligation_id"]].append(issue)
    relationship_groups = {key: row["output_ids"] for key, row in relationships.items()}
    for obligation_ids in relationship_groups.values():
        for left, right in zip(obligation_ids, obligation_ids[1:]):
            adjacency[left].add(right)
            adjacency[right].add(left)

    bundle_rows = [
        dict(item)
        for item in evidence_bundle_constraints
        if isinstance(item, Mapping)
        and str(item.get("constraint_id") or "").strip()
    ]
    evidence_bundle_edges: List[tuple[str, str]] = []
    for bundle in bundle_rows:
        owner_ids = [
            str(owner_id).strip()
            for owner_id in (bundle.get("owner_ids") or [])
            if str(owner_id).strip() in obligation_by_id
        ]
        for left, right in zip(owner_ids, owner_ids[1:]):
            adjacency[left].add(right)
            adjacency[right].add(left)
            evidence_bundle_edges.append((left, right))

    components: List[List[str]] = []
    seen: set[str] = set()
    for obligation_id in order:
        if obligation_id in seen:
            continue
        pending = [obligation_id]
        component: set[str] = set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(adjacency[current] - component)
        seen.update(component)
        components.append(sorted(component, key=order.__getitem__))

    islands: List[Dict[str, Any]] = []
    for island_index, component in enumerate(components, start=1):
        component_set = set(component)
        local_edges = [
            edge
            for edge in dependency_edges
            if edge[0] in component_set and edge[1] in component_set
        ]
        indegree = {obligation_id: 0 for obligation_id in component}
        dependents = {obligation_id: [] for obligation_id in component}
        for dependent_id, dependency_id in local_edges:
            indegree[dependent_id] += 1
            dependents[dependency_id].append(dependent_id)
        ready = [
            obligation_id
            for obligation_id in component
            if indegree[obligation_id] == 0
        ]
        visited: List[str] = []
        while ready:
            current = ready.pop(0)
            visited.append(current)
            for dependent_id in sorted(
                dependents[current],
                key=order.__getitem__,
            ):
                indegree[dependent_id] -= 1
                if indegree[dependent_id] == 0:
                    ready.append(dependent_id)
        island_errors = [
            dict(error)
            for obligation_id in component
            for error in errors_by_id[obligation_id]
        ]
        if len(visited) != len(component):
            island_errors.append(
                {
                    "code": "dependency_cycle",
                    "obligation_id": component[0],
                    "detail": ",".join(component),
                }
            )
        island_relationship_ids = [
            relationship_id
            for relationship_id, obligation_ids in relationship_groups.items()
            if len(set(obligation_ids) & component_set) >= 2
        ]
        island_bundle_ids = [
            str(bundle.get("constraint_id") or "")
            for bundle in bundle_rows
            if len(set(bundle.get("owner_ids") or []) & component_set) >= 2
        ]
        islands.append(
            {
                "island_id": f"island_{island_index:03d}",
                "obligation_ids": component,
                "dependency_edges": [list(edge) for edge in local_edges],
                "output_relationships": {key: relationships[key] for key in island_relationship_ids},
                "evidence_bundle_constraint_ids": island_bundle_ids,
                "evidence_bundle_edges": [
                    list(edge)
                    for edge in evidence_bundle_edges
                    if edge[0] in component_set and edge[1] in component_set
                ],
                "errors": island_errors,
            }
        )
    return {
        "schema": "semantic_compilation_islands_v2",
        "status": (
            "invalid"
            if any(island["errors"] for island in islands)
            else "ok"
        ),
        "islands": islands,
    }


def _semantic_candidate_visibility(
    catalog: Sequence[Mapping[str, Any]],
    *,
    visible_candidate_ids: Sequence[Any],
    candidate_ids_by_owner: Mapping[str, Sequence[Any]],
    evidence_bundle_constraints: Sequence[Mapping[str, Any]] = (),
) -> CandidateVisibilityV1:
    """Freeze the complete candidate authority used for one validation."""

    requested_ids = {
        str(candidate_id)
        for candidate_id in visible_candidate_ids
        if str(candidate_id)
    }
    requested_ids.update(
        str(candidate_id)
        for candidate_ids in candidate_ids_by_owner.values()
        for candidate_id in candidate_ids
        if str(candidate_id)
    )
    catalog_order = [
        str(item.get("candidate_id") or "")
        for item in catalog
        if str(item.get("candidate_id") or "")
    ]
    ordered_visible_ids = [
        candidate_id
        for candidate_id in catalog_order
        if candidate_id in requested_ids
    ]
    ordered_visible_ids.extend(
        sorted(requested_ids.difference(ordered_visible_ids))
    )
    return CandidateVisibilityV1.create(
        catalog_fingerprint=semantic_candidate_catalog_fingerprint(catalog),
        visible_candidate_ids=ordered_visible_ids,
        candidate_ids_by_owner=candidate_ids_by_owner,
        evidence_bundle_constraints=evidence_bundle_constraints,
    )


def _project_atomic_evidence_bundle_options(
    *,
    cohorts: Sequence[Mapping[str, Any]],
    visible_candidate_ids: Sequence[Any],
    constraints: Sequence[EvidenceBundleConstraintV1],
) -> Dict[str, Any]:
    """Project each ranked bundle constraint through its best complete row."""

    selected_ids_by_parent: Dict[str, List[str]] = {}
    active_constraints: List[EvidenceBundleConstraintV1] = []
    selections: List[Dict[str, Any]] = []
    positions_by_owner = {
        str(cohort.get("owner_id") or ""): {
            str(candidate_id): index
            for index, candidate_id in enumerate(
                cohort.get("candidate_ids") or []
            )
            if str(candidate_id)
        }
        for cohort in cohorts
        if str(cohort.get("owner_type") or "") == "obligation"
        and str(cohort.get("owner_id") or "")
    }
    for constraint in constraints:
        selected_option = constraint.options[0]
        selected_map = selected_option.candidate_ids_by_owner()
        for owner_id in constraint.owner_ids:
            allowed_ids = list(selected_map.get(owner_id) or [])
            if owner_id not in selected_ids_by_parent:
                selected_ids_by_parent[owner_id] = allowed_ids
                continue
            allowed_set = set(allowed_ids)
            selected_ids_by_parent[owner_id] = [
                candidate_id
                for candidate_id in selected_ids_by_parent[owner_id]
                if candidate_id in allowed_set
            ]
        active_constraint = EvidenceBundleConstraintV1.create(
            owner_ids=constraint.owner_ids,
            options=(selected_option,),
        )
        active_constraints.append(active_constraint)
        ranked_option_diagnostics: List[Dict[str, Any]] = []
        for option in constraint.options:
            option_positions = {
                owner_id: min(
                    (
                        positions_by_owner.get(owner_id, {}).get(
                            candidate_id,
                            10**6,
                        )
                        for candidate_id in candidate_ids
                    ),
                    default=10**6,
                )
                for owner_id, candidate_ids in (
                    option.candidate_ids_by_owner().items()
                )
            }
            ranked_option_diagnostics.append(
                {
                    "option_id": option.option_id,
                    "physical_table_id": option.physical_table_id,
                    "physical_row_id": option.physical_row_id,
                    "owner_candidate_positions": option_positions,
                    "position_sum": sum(option_positions.values()),
                    "worst_position": max(
                        option_positions.values(),
                        default=10**6,
                    ),
                }
            )
        selections.append(
            {
                "constraint_id": active_constraint.constraint_id,
                "source_constraint_id": constraint.constraint_id,
                "selected_option_id": selected_option.option_id,
                "selection_strategy": (
                    "owner_cohort_sum_then_worst_rank_v1"
                ),
                "complete_option_count": len(constraint.options),
                "selected_physical_table_id": selected_option.physical_table_id,
                "selected_physical_row_id": selected_option.physical_row_id,
                "ranked_options": [
                    option.to_projection() for option in constraint.options
                ],
                "ranked_option_diagnostics": ranked_option_diagnostics,
            }
        )

    projected_cohorts: List[Dict[str, Any]] = []
    for raw_cohort in cohorts:
        cohort = dict(raw_cohort)
        candidate_ids = list(
            dict.fromkeys(
                str(candidate_id)
                for candidate_id in (cohort.get("candidate_ids") or [])
                if str(candidate_id)
            )
        )
        parent_id = str(cohort.get("parent_obligation_id") or "")
        if (
            parent_id in selected_ids_by_parent
            and str(cohort.get("owner_type") or "") != "compatibility"
        ):
            allowed_set = set(selected_ids_by_parent[parent_id])
            candidate_ids = [
                candidate_id
                for candidate_id in candidate_ids
                if candidate_id in allowed_set
            ]
        cohort["candidate_ids"] = candidate_ids
        source_group_selection = dict(
            cohort.get("source_defined_group_selection") or {}
        )
        if source_group_selection:
            source_group_selection["required_candidate_ids"] = [
                candidate_id
                for candidate_id in (
                    source_group_selection.get("required_candidate_ids") or []
                )
                if candidate_id in candidate_ids
            ]
            cohort["source_defined_group_selection"] = source_group_selection
        cohort["candidate_id_fingerprint"] = (
            semantic_candidate_id_fingerprint(candidate_ids)
        )
        projected_cohorts.append(cohort)

    selectable_by_owner: Dict[str, List[str]] = {}
    parent_requirement_ids: Dict[str, List[str]] = {}
    for cohort in projected_cohorts:
        owner_id = str(cohort.get("owner_id") or "")
        parent_id = str(cohort.get("parent_obligation_id") or "")
        candidate_ids = list(cohort.get("candidate_ids") or [])
        selectable_by_owner.setdefault(owner_id, [])
        selectable_by_owner[owner_id].extend(
            candidate_id
            for candidate_id in candidate_ids
            if candidate_id not in selectable_by_owner[owner_id]
        )
        if str(cohort.get("owner_type") or "") == "requirement":
            parent_requirement_ids.setdefault(parent_id, []).extend(
                candidate_ids
            )

    for cohort in projected_cohorts:
        parent_id = str(cohort.get("parent_obligation_id") or "")
        parent_ids = selectable_by_owner.setdefault(parent_id, [])
        for candidate_id in [
            *list(cohort.get("candidate_ids") or []),
            *parent_requirement_ids.get(parent_id, []),
        ]:
            if candidate_id not in parent_ids:
                parent_ids.append(candidate_id)

    selectable_ids = {
        candidate_id
        for candidate_ids in selectable_by_owner.values()
        for candidate_id in candidate_ids
    }
    projected_visible_ids = [
        str(candidate_id)
        for candidate_id in visible_candidate_ids
        if str(candidate_id) in selectable_ids
    ]
    return {
        "cohorts": projected_cohorts,
        "candidate_ids_by_owner": selectable_by_owner,
        "visible_candidate_ids": projected_visible_ids,
        "evidence_bundle_constraints": [
            constraint.to_projection() for constraint in active_constraints
        ],
        "evidence_bundle_option_selections": selections,
    }


def _active_evidence_bundle_selection_diagnostics(
    *,
    constraints: Sequence[
        EvidenceBundleConstraintV1 | Mapping[str, Any]
    ],
    initial_selections: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Return selection diagnostics matching the final active constraints."""

    selection_by_constraint_id: Dict[str, Dict[str, Any]] = {}
    for row in initial_selections:
        constraint_id = str(row.get("constraint_id") or "")
        if constraint_id:
            selection_by_constraint_id[constraint_id] = dict(row)
    for attempt in attempts:
        for row in attempt.get("evidence_bundle_option_selections") or []:
            if not isinstance(row, Mapping):
                continue
            constraint_id = str(row.get("constraint_id") or "")
            if constraint_id:
                selection_by_constraint_id[constraint_id] = dict(row)

    active_constraint_ids = [
        (
            constraint.constraint_id
            if isinstance(constraint, EvidenceBundleConstraintV1)
            else str(constraint.get("constraint_id") or "")
        )
        for constraint in constraints
    ]
    return [
        selection_by_constraint_id[constraint_id]
        for constraint_id in active_constraint_ids
        if constraint_id in selection_by_constraint_id
    ]


def _semantic_program_prompt_cohort(
    raw_cohort: Mapping[str, Any],
) -> Dict[str, Any]:
    """Keep observability-only ranking fields out of compiler input."""

    return project_prompt_cohort(raw_cohort)


def _rank_applicable_owner_candidates(
    catalog: Sequence[Mapping[str, Any]],
    *,
    owner: Mapping[str, Any],
    candidate_kind: str,
    limit: int,
    parent_owner: Optional[Mapping[str, Any]] = None,
    excluded_candidate_ids: Sequence[str] = (),
) -> tuple[
    List[Dict[str, Any]],
    Dict[str, int],
    Dict[str, Dict[str, Any]],
    Dict[str, Any],
]:
    allowed_kinds = (
        {"numeric", "narrative"}
        if candidate_kind == "evidence"
        else {candidate_kind}
    )
    full_catalog = catalog
    source_section_counts: Dict[str, int] = {}
    if has_source_section_constraint(owner, parent_owner):
        eligible = []
        for candidate in catalog:
            section_state = source_section_applicability(candidate, owner, parent_owner)["state"]
            source_section_counts[section_state] = source_section_counts.get(section_state, 0) + 1
            if section_state == "match":
                eligible.append(candidate)
        catalog = eligible
    base_applicability_by_id: Dict[str, Dict[str, Any]] = {}
    for raw_candidate in catalog:
        candidate = dict(raw_candidate or {})
        candidate_id = str(candidate.get("candidate_id") or "").strip()
        if not candidate_id:
            continue
        base_applicability_by_id[candidate_id] = source_candidate_applicability(
            candidate,
            owner,
            parent_owner,
        )
    matches_by_id = build_candidate_matches(
        catalog,
        owner=owner,
        parent_owner=parent_owner,
        base_applicability_by_id=base_applicability_by_id,
    )
    excluded = {
        str(candidate_id).strip()
        for candidate_id in excluded_candidate_ids
        if str(candidate_id or "").strip()
    }
    candidate_by_id = {
        str(item.get("candidate_id") or ""): dict(item)
        for item in catalog
        if str(item.get("candidate_id") or "")
    }
    selected_bundle_ids: List[str] = []
    if candidate_kind == "numeric":
        bundles = build_semantic_source_bundles(full_catalog)
        bundle_id_by_candidate = source_bundle_id_by_candidate_id(bundles)
        order_by_bundle = {
            bundle.source_bundle_id: {
                candidate_id: index
                for index, candidate_id in enumerate(bundle.candidate_ids)
            }
            for bundle in bundles
        }
        excluded_bundle_ids = {
            bundle_id_by_candidate[candidate_id]
            for candidate_id in excluded
            if candidate_id in bundle_id_by_candidate
        }
        members_by_bundle: Dict[str, List[str]] = {}
        for candidate_id, match in matches_by_id.items():
            candidate = candidate_by_id.get(candidate_id, {})
            if (
                candidate_id in excluded
                or match.state == "explicit_conflict"
                or str(candidate.get("kind") or "") not in allowed_kinds
                or candidate_id not in bundle_id_by_candidate
                or bundle_id_by_candidate[candidate_id] in excluded_bundle_ids
            ):
                continue
            members_by_bundle.setdefault(
                bundle_id_by_candidate[candidate_id], []
            ).append(candidate_id)
        bundle_rank = {
            bundle_id: max(
                matches_by_id[candidate_id].rank_vector
                for candidate_id in candidate_ids
            )
            for bundle_id, candidate_ids in members_by_bundle.items()
        }
        bundle_source_key = {
            bundle_id: min(
                (
                    project_candidate_fact(candidate_by_id[candidate_id]).source_key,
                    candidate_id,
                )
                for candidate_id in candidate_ids
            )
            for bundle_id, candidate_ids in members_by_bundle.items()
        }
        ranked_bundle_ids = sorted(
            members_by_bundle,
            key=lambda bundle_id: (
                bundle_source_key[bundle_id],
                bundle_id,
            ),
        )
        ranked_bundle_ids.sort(
            key=lambda bundle_id: bundle_rank[bundle_id],
            reverse=True,
        )
        selected_bundle_ids = ranked_bundle_ids[: max(0, int(limit))]
        selected_ids: List[str] = []
        for bundle_id in selected_bundle_ids:
            member_ids = list(members_by_bundle[bundle_id])
            member_ids.sort(
                key=lambda candidate_id: order_by_bundle.get(
                    bundle_id, {}
                ).get(candidate_id, 10**9)
            )
            member_ids.sort(
                key=lambda candidate_id: matches_by_id[
                    candidate_id
                ].rank_vector,
                reverse=True,
            )
            selected_ids.extend(member_ids)
        selected = [candidate_by_id[candidate_id] for candidate_id in selected_ids]
    else:
        selected = rank_candidate_matches(
            catalog,
            matches_by_id,
            allowed_kinds=tuple(sorted(allowed_kinds)),
            limit=limit,
            excluded_candidate_ids=excluded_candidate_ids,
        )
    rows_by_state: Dict[str, List[str]] = {
        "compatible": [],
        "unknown_only": [],
        "explicit_conflict": [],
    }
    for candidate_id, match in matches_by_id.items():
        if candidate_id in excluded:
            continue
        candidate = candidate_by_id.get(candidate_id, {})
        if str(candidate.get("kind") or "") not in allowed_kinds:
            continue
        rows_by_state[match.state].append(candidate_id)
    counts = {
        state: len(rows)
        for state, rows in rows_by_state.items()
    }
    ranking_diagnostics = summarize_candidate_match_ranking(
        matches_by_id,
        [
            *rows_by_state["compatible"],
            *rows_by_state["unknown_only"],
        ],
    )
    ranking_diagnostics.update(
        {
            "population": "eligible_catalog",
            "source": "runtime_candidate_matching",
            "selection_unit": (
                "source_bundle" if candidate_kind == "numeric" else
                "narrative_source_hierarchy" if str(owner.get("kind") or (parent_owner or {}).get("kind")) == "narrative"
                else "candidate"
            ),
            "selected_source_bundle_ids": selected_bundle_ids,
        }
    )
    if source_section_counts:
        ranking_diagnostics["source_section_filter"] = source_section_counts
    if ranking_diagnostics["selection_unit"] == "narrative_source_hierarchy":
        ranking_diagnostics["selected_source_paths_by_id"] = {
            str(row["candidate_id"]): [list(part) for part in narrative_candidate_source_path(row)]
            for row in selected
        }
    return (
        selected,
        counts,
        {
            candidate_id: project_candidate_match(match)
            for candidate_id, match in matches_by_id.items()
            if str(candidate_by_id.get(candidate_id, {}).get("kind") or "")
            in allowed_kinds
        },
        ranking_diagnostics,
    )


def _semantic_candidate_cohorts(
    catalog: Sequence[Mapping[str, Any]],
    obligations: Sequence[Mapping[str, Any]],
    *,
    target_obligation_ids: Sequence[str] = (),
    excluded_candidate_ids_by_owner: Optional[Mapping[str, Sequence[str]]] = None,
) -> Dict[str, Any]:
    """Build bounded, owner-specific compiler visibility cohorts."""

    limits = dict(CALCULATION_PROMPT_POLICY.get("semantic_program_prompt_limits") or {})
    global_numeric_limit = max(0, int(limits.get("numeric_candidates") or 96))
    global_narrative_limit = max(0, int(limits.get("narrative_candidates") or 32))
    numeric_owner_limit = max(
        0,
        int(limits.get("numeric_source_bundles_per_owner") or 2),
    )
    narrative_owner_limit = max(
        0,
        int(limits.get("narrative_candidates_per_owner") or 6),
    )
    compatibility_limit = max(
        0,
        int(
            limits.get("compatibility_narrative_candidates_per_numeric_obligation")
            or 2
        ),
    )
    targets = {
        str(item).strip()
        for item in target_obligation_ids
        if str(item or "").strip()
    }
    excluded_by_owner = {
        str(owner_id): list(candidate_ids or [])
        for owner_id, candidate_ids in dict(
            excluded_candidate_ids_by_owner or {}
        ).items()
    }
    obligation_rows = [
        dict(item)
        for item in obligations
        if isinstance(item, Mapping)
        and str(item.get("obligation_id") or "").strip()
        and (
            not targets
            or str(item.get("obligation_id") or "").strip() in targets
        )
    ]

    specifications: List[Dict[str, Any]] = []
    for obligation in obligation_rows:
        obligation_id = str(obligation.get("obligation_id") or "").strip()
        is_narrative = str(obligation.get("kind") or "") == "narrative"
        # A narrative may read prose or table cells in either evidence mode.
        # Source-defined grouping is a separate contract, not table access authority.
        narrative_candidate_kind = "evidence"
        specifications.append(
            {
                "cohort_id": f"{obligation_id}:output",
                "owner_id": obligation_id,
                "parent_obligation_id": obligation_id,
                "owner_type": "obligation",
                "candidate_kind": (
                    narrative_candidate_kind if is_narrative else "numeric"
                ),
                "limit": narrative_owner_limit if is_narrative else numeric_owner_limit,
                "owner": obligation,
                "parent_owner": None,
            }
        )
        if not is_narrative:
            specifications.append(
                {
                    "cohort_id": f"{obligation_id}:compatibility",
                    "owner_id": obligation_id,
                    "parent_obligation_id": obligation_id,
                    "owner_type": "compatibility",
                    "candidate_kind": "narrative",
                    "limit": compatibility_limit,
                    "owner": obligation,
                    "parent_owner": None,
                }
            )
        for requirement in obligation.get("evidence_requirements") or []:
            if not isinstance(requirement, Mapping) or not bool(
                requirement.get("required", True)
            ):
                continue
            requirement_id = str(requirement.get("requirement_id") or "").strip()
            if not requirement_id:
                continue
            effective_requirement = {
                **dict(requirement),
                "scope": {
                    **dict(obligation.get("scope") or {}),
                    **dict(requirement.get("scope") or {}),
                },
            }
            specifications.append(
                {
                    "cohort_id": f"{obligation_id}:requirement:{requirement_id}",
                    "owner_id": requirement_id,
                    "parent_obligation_id": obligation_id,
                    "owner_type": "requirement",
                    "candidate_kind": (
                        narrative_candidate_kind if is_narrative else "numeric"
                    ),
                    "limit": narrative_owner_limit if is_narrative else numeric_owner_limit,
                    "owner": effective_requirement,
                    "parent_owner": obligation,
                }
            )

    numeric_bundle_reservation = sum(
        int(item["limit"])
        for item in specifications
        if item["candidate_kind"] == "numeric"
    )
    reservation = {
        "numeric": 0,
        "narrative": 0,
        "numeric_source_bundles": numeric_bundle_reservation,
        "numeric_limit": global_numeric_limit,
        "narrative_limit": global_narrative_limit,
    }
    candidate_by_id = {
        str(item.get("candidate_id") or ""): dict(item)
        for item in catalog
        if str(item.get("candidate_id") or "")
    }
    cohorts: List[Dict[str, Any]] = []
    match_by_id: Dict[str, Dict[str, Dict[str, Any]]] = {}
    visible_ids: List[str] = []
    for specification in specifications:
        owner_id = str(specification["owner_id"])
        selected, counts, owner_matches, ranking_diagnostics = (
            _rank_applicable_owner_candidates(
                catalog,
                owner=specification["owner"],
                parent_owner=specification.get("parent_owner"),
                candidate_kind=str(specification["candidate_kind"]),
                limit=int(specification["limit"]),
                excluded_candidate_ids=excluded_by_owner.get(owner_id, []),
            )
        )
        candidate_ids = [
            str(item.get("candidate_id") or "")
            for item in selected
            if str(item.get("candidate_id") or "")
        ]
        for candidate_id, match in owner_matches.items():
            match_by_id.setdefault(candidate_id, {})[owner_id] = dict(
                match
            )
        parent_id = str(specification["parent_obligation_id"])
        for candidate_id in candidate_ids:
            if candidate_id not in visible_ids:
                visible_ids.append(candidate_id)
        cohorts.append(
            {
                "cohort_id": str(specification["cohort_id"]),
                "owner_id": owner_id,
                "parent_obligation_id": parent_id,
                "owner_type": str(specification["owner_type"]),
                "candidate_kind": str(specification["candidate_kind"]),
                "candidate_ids": candidate_ids,
                "candidate_id_fingerprint": semantic_candidate_id_fingerprint(
                    candidate_ids
                ),
                "match_counts": counts,
                "ranking_diagnostics": ranking_diagnostics,
                "limit": int(specification["limit"]),
            }
        )

    source_group_obligation_ids = {
        str(obligation.get("obligation_id") or "")
        for obligation in obligation_rows
        if str(obligation.get("kind") or "") == "narrative"
        and str(obligation.get("evidence_mode") or "declared_inputs")
        == "source_defined_group"
    }
    source_group_selection_by_parent: Dict[str, Dict[str, Any]] = {}
    for cohort in cohorts:
        parent_id = str(cohort.get("parent_obligation_id") or "")
        if (
            parent_id not in source_group_obligation_ids
            or str(cohort.get("owner_type") or "") != "obligation"
        ):
            continue
        original_candidate_ids = list(cohort.get("candidate_ids") or [])
        explicitly_compatible_ids = [
            candidate_id
            for candidate_id in original_candidate_ids
            if str(
                match_by_id.get(candidate_id, {})
                .get(parent_id, {})
                .get("state")
                or ""
            )
            == "compatible"
        ]
        group_excluded_ids = {
            candidate_id
            for candidate_owner_id, candidate_ids in excluded_by_owner.items()
            if candidate_owner_id == parent_id
            or candidate_owner_id.startswith(f"{parent_id}:")
            for candidate_id in candidate_ids
        }
        obligation_by_id = {
            str(obligation.get("obligation_id") or ""): obligation
            for obligation in obligation_rows
        }
        selection = select_source_defined_physical_row_group(
            [candidate for candidate in catalog if source_section_applicability(
                candidate, obligation_by_id[parent_id]
            )["state"] in {"unrestricted", "match"}],
            explicitly_compatible_ids,
            owner=obligation_by_id.get(parent_id),
            limit=int(cohort.get("limit") or 0),
            excluded_candidate_ids=group_excluded_ids,
        )
        if selection.get("selection_mode") not in {
            "complete_physical_row",
            "capacity_exceeded",
        }:
            selection = {
                "selection_mode": "open",
                "physical_table_id": "",
                "physical_row_id": "",
                "candidate_ids": original_candidate_ids,
                "required_candidate_ids": [],
                "complete_option_count": 0,
            }
        source_group_selection_by_parent[parent_id] = selection

    source_group_overflow = {
        parent_id: selection
        for parent_id, selection in source_group_selection_by_parent.items()
        if selection.get("selection_mode") == "capacity_exceeded"
    }
    if source_group_overflow:
        return {
            "schema": "semantic_candidate_cohorts_v2",
            "status": "capacity_exceeded",
            "reservation": {
                **reservation,
                "source_defined_group_overflow": source_group_overflow,
            },
            "cohorts": [],
            "candidate_ids_by_owner": {},
            "visible_candidate_ids": [],
            "candidate_match_by_id": match_by_id,
            "evidence_bundle_constraints": [],
            "evidence_bundle_option_selections": [],
        }

    specification_by_cohort = {item["cohort_id"]: item for item in specifications}
    for cohort in cohorts:
        parent_id = str(cohort.get("parent_obligation_id") or "")
        selection = source_group_selection_by_parent.get(parent_id)
        if not selection:
            continue
        owner_excluded_ids = set(
            excluded_by_owner.get(str(cohort.get("owner_id") or ""), [])
        )
        specification = specification_by_cohort[cohort["cohort_id"]]
        candidate_ids = [
            candidate_id
            for candidate_id in (selection.get("candidate_ids") or [])
            if candidate_id not in owner_excluded_ids
            and source_section_applicability(candidate_by_id[candidate_id],
                specification["owner"], specification["parent_owner"])["state"] in {"unrestricted", "match"}
        ]
        cohort["candidate_ids"] = candidate_ids
        cohort["candidate_id_fingerprint"] = (
            semantic_candidate_id_fingerprint(candidate_ids)
        )
        cohort["source_defined_group_selection"] = {
            "selection_mode": str(selection.get("selection_mode") or "open"),
            "physical_table_id": str(selection.get("physical_table_id") or ""),
            "physical_row_id": str(selection.get("physical_row_id") or ""),
            "required_candidate_ids": [
                candidate_id
                for candidate_id in (
                    selection.get("required_candidate_ids") or []
                )
                if candidate_id in candidate_ids
            ],
            "complete_option_count": int(
                selection.get("complete_option_count") or 0
            ),
            "policy_group_names": list(
                selection.get("policy_group_names") or []
            ),
        }

    visible_ids = list(
        dict.fromkeys(
            candidate_id
            for cohort in cohorts
            for candidate_id in (cohort.get("candidate_ids") or [])
            if candidate_id
        )
    )

    evidence_bundle_constraints = build_physical_evidence_bundle_constraints(
        catalog,
        obligation_rows,
        cohorts=cohorts,
        candidate_match_by_id=match_by_id,
    )
    atomic_projection = _project_atomic_evidence_bundle_options(
        cohorts=cohorts,
        visible_candidate_ids=visible_ids,
        constraints=evidence_bundle_constraints,
    )

    projected_visible_ids = list(atomic_projection["visible_candidate_ids"])
    # Ranking decides what to expose, not where an exposed source may be used.
    # Physical row selection and explicit retry exclusions remain independent
    # authority boundaries, including sources visible through another owner.
    bundles_by_candidate = source_bundle_id_by_candidate_id(build_semantic_source_bundles(catalog))
    physical_allowed: Dict[str, set[str]] = {}
    for constraint in atomic_projection["evidence_bundle_constraints"]:
        for option in constraint["options"]:
            for owner_id, identifiers in option["candidate_ids_by_owner"].items():
                allowed = set(identifiers)
                physical_allowed[owner_id] = physical_allowed.get(owner_id, allowed) & allowed
    authorized_cohorts = []
    for raw_cohort in atomic_projection["cohorts"]:
        cohort = dict(raw_cohort)
        specification = specification_by_cohort[cohort["cohort_id"]]
        owner_id, parent_id = cohort["owner_id"], cohort["parent_obligation_id"]
        kind = cohort["candidate_kind"]
        allowed_kinds = {"numeric", "narrative"} if kind == "evidence" else {kind}
        excluded = set(excluded_by_owner.get(owner_id, []))
        excluded_bundles = {bundles_by_candidate[item] for item in excluded if item in bundles_by_candidate}
        exposure_ids = list(cohort["candidate_ids"])
        candidate_ids = []
        for candidate_id in dict.fromkeys([*exposure_ids, *sorted(projected_visible_ids)]):
            candidate = candidate_by_id[candidate_id]
            if candidate["kind"] not in allowed_kinds or candidate_id in excluded:
                continue
            if kind == "numeric" and bundles_by_candidate.get(candidate_id) in excluded_bundles:
                continue
            if cohort["owner_type"] != "compatibility" and parent_id in physical_allowed:
                if candidate_id not in physical_allowed[parent_id]:
                    continue
            group = cohort.get("source_defined_group_selection") or {}
            if group.get("selection_mode") == "complete_physical_row" and candidate_id not in exposure_ids:
                continue
            applicability = source_candidate_applicability(candidate, specification["owner"], specification["parent_owner"])
            match = match_by_id.get(candidate_id, {}).get(owner_id, {})
            if applicability["state"] == "explicit_conflict" or match.get("unit_state") == "conflict":
                continue
            candidate_ids.append(candidate_id)
        cohort.update(exposure_candidate_ids=exposure_ids, candidate_ids=candidate_ids,
                      candidate_id_fingerprint=semantic_candidate_id_fingerprint(candidate_ids))
        authorized_cohorts.append(cohort)
    # Reuse the canonical parent/input visibility projection without reselecting
    # physical rows. The already frozen constraints remain on the envelope.
    authority = _project_atomic_evidence_bundle_options(
        cohorts=authorized_cohorts, visible_candidate_ids=projected_visible_ids, constraints=())
    numeric_count = sum(
        str(candidate_by_id.get(candidate_id, {}).get("kind") or "")
        == "numeric"
        for candidate_id in projected_visible_ids
    )
    narrative_count = sum(
        str(candidate_by_id.get(candidate_id, {}).get("kind") or "")
        == "narrative"
        for candidate_id in projected_visible_ids
    )
    reservation = {
        **reservation,
        "numeric": numeric_count,
        "narrative": narrative_count,
    }
    if numeric_count > global_numeric_limit or narrative_count > global_narrative_limit:
        return {
            "schema": "semantic_candidate_cohorts_v2",
            "status": "capacity_exceeded",
            "reservation": reservation,
            "cohorts": [],
            "candidate_ids_by_owner": {},
            "visible_candidate_ids": [],
            "candidate_match_by_id": match_by_id,
            "evidence_bundle_constraints": [],
            "evidence_bundle_option_selections": [],
        }

    return {
        "schema": "semantic_candidate_cohorts_v2",
        "status": "ok",
        "reservation": reservation,
        "cohorts": authority["cohorts"],
        "candidate_ids_by_owner": authority[
            "candidate_ids_by_owner"
        ],
        "visible_candidate_ids": projected_visible_ids,
        "candidate_match_by_id": match_by_id,
        "evidence_bundle_constraints": atomic_projection[
            "evidence_bundle_constraints"
        ],
        "evidence_bundle_option_selections": atomic_projection[
            "evidence_bundle_option_selections"
        ],
    }


def _bounded_relevance_excerpt(
    source_text: str,
    focus_texts: List[str],
    *,
    limit: int,
) -> str:
    """Return a bounded source excerpt centered on its strongest visible hint."""

    text = _normalise_spaces(str(source_text or ""))
    bounded = max(0, int(limit))
    if not bounded or len(text) <= bounded:
        return text
    normalized_focus = list(
        dict.fromkeys(
            value
            for item in focus_texts
            for value in [
                _normalise_spaces(str(item or "")).lower(),
                *[
                    token.lower()
                    for token in re.findall(
                        r"[^\W_]+",
                        _normalise_spaces(str(item or "")),
                        flags=re.UNICODE,
                    )
                    if len(token) >= 2
                ],
            ]
            if value
        )
    )
    lowered = text.lower()
    matches = [
        (len(focus), lowered.find(focus), focus)
        for focus in normalized_focus
        if lowered.find(focus) >= 0
    ]
    if not matches:
        return text[:bounded]
    _length, position, focus = max(matches, key=lambda item: (item[0], -item[1]))
    center = position + len(focus) // 2
    start = max(0, center - bounded // 3)
    start = min(start, max(0, len(text) - bounded))
    return text[start : start + bounded]


def _retry_dependency_outputs(
    *,
    program: Mapping[str, Any],
    validation: Mapping[str, Any],
    visibility: CandidateVisibilityV1,
    obligations: Sequence[Mapping[str, Any]],
    catalog: Sequence[Mapping[str, Any]],
    query: str,
    target_obligation_ids: Sequence[str],
) -> Dict[str, Dict[str, Any]]:
    """Project executable dependencies as inputs, never as new selectable candidates."""
    targets = set(target_obligation_ids)
    dependency_ids = {
        str(dependency)
        for obligation in obligations
        if str(obligation.get("obligation_id") or "") in targets
        for dependency in obligation.get("depends_on") or []
    } - targets
    if not dependency_ids:
        return {}
    envelope = CompilationEnvelopeV2.create(
        visibility=visibility, program=program, validation=validation,
        candidate_catalog=catalog, obligations=obligations, query=query,
    )
    execution = execute_semantic_calculation_program(
        program=program, obligations=obligations, candidate_catalog=catalog, query=query,
        compilation_envelope=envelope, require_compilation_envelope=True,
    )
    outputs = execution["outputs_by_obligation"]
    inputs: Dict[str, Dict[str, Any]] = {}
    for obligation in obligations:
        obligation_id = str(obligation.get("obligation_id") or "")
        output = outputs.get(obligation_id)
        if (obligation_id not in dependency_ids or not output
                or output.get("status") != "ok" or output.get("normalized_value") is None):
            continue
        inputs[obligation_id] = {
            "kind": output["kind"],
            "label": output["label"],
            "scope": dict(obligation.get("scope") or {}),
            # For a derived output this is the calculated value, not its source display.
            "normalized_value": output["normalized_value"],
            "normalized_unit": output["normalized_unit"],
            "candidate_ids": list(output["candidate_ids"]),
            "source_row_ids": list(output["source_row_ids"]),
            "source_anchors": list(output["source_anchors"]),
        }
    return inputs


def _semantic_retry_target_ids(
    *, program: Mapping[str, Any], validation: Mapping[str, Any],
    obligations: Sequence[Mapping[str, Any]], invocation_failed: bool,
    bundle_constraints: Sequence[EvidenceBundleConstraintV1],
) -> List[str]:
    """Repair invalid/missing outputs without reopening explicit valid abstentions."""
    owner_ids = [str(item.get("obligation_id") or "") for item in obligations]
    unresolved = set(validation.get("missing_obligation_ids") or []) | set(
        validation.get("ambiguous_obligation_ids") or [])
    errors = list(validation.get("errors") or [])
    error_owners = {str(item.get("obligation_id") or "") for item in errors}
    planning_errors = {str(item.get("obligation_id") or "") for item in errors
                       if item.get("repair_action") == "repair_requirements"}
    abstentions = set()
    if (not invocation_failed and program.get("status") in {"incomplete", "ambiguous"}
            and error_owners.issubset(owner_ids)):
        declared = set(program.get("missing_obligation_ids") or []) | set(
            program.get("ambiguous_obligation_ids") or [])
        abstentions = (declared & unresolved & set(owner_ids)) - error_owners

    def bundled_owners(ids: set[str]) -> set[str]:
        expanded = set(ids)
        while True:
            previous = set(expanded)
            for constraint in bundle_constraints:
                if expanded.intersection(constraint.owner_ids):
                    expanded.update(constraint.owner_ids)
            if expanded == previous:
                return expanded

    # Row-atomic peers cannot be repaired by reopening a withheld member.
    targets = bundled_owners(unresolved - bundled_owners(abstentions | planning_errors))
    return [owner_id for owner_id in owner_ids if owner_id in targets]


def _merge_targeted_program_retry(
    *,
    previous_validation: Dict[str, Any],
    retry_program: Dict[str, Any],
    target_obligation_ids: List[str],
    previous_program: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Preserve valid prior outputs and accept retry edits only for targets."""

    targets = {
        str(item).strip() for item in target_obligation_ids if str(item).strip()
    }

    def merged_rows(validation_key: str, program_key: str) -> List[Dict[str, Any]]:
        accepted_ids = {str(item.get("obligation_id") or "") for item in previous_validation.get(validation_key) or []}
        preserved = [
            dict(item)
            for item in ((previous_program.get(program_key) or []) if previous_program is not None
                         else (previous_validation.get(validation_key) or []))
            if str((item or {}).get("obligation_id") or "").strip() in accepted_ids - targets
        ]
        for row in preserved:
            # Validation-owned quote locations are trace, not model program JSON.
            row.pop("claim_readings", None)
        replacements = [
            dict(item)
            for item in retry_program.get(program_key) or []
            if str((item or {}).get("obligation_id") or "").strip() in targets
        ]
        return [*preserved, *replacements]

    preserved_program = {
        key: [dict(item) for item in previous_validation.get(validation_key) or []
              if str(item.get("obligation_id") or "").strip() not in targets]
        for validation_key, key in (
            ("valid_direct_bindings", "direct_bindings"),
            ("valid_expressions", "expressions"),
            ("valid_narrative_bindings", "narrative_bindings"),
        )
    }
    preserved_candidate_ids = set(_semantic_program_candidate_ids(preserved_program))
    for rows in preserved_program.values():
        for row in rows:
            preserved_candidate_ids.update(
                (previous_validation.get("source_candidate_ids_by_obligation") or {}).get(
                    str(row.get("obligation_id") or ""), []
                )
            )
    source_assertions: List[Dict[str, Any]] = []
    for raw_assertion in previous_validation.get("valid_source_assertions") or []:
        assertion = dict(raw_assertion or {})
        covered_ids = {
            str(item)
            for item in (assertion.pop("covered_obligation_ids", []) or [])
            if str(item)
        }
        assertion.pop("assertion_fingerprint", None)
        if covered_ids and covered_ids.issubset(targets):
            continue
        if covered_ids.intersection(targets):
            # A shared assertion may contain a replaced target-only value. Keep
            # its exact quote, but retain authority only for untouched inputs.
            assertion["candidate_ids"] = [
                item for item in assertion.get("candidate_ids") or []
                if str(item).strip() in preserved_candidate_ids
            ]
            if not assertion["candidate_ids"]:
                continue
        source_assertions.append(assertion)
    # Assertions have no owner field, so derive their editable scope from the
    # target bindings. An extra retry assertion must not revoke a preserved
    # owner's evidence or turn an unrelated invented ID into a global error.
    target_candidate_ids = set(_semantic_program_candidate_ids({
        key: [dict(item) for item in retry_program.get(key) or []
              if isinstance(item, Mapping)
              and str(item.get("obligation_id") or "").strip() in targets]
        for key in ("direct_bindings", "expressions", "narrative_bindings")
    }))
    preserved_assertion_ids = {
        str(candidate_id).strip()
        for assertion in source_assertions
        for candidate_id in assertion.get("candidate_ids") or []
    }
    for raw_assertion in retry_program.get("source_assertions") or []:
        if not isinstance(raw_assertion, Mapping):
            continue
        candidate_ids = list(dict.fromkeys(
            str(item).strip() for item in raw_assertion.get("candidate_ids") or []
            if str(item).strip()
        ))
        if not candidate_ids or not set(candidate_ids).issubset(target_candidate_ids):
            continue
        editable_ids = [item for item in candidate_ids if item not in preserved_assertion_ids]
        if editable_ids:
            source_assertions.append({**dict(raw_assertion), "candidate_ids": editable_ids})
    deduplicated_assertions: List[Dict[str, Any]] = []
    seen_assertions: set[str] = set()
    for assertion in source_assertions:
        serialized = json.dumps(
            assertion,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if serialized in seen_assertions:
            continue
        seen_assertions.add(serialized)
        deduplicated_assertions.append(assertion)

    return {
        "status": str(retry_program.get("status") or "incomplete"),
        "direct_bindings": merged_rows(
            "valid_direct_bindings", "direct_bindings"
        ),
        "expressions": merged_rows("valid_expressions", "expressions"),
        "narrative_bindings": merged_rows(
            "valid_narrative_bindings", "narrative_bindings"
        ),
        "source_assertions": deduplicated_assertions,
        "missing_obligation_ids": [
            str(item) for item in previous_validation.get("missing_obligation_ids") or []
            if str(item).strip() not in targets
        ] + [
            str(item)
            for item in retry_program.get("missing_obligation_ids") or []
            if str(item).strip() in targets
        ],
        "ambiguous_obligation_ids": [
            str(item) for item in previous_validation.get("ambiguous_obligation_ids") or []
            if str(item).strip() not in targets
        ] + [
            str(item)
            for item in retry_program.get("ambiguous_obligation_ids") or []
            if str(item).strip() in targets
        ],
        "rationale": str(retry_program.get("rationale") or ""),
    }


def _semantic_program_candidate_ids(program: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for binding in program.get("direct_bindings") or []:
        if not isinstance(binding, dict):
            continue
        values.append(str(binding.get("candidate_id") or ""))
        values.extend(
            str(item or "")
            for item in (binding.get("compatibility_candidate_ids") or [])
        )
    for expression in program.get("expressions") or []:
        if not isinstance(expression, dict):
            continue
        values.extend(
            str(item.get("source_id") or "")
            for item in (expression.get("variable_bindings") or [])
            if isinstance(item, dict)
        )
        values.append(str(expression.get("source_display_candidate_id") or ""))
        values.extend(
            str(item or "")
            for item in (expression.get("compatibility_candidate_ids") or [])
        )
    for binding in program.get("narrative_bindings") or []:
        if isinstance(binding, dict):
            values.extend(narrative_candidate_ids(binding))
    return list(dict.fromkeys(item for item in values if item))


def _semantic_program_candidate_roles(
    program: Mapping[str, Any],
) -> Dict[str, Dict[str, List[tuple[str, str]]]]:
    roles: Dict[str, Dict[str, List[tuple[str, str]]]] = {}

    def add(
        obligation_id: str,
        role: str,
        owner_id: str,
        candidate_id: str,
    ) -> None:
        if not obligation_id or not owner_id or not candidate_id:
            return
        role_rows = roles.setdefault(obligation_id, {}).setdefault(role, [])
        row = (owner_id, candidate_id)
        if row not in role_rows:
            role_rows.append(row)

    for raw_binding in program.get("direct_bindings") or []:
        binding = dict(raw_binding or {})
        obligation_id = str(binding.get("obligation_id") or "").strip()
        add(
            obligation_id,
            "direct_primary",
            obligation_id,
            str(binding.get("candidate_id") or "").strip(),
        )
        for candidate_id in binding.get("compatibility_candidate_ids") or []:
            add(
                obligation_id,
                "compatibility",
                obligation_id,
                str(candidate_id or "").strip(),
            )
    for raw_expression in program.get("expressions") or []:
        expression = dict(raw_expression or {})
        obligation_id = str(expression.get("obligation_id") or "").strip()
        for raw_binding in expression.get("variable_bindings") or []:
            binding = dict(raw_binding or {})
            source_id = str(binding.get("source_id") or "").strip()
            requirement_id = str(
                binding.get("source_requirement_id") or obligation_id
            ).strip()
            add(
                obligation_id,
                "expression_input",
                requirement_id,
                source_id,
            )
        add(
            obligation_id,
            "source_display",
            obligation_id,
            str(expression.get("source_display_candidate_id") or "").strip(),
        )
        for candidate_id in expression.get("compatibility_candidate_ids") or []:
            add(
                obligation_id,
                "compatibility",
                obligation_id,
                str(candidate_id or "").strip(),
            )
    for raw_binding in program.get("narrative_bindings") or []:
        binding = dict(raw_binding or {})
        obligation_id = str(binding.get("obligation_id") or "").strip()
        requirement_owner_by_candidate: Dict[str, str] = {}
        for raw_evidence_binding in binding.get("evidence_bindings") or []:
            evidence_binding = dict(raw_evidence_binding or {})
            candidate_id = str(evidence_binding.get("candidate_id") or "").strip()
            requirement_id = str(
                evidence_binding.get("source_requirement_id") or ""
            ).strip()
            if candidate_id and requirement_id:
                requirement_owner_by_candidate[candidate_id] = requirement_id
        for candidate_id in narrative_candidate_ids(binding):
            normalized_id = str(candidate_id or "").strip()
            add(
                obligation_id,
                "narrative",
                requirement_owner_by_candidate.get(normalized_id, obligation_id),
                normalized_id,
            )
    return roles


def _retry_candidate_exclusions(
    *,
    program: Mapping[str, Any],
    validation_errors: Sequence[Mapping[str, Any]],
    target_obligation_ids: Sequence[str],
) -> Dict[str, List[str]]:
    target_set = {
        str(item).strip()
        for item in target_obligation_ids
        if str(item or "").strip()
    }
    candidate_roles = _semantic_program_candidate_roles(program)
    exclusions: Dict[str, List[str]] = {}
    for error in validation_errors:
        obligation_id = str(error.get("obligation_id") or "").strip()
        if error.get("repair_action") != "replace_candidate" or obligation_id not in target_set:
            continue
        owner_id = str(error.get("owner_id") or "")
        candidate_id = str(error.get("candidate_id") or "")
        selected_pairs = {
            row
            for rows in candidate_roles.get(obligation_id, {}).values()
            for row in rows
        }
        if not owner_id or not candidate_id or (owner_id, candidate_id) not in selected_pairs:
            continue
        exclusions.setdefault(owner_id, [])
        if candidate_id not in exclusions[owner_id]:
            exclusions[owner_id].append(candidate_id)
    return exclusions


class FinancialAgentCalculationMixin:
    """Compile and execute one grounded program for all answer obligations."""


    def _semantic_source_candidates_for_state(
        self,
        state: CandidateInput,
    ) -> List[Dict[str, Any]]:
        return build_semantic_source_candidates(
            state,
            source_anchor_builder=self._build_source_anchor,
        )

    def _semantic_candidate_catalog_for_state(
        self,
        state: FinancialAgentState,
        *,
        source_candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        return build_semantic_candidate_catalog(
            source_candidates
            if source_candidates is not None
            else self._semantic_source_candidates_for_state(state),
            evidence_items=list(state.get("evidence_items") or []),
        )

    @staticmethod
    def _semantic_program_prompt_rows(
        catalog: List[Dict[str, Any]],
        source_bundle_id_by_candidate: Optional[Mapping[str, str]] = None,
        source_value_span_by_candidate: Optional[
            Mapping[str, Sequence[int]]
        ] = None,
    ) -> List[Dict[str, Any]]:
        prompt_rows = [
            {
                "candidate_id": str(item.get("candidate_id") or ""),
                "kind": str(item.get("kind") or ""),
                "row_label": str(item.get("row_label") or ""),
                "row_headers": list(item.get("row_headers") or []),
                "local_entity_surfaces": list(
                    item.get("local_entity_surfaces") or []
                ),
                "column_headers": list(item.get("column_headers") or []),
                **({"interpretation_axis_sources": interpretation_axis_sources(item)}
                   if item.get("kind") == "numeric" and item.get("candidate_kind") != "sentence_value" else {}),
                "raw_value": str(item.get("raw_value") or ""),
                "raw_unit": str(item.get("raw_unit") or ""),
                **({"source_unit_hint": item.get("source_unit_hint", ""),
                    "raw_unit_source": item.get("raw_unit_source", ""),
                    "source_unit_provenance": item["source_unit_provenance"]}
                   if item.get("source_unit_provenance") else {}),
                "normalized_unit": str(item.get("normalized_unit") or ""),
                "period": str(item.get("period") or ""),
                "source_period_surface": str(item.get("source_period_surface") or ""),
                "period_role": str(item.get("period_role") or ""),
                "period_label_surfaces": list(
                    item.get("period_label_surfaces") or []
                ),
                "period_source": str(item.get("period_source") or ""),
                "period_label_scope": str(item.get("period_label_scope") or ""),
                "year": item.get("year"),
                "value_year": item.get("value_year"),
                "company": str(item.get("company") or ""),
                "document_company": str(item.get("document_company") or ""),
                "consolidation_scope": str(item.get("consolidation_scope") or ""),
                "consolidation_scope_source": str(
                    item.get("consolidation_scope_source") or ""
                ),
                "segment": str(item.get("segment") or ""),
                "basis": str(item.get("basis") or ""),
                "value_role": str(item.get("value_role") or ""),
                "statement_type": str(item.get("statement_type") or ""),
                "table_context": str(item.get("table_context") or "")[:160],
                "table_source_id": str(item.get("table_source_id") or ""),
                **({"source_document_id": item["source_document_id"]}
                   if item.get("source_document_id") else {}),
                "physical_table_id": str(item.get("physical_table_id") or ""),
                "physical_row_id": str(item.get("physical_row_id") or ""),
                "physical_cell_id": str(item.get("physical_cell_id") or ""),
                "physical_value_id": str(item.get("physical_value_id") or ""),
                "source_row_id": str(item.get("source_row_id") or ""),
                "context_fingerprint": str(item.get("context_fingerprint") or ""),
                "source_anchor": str(item.get("source_anchor") or ""),
                "source_section_path": list(candidate_section_path(item)),
                **({"local_heading": str(item["local_heading"])} if item.get("local_heading") else {}),
                **({"source_context_provenance": dict(item["source_context_provenance"])}
                   if item.get("source_context_provenance") else {}),
                "candidate_kind": str(item.get("candidate_kind") or ""),
                "source_bundle_id": str(
                    (source_bundle_id_by_candidate or {}).get(
                        str(item.get("candidate_id") or ""),
                        "",
                    )
                ),
                "source_value_span": list(
                    (source_value_span_by_candidate or {}).get(
                        str(item.get("candidate_id") or ""),
                        [],
                    )
                ),
                **({"source_body_coverage": dict(item["source_body_coverage"])}
                   if item.get("source_body_coverage") else {}),
                "aggregation_stage": str(item.get("aggregation_stage") or ""),
                "aggregate_label": str(item.get("aggregate_label") or ""),
            }
            for item in catalog
        ]
        return prompt_rows

    @staticmethod
    def _semantic_program_prompt_catalog(catalog: List[Dict[str, Any]]) -> str:
        return json.dumps(
            FinancialAgentCalculationMixin._semantic_program_prompt_rows(catalog),
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _semantic_program_prompt_payload(
        catalog: List[Dict[str, Any]],
        cohort_plan: Mapping[str, Any],
    ) -> Dict[str, Any]:
        visible_ids = [
            str(item)
            for item in (cohort_plan.get("visible_candidate_ids") or [])
            if str(item or "").strip()
        ]
        visible_set = set(visible_ids)
        visible_catalog = [
            dict(item)
            for item in catalog
            if str(item.get("candidate_id") or "") in visible_set
        ]
        source_bundles = build_semantic_source_bundles(
            visible_catalog,
            candidate_ids=visible_ids,
        )
        bundle_id_by_candidate = source_bundle_id_by_candidate_id(source_bundles)
        value_span_by_candidate = {
            candidate_id: span
            for bundle in source_bundles
            for candidate_id, span in bundle.value_span_by_candidate_id().items()
        }
        prompt_rows = FinancialAgentCalculationMixin._semantic_program_prompt_rows(
            visible_catalog,
            source_bundle_id_by_candidate=bundle_id_by_candidate,
            source_value_span_by_candidate=value_span_by_candidate,
        )
        row_by_id = {
            str(item.get("candidate_id") or ""): item
            for item in prompt_rows
            if str(item.get("candidate_id") or "")
        }
        source_contexts = {}
        for candidate in visible_catalog:
            for context in candidate.get("source_contexts") or []:
                context_id = str(context.get("context_id") or "")
                if not context_id:
                    continue
                projection = {key: value for key, value in context.items() if key != "relation"}
                if context_id in source_contexts and source_contexts[context_id] != projection:
                    raise ValueError(f"conflicting source context: {context_id}")
                source_contexts[context_id] = projection
        source_contexts = dict(sorted(source_contexts.items()))
        return project_reading_payload({
            "source_contexts_by_id": source_contexts,
            "source_context_fingerprint": hashlib.sha256(json.dumps(
                source_contexts, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
            "reservation": dict(cohort_plan.get("reservation") or {}),
            "source_bundle_fingerprint": semantic_source_bundle_fingerprint(
                source_bundles
            ),
            "source_bundles_by_id": {
                bundle.source_bundle_id: bundle.to_projection()
                for bundle in source_bundles
            },
            "cohorts": [
                _semantic_program_prompt_cohort(item)
                for item in (cohort_plan.get("cohorts") or [])
                if isinstance(item, Mapping)
            ],
            "evidence_bundle_constraints": [
                dict(item)
                for item in (
                    cohort_plan.get("evidence_bundle_constraints") or []
                )
            ],
            "evidence_bundle_option_selections": [
                {
                    key: item.get(key)
                    for key in (
                        "constraint_id",
                        "source_constraint_id",
                        "selected_option_id",
                        "selection_strategy",
                    )
                }
                for item in (
                    cohort_plan.get("evidence_bundle_option_selections") or []
                )
                if isinstance(item, Mapping)
            ],
            "candidates_by_id": {
                candidate_id: row_by_id[candidate_id]
                for candidate_id in visible_ids
                if candidate_id in row_by_id
            },
        }, visible_catalog)

    @staticmethod
    def _semantic_program_evidence_items(
        catalog: List[Dict[str, Any]],
        selected_candidate_ids: List[str],
        *, validation: Optional[Mapping[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        candidate_by_id = {
            str(item.get("candidate_id") or ""): dict(item)
            for item in catalog
            if str(item.get("candidate_id") or "")
        }
        rows: List[Dict[str, Any]] = []
        description_only_ids = narrative_description_only_ids(validation or {})
        readings_by_candidate: Dict[str, List[Dict[str, Any]]] = {}
        for binding in (validation or {}).get("valid_narrative_bindings") or []:
            for reading in binding.get("description_readings") or []:
                readings_by_candidate.setdefault(reading["candidate_id"], []).append(dict(reading))
        for candidate_id in dict.fromkeys(selected_candidate_ids):
            candidate = candidate_by_id.get(str(candidate_id or ""))
            if not candidate:
                continue
            source_text = _normalise_spaces(str(candidate.get("source_text") or ""))
            description_only = candidate_id in description_only_ids
            if description_only:
                source_text = " ".join(dict.fromkeys(reading["quote"] for reading in readings_by_candidate[candidate_id]))
            numeric_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        candidate.get("row_label"),
                        " / ".join(str(item) for item in (candidate.get("column_headers") or [])),
                        candidate.get("raw_value"),
                        candidate.get("raw_unit"),
                    )
                    if str(value or "").strip()
                )
            )
            claim = source_text or numeric_surface
            rows.append(
                {
                    "evidence_id": str(candidate_id),
                    "source_anchor": str(candidate.get("source_anchor") or ""),
                    "claim": claim,
                    "quote_span": source_text or numeric_surface,
                    "support_level": "direct",
                    "question_relevance": "high",
                    "raw_value": "" if description_only else str(candidate.get("raw_value") or ""),
                    "raw_unit": "" if description_only else str(candidate.get("raw_unit") or ""),
                    "source_row_id": str(candidate.get("source_row_id") or ""),
                    "source_candidate_id": str(candidate.get("source_candidate_id") or ""),
                    "metadata": {**{
                        key: candidate.get(key)
                        for key in (
                            "company", "year", "value_year", "period",
                            "consolidation_scope", "consolidation_scope_source", "segment",
                            "basis", "table_source_id", "statement_type", "context_fingerprint",
                            "source_document_id", "physical_table_id", "physical_row_id",
                            "physical_cell_id", "physical_value_id", "physical_cell_key",
                        )
                        if candidate.get(key) not in (None, "")
                    }, **({"description_readings": readings_by_candidate[candidate_id]} if description_only else {})},
                }
            )
        return rows

    def _compile_semantic_calculation_island(
        self,
        state: CompilationInput,
        *,
        other_selectable_ids: Sequence[str] = (),
        output_responsibility_context_json: str = "",
    ) -> Dict[str, Any]:
        """Compile one preflighted dependency/coupling island."""

        obligations = [
            dict(item)
            for item in (
                state.get("answer_obligations")
                or dict(state.get("semantic_plan") or {}).get("answer_obligations")
                or []
            )
            if isinstance(item, dict)
        ]
        query = str(state.get("query") or "")
        catalog_prebuilt = bool(
            state.get("semantic_candidate_catalog_prebuilt")
        )
        source_candidates = (
            [
                dict(item)
                for item in (state.get("semantic_source_candidates") or [])
                if isinstance(item, Mapping)
            ]
            if catalog_prebuilt
            else self._semantic_source_candidates_for_state(state)
        )
        catalog = (
            [
                dict(item)
                for item in (state.get("semantic_candidate_catalog") or [])
                if isinstance(item, Mapping)
            ]
            if catalog_prebuilt
            else self._semantic_candidate_catalog_for_state(
                state,
                source_candidates=source_candidates,
            )
        )
        cohort_plan = _semantic_candidate_cohorts(
            catalog,
            obligations,
        )
        prompt_payload = self._semantic_program_prompt_payload(catalog, cohort_plan)
        prompt_catalog_json = _compiler_json(prompt_payload)
        prompt_candidate_ids = [
            str(item)
            for item in (cohort_plan.get("visible_candidate_ids") or [])
            if str(item or "").strip()
        ]
        prompt_catalog_rows = [
            dict(item)
            for item in dict(prompt_payload.get("candidates_by_id") or {}).values()
        ]
        initial_selectable_ids_by_owner = {
            str(owner_id): list(candidate_ids or [])
            for owner_id, candidate_ids in dict(
                cohort_plan.get("candidate_ids_by_owner") or {}
            ).items()
        }
        initial_bundle_constraints = list(
            cohort_plan.get("evidence_bundle_constraints") or []
        )
        validation_bundle_constraints = list(initial_bundle_constraints)
        validation_visibility = _semantic_candidate_visibility(
            catalog,
            visible_candidate_ids=prompt_candidate_ids,
            candidate_ids_by_owner=initial_selectable_ids_by_owner,
            evidence_bundle_constraints=validation_bundle_constraints,
        )
        candidate_by_id = {
            str(item.get("candidate_id") or ""): dict(item)
            for item in catalog
            if str(item.get("candidate_id") or "")
        }
        prompt_source_catalog_rows = [
            candidate_by_id[candidate_id]
            for candidate_id in prompt_candidate_ids
            if candidate_id in candidate_by_id
        ]
        required_ids = [
            str(item.get("obligation_id") or "")
            for item in obligations
            if bool(item.get("required", True)) and str(item.get("obligation_id") or "")
        ]
        program_data: Dict[str, Any] = {
            "status": "incomplete",
            "direct_bindings": [],
            "expressions": [],
            "narrative_bindings": [],
            "source_assertions": [],
            "missing_obligation_ids": required_ids,
            "ambiguous_obligation_ids": [],
            "rationale": (
                "no answer obligations"
                if not obligations
                else "candidate cohort capacity exceeded"
                if cohort_plan.get("status") == "capacity_exceeded"
                else "no visible candidates"
                if obligations and not prompt_candidate_ids
                else ""
            ),
        }
        validation = validate_semantic_calculation_program(
            program=program_data,
            require_narrative_claims=True,
            obligations=obligations,
            candidate_catalog=catalog,
            query=query,
            candidate_visibility=validation_visibility,
        )
        retry_count = 0
        invocation_errors: List[str] = []
        validation_history: List[Dict[str, Any]] = []
        attempt_candidate_diagnostics: List[Dict[str, Any]] = []
        capture_attempts = bool(state.get("include_debug_bundle"))
        compiler_attempts: List[CompilerAttemptDebugV1] = []
        catalog_candidate_ids = set(candidate_by_id)
        if cohort_plan.get("status") == "capacity_exceeded":
            invocation_errors.append("semantic candidate cohort capacity exceeded")
        if (
            obligations
            and cohort_plan.get("status") == "ok"
            and prompt_candidate_ids
        ):
            retry_feedback = "-"
            retry_target_ids: List[str] = []
            read_only_dependency_outputs: Dict[str, Dict[str, Any]] = {}
            previous_validation: Dict[str, Any] = {}
            active_cohort_plan = dict(cohort_plan)
            active_prompt_payload = dict(prompt_payload)
            validation_selectable_ids_by_owner = dict(
                initial_selectable_ids_by_owner
            )
            for attempt in range(2):
                invocation_failed = False
                model_program_json = None
                validation_input_program_json = None
                response_error_type = ""
                transport_errors = []
                response_wire = None
                prompt_retry_feedback = "-"
                active_prompt_candidate_ids = [
                    str(item)
                    for item in (
                        active_cohort_plan.get("visible_candidate_ids") or []
                    )
                    if str(item or "").strip()
                ]
                active_prompt_catalog_json = _compiler_json(active_prompt_payload)
                active_responsibility_context_json = ""
                responsibility_prompt = ""
                references = None
                serialized_schema_bytes = None
                prompt_obligations = (
                    [item for item in obligations if str(item.get("obligation_id") or "") in set(retry_target_ids)]
                    if attempt and retry_target_ids else obligations
                )
                compilation_scope = {
                    "schema": "semantic_compilation_scope_v1",
                    "active_obligation_ids": [str(item["obligation_id"]) for item in prompt_obligations],
                    "question_role": "context_only",
                    "request_units_by_id": project_request_units(build_request_units(query), prompt_obligations),
                    "evidence_coverage": "bounded_excerpts",
                    "document_absence_established": False,
                }
                try:
                    references = CompilerReferencesV1.build(catalog, obligations, query, active_prompt_payload)
                    attempt_visibility = _semantic_candidate_visibility(catalog,
                        visible_candidate_ids=active_prompt_candidate_ids,
                        candidate_ids_by_owner=active_cohort_plan["candidate_ids_by_owner"],
                        evidence_bundle_constraints=active_cohort_plan.get("evidence_bundle_constraints") or [])
                    response_model = compiler_response_model(prompt_obligations, references, attempt_visibility)
                    serialized_schema_bytes = len(_compiler_json(response_model.model_json_schema()).encode("utf-8"))
                    structured_llm = self._llm_for_phase("program_compilation").with_structured_output(response_model)
                    wire_payload = references.project(active_prompt_payload)
                    wire_payload["schema"] = "semantic_program_candidate_payload_v9"
                    wire_payload = project_wire_reading_payload(wire_payload)
                    active_prompt_catalog_json = _compiler_json(wire_payload)
                    if any(item.get("kind") == "narrative" for item in prompt_obligations):
                        active_responsibility_context_json = output_responsibility_context_json
                    if active_responsibility_context_json:
                        active_responsibility_context_json = _compiler_json(references.project(json.loads(active_responsibility_context_json)))
                        responsibility_prompt = CALCULATION_PROMPT_POLICY[
                            "semantic_program_output_responsibility_context_template"
                        ].format(context=active_responsibility_context_json)
                    template_key = (
                        "semantic_program_narrative_prompt_template"
                        if active_prompt_payload["reading_mode"] == "narrative_only"
                        else "semantic_program_prompt_template"
                    )
                    prompt = chat_prompt_template_from_template(CALCULATION_PROMPT_POLICY[template_key])
                    row_description_instructions = (
                        CALCULATION_PROMPT_POLICY["semantic_program_row_description_instructions"]
                        if any(row.get("row_description_quote_options") for row in
                               active_prompt_payload["candidates_by_id"].values()) else ""
                    )
                    prompt_retry_feedback = project_prompt_retry_feedback(retry_feedback,
                        narrative_only=active_prompt_payload["reading_mode"] == "narrative_only")
                    if prompt_retry_feedback != "-":
                        prompt_retry_feedback = _compiler_json(references.project(json.loads(prompt_retry_feedback)))
                    prompt_value = prompt.invoke(
                        {
                            "query": query,
                            "compilation_scope": _compiler_json(references.project(compilation_scope)),
                            "obligations": _compiler_json(references.project(prompt_obligations)),
                            "output_responsibility_context": responsibility_prompt,
                            "candidate_catalog": active_prompt_catalog_json,
                            "retry_feedback": prompt_retry_feedback,
                            "row_description_instructions": row_description_instructions,
                        }
                    )
                    # The provider sees only the new per-output transport schema.
                    with diagnostic_location(attempt=attempt + 1):
                        if diagnostics_enabled():
                            messages = [{"type": message.type, "content": message.content}
                                        for message in prompt_value.to_messages()]
                            prompt_json = _compiler_json(messages)
                            record_diagnostic("compiler_request", {
                                "active_obligation_ids": compilation_scope["active_obligation_ids"],
                                "visible_candidate_ids": active_prompt_candidate_ids,
                                "prompt_messages_json": prompt_json,
                                "prompt_messages_bytes": len(prompt_json.encode("utf-8")),
                                "candidate_payload_bytes": len(active_prompt_catalog_json.encode("utf-8")),
                            })
                        compiled: Any = structured_llm.invoke(prompt_value)
                    response_wire = compiled.model_dump()
                    if capture_attempts:
                        model_program_json = _compiler_json(compiled.model_dump())
                    compiled_program = lower_compiler_response(
                        compiled, model=response_model, refs=references, obligations=prompt_obligations,
                        errors=transport_errors,
                        catalog=catalog, visibility=attempt_visibility)
                    program_data = (
                        _merge_targeted_program_retry(
                            previous_validation=previous_validation,
                            previous_program=program_data,
                            retry_program=compiled_program,
                            target_obligation_ids=retry_target_ids,
                        )
                        if attempt and retry_target_ids
                        else compiled_program
                    )
                except ProviderAdmissionError:
                    # A spending/authorization stop is not an evidence or
                    # schema failure. Preserve its cause for the caller.
                    raise
                except Exception as exc:
                    invocation_failed = True
                    response_error_type = type(exc).__name__
                    safe_error = f"{response_error_type}: compiler response unavailable or invalid"
                    invocation_errors.append(safe_error)
                    for owner_id in retry_target_ids if attempt else required_ids:
                        transport_errors.append({"code": "compiler_response_schema_error" if isinstance(exc, ValueError) else "compiler_invocation_error",
                            "obligation_id": owner_id, "owner_id": owner_id, "candidate_id": "",
                            "location": "compiler_response", "repair_action": "repair_program", "detail": safe_error})
                    failed_program = {
                        "status": "incomplete",
                        "direct_bindings": [],
                        "expressions": [],
                        "narrative_bindings": [],
                        "source_assertions": [],
                        "missing_obligation_ids": (
                            retry_target_ids if attempt else required_ids
                        ),
                        "ambiguous_obligation_ids": [],
                        "rationale": safe_error,
                    }
                    program_data = (
                        _merge_targeted_program_retry(
                            previous_validation=previous_validation,
                            previous_program=program_data,
                            retry_program=failed_program,
                            target_obligation_ids=retry_target_ids,
                        )
                        if attempt and retry_target_ids
                        else failed_program
                    )
                if capture_attempts and not invocation_failed:
                    validation_input_program_json = _compiler_json(program_data)
                validation = validate_semantic_calculation_program(
                    program=program_data,
                    require_narrative_claims=True,
                    obligations=obligations,
                    candidate_catalog=catalog,
                    query=query,
                    candidate_visibility=(
                        validation_visibility := _semantic_candidate_visibility(
                            catalog,
                            visible_candidate_ids=[
                                candidate_id
                                for candidate_ids in (
                                    validation_selectable_ids_by_owner.values()
                                )
                                for candidate_id in candidate_ids
                            ],
                            candidate_ids_by_owner=(
                                validation_selectable_ids_by_owner
                            ),
                            evidence_bundle_constraints=(
                                validation_bundle_constraints
                            ),
                        )
                    ),
                )
                execution_validation = validation
                if transport_errors:
                    validation = {**validation, "errors": [*validation["errors"], *transport_errors],
                        "status": "invalid" if not any(validation.get(key) for key in (
                            "valid_direct_bindings", "valid_expressions", "valid_narrative_bindings")) else "partial"}
                if capture_attempts:
                    compiler_attempts.append(project_compiler_attempt(
                        attempt=attempt + 1,
                        active_obligation_ids=compilation_scope["active_obligation_ids"],
                        island_obligation_ids=[str(item["obligation_id"]) for item in obligations],
                        visible_candidate_ids=active_prompt_candidate_ids,
                        model_program_json=model_program_json,
                        validation_input_program_json=validation_input_program_json,
                        validation=validation,
                        retry_feedback_text=prompt_retry_feedback,
                        response_error_type=response_error_type,
                    ))
                proposed_ids = [
                    item
                    for item in _semantic_program_candidate_ids(program_data)
                    if item in catalog_candidate_ids
                ]
                validation_history.append(
                    {
                        "attempt": attempt + 1,
                        "status": str(validation.get("status") or ""),
                        "errors": list(validation.get("errors") or []),
                        "missing_obligation_ids": list(
                            validation.get("missing_obligation_ids") or []
                        ),
                        "ambiguous_obligation_ids": list(
                            validation.get("ambiguous_obligation_ids") or []
                        ),
                        "proposed_candidate_ids": proposed_ids,
                        "visible_candidate_ids": active_prompt_candidate_ids,
                        "visible_candidate_id_fingerprint": (
                            semantic_candidate_id_fingerprint(
                                active_prompt_candidate_ids
                            )
                        ),
                        "candidate_payload_bytes": len(
                            active_prompt_catalog_json.encode("utf-8")
                        ),
                    }
                )
                attempt_candidate_diagnostics.append(
                    {
                        "attempt": attempt + 1,
                        "target_obligation_ids": list(retry_target_ids),
                        "compilation_scope": compilation_scope,
                        "output_responsibility_context_fingerprint": hashlib.sha256(
                            active_responsibility_context_json.encode("utf-8")
                        ).hexdigest() if active_responsibility_context_json else "",
                        "serialized_output_responsibility_context_bytes": len(
                            active_responsibility_context_json.encode("utf-8")
                        ),
                        "output_responsibility_prompt_bytes": len(responsibility_prompt.encode("utf-8")),
                        "read_only_dependency_ids": list(read_only_dependency_outputs),
                        "serialized_dependency_bytes": len(json.dumps(
                            read_only_dependency_outputs, ensure_ascii=False, indent=2,
                        ).encode("utf-8")) if read_only_dependency_outputs else 0,
                        "visible_candidate_ids": active_prompt_candidate_ids,
                        "visible_candidate_id_fingerprint": (
                            semantic_candidate_id_fingerprint(
                                active_prompt_candidate_ids
                            )
                        ),
                        "serialized_candidate_bytes": len(
                            active_prompt_catalog_json.encode("utf-8")
                        ),
                        "evidence_bundle_option_selections": list(
                            active_cohort_plan.get(
                                "evidence_bundle_option_selections"
                            )
                            or []
                        ),
                        "source_bundle_ids": list(
                            dict(active_prompt_payload.get("source_bundles_by_id") or {})
                        ),
                        "source_bundle_fingerprint": str(
                            active_prompt_payload.get("source_bundle_fingerprint")
                            or ""
                        ),
                        "compiler_schema": "compiler_response_v2",
                        "serialized_schema_bytes": serialized_schema_bytes,
                        "reference_fingerprint": hashlib.sha256(_compiler_json(references.entries).encode()).hexdigest() if references else "",
                        "source_context_fingerprint": active_prompt_payload.get("source_context_fingerprint", ""),
                        "source_context_count": len(active_prompt_payload.get("source_contexts_by_id") or {}),
                        "serialized_context_bytes": len(json.dumps(
                            active_prompt_payload.get("source_contexts_by_id") or {},
                            ensure_ascii=False, sort_keys=True).encode("utf-8")),
                    }
                )
                retry_target_ids = _semantic_retry_target_ids(
                    program=program_data, validation=validation, obligations=obligations,
                    invocation_failed=invocation_failed,
                    bundle_constraints=validation_visibility.evidence_bundle_constraints,
                )
                needs_retry = (
                    str(validation.get("status") or "") != "ready"
                    and bool(retry_target_ids)
                )
                if not needs_retry or attempt == 1:
                    break
                previous_validation = dict(validation)
                target_id_set = set(retry_target_ids)
                retry_exclusions = _retry_candidate_exclusions(
                    program=program_data,
                    validation_errors=list(validation.get("errors") or []),
                    target_obligation_ids=retry_target_ids,
                )
                active_cohort_plan = _semantic_candidate_cohorts(
                    catalog,
                    obligations,
                    target_obligation_ids=retry_target_ids,
                    excluded_candidate_ids_by_owner=retry_exclusions,
                )
                target_owner_ids = set(retry_target_ids)
                target_owner_ids.update(
                    str(requirement.get("requirement_id") or "")
                    for obligation in obligations
                    if str(obligation.get("obligation_id") or "") in target_id_set
                    for requirement in obligation.get("evidence_requirements") or []
                )
                retry_capacity = _semantic_candidate_capacity(catalog, [
                    *other_selectable_ids,
                    *list(active_cohort_plan.get("visible_candidate_ids") or []),
                    *[candidate_id for owner_id, ids in validation_selectable_ids_by_owner.items()
                      if owner_id not in target_owner_ids for candidate_id in ids],
                ])
                if active_cohort_plan.get("status") == "capacity_exceeded" or retry_capacity["status"] == "capacity_exceeded":
                    invocation_errors.append("retry candidate capacity exceeded")
                    attempt_candidate_diagnostics[-1]["retry_blocked_reason"] = "capacity_exceeded"
                    attempt_candidate_diagnostics[-1]["retry_capacity"] = retry_capacity
                    break
                retry_count = 1
                active_prompt_payload = self._semantic_program_prompt_payload(
                    catalog,
                    active_cohort_plan,
                )
                read_only_dependency_outputs = _retry_dependency_outputs(
                    program=program_data, validation=execution_validation, visibility=validation_visibility,
                    obligations=obligations, catalog=catalog, query=query,
                    target_obligation_ids=retry_target_ids,
                )
                target_owner_ids = set(retry_target_ids)
                for obligation in obligations:
                    obligation_id = str(
                        obligation.get("obligation_id") or ""
                    ).strip()
                    if obligation_id not in target_id_set:
                        continue
                    target_owner_ids.update(
                        str(requirement.get("requirement_id") or "").strip()
                        for requirement in (
                            obligation.get("evidence_requirements") or []
                        )
                        if str(requirement.get("requirement_id") or "").strip()
                    )
                retry_selectable_ids_by_owner = dict(
                    active_cohort_plan.get("candidate_ids_by_owner") or {}
                )
                validation_bundle_constraints = [
                    constraint
                    for constraint in initial_bundle_constraints
                    if not target_owner_ids.intersection(
                        constraint.get("owner_ids") or []
                    )
                ]
                validation_bundle_constraints.extend(
                    list(
                        active_cohort_plan.get("evidence_bundle_constraints")
                        or []
                    )
                )
                validation_selectable_ids_by_owner = {
                    **initial_selectable_ids_by_owner,
                    **{
                        owner_id: list(
                            retry_selectable_ids_by_owner.get(owner_id, [])
                        )
                        for owner_id in target_owner_ids
                    },
                }
                evidence_requirement_ids_by_obligation = {
                    str(item.get("obligation_id") or ""): [
                        str(requirement.get("requirement_id") or "")
                        for requirement in (item.get("evidence_requirements") or [])
                        if bool(requirement.get("required", True))
                        and str(requirement.get("requirement_id") or "")
                    ]
                    for item in obligations
                    if str(item.get("obligation_id") or "") in target_id_set
                }
                validation_errors_by_obligation = {
                    obligation_id: [
                        dict(item)
                        for item in (validation.get("errors") or [])
                        if str((item or {}).get("obligation_id") or "")
                        == obligation_id
                    ]
                    for obligation_id in retry_target_ids
                }
                narrative_retry_drafts = project_narrative_retry_drafts(
                    program_data, obligations=obligations, target_obligation_ids=retry_target_ids,
                    candidate_ids_by_owner=retry_selectable_ids_by_owner,
                    visible_catalog=[candidate_by_id[key]
                        for key in active_cohort_plan.get("visible_candidate_ids") or []],
                    validation_errors=validation.get("errors") or [],
                )
                retry_feedback = json.dumps(
                    {
                        "missing_obligation_ids": list(validation.get("missing_obligation_ids") or []),
                        "ambiguous_obligation_ids": list(validation.get("ambiguous_obligation_ids") or []),
                        "validation_errors": [
                            dict(item)
                            for item in (validation.get("errors") or [])
                            if str(item.get("obligation_id") or "")
                            in target_id_set
                        ],
                        "allowed_candidate_ids_by_owner": (
                            retry_selectable_ids_by_owner
                        ),
                        "read_only_dependency_outputs": read_only_dependency_outputs,
                        **({"unvalidated_compiler_response": {"outputs": {
                            key: value for key, value in response_wire.get("outputs", {}).items() if key in target_id_set}}}
                           if transport_errors and response_wire is not None else {}),
                        **({"unvalidated_narrative_drafts": narrative_retry_drafts} if narrative_retry_drafts else {}),
                        "declared_obligation_ids": [
                            str(item.get("obligation_id") or "")
                            for item in obligations
                            if str(item.get("obligation_id") or "")
                            in target_id_set or str(item.get("obligation_id") or "")
                            in read_only_dependency_outputs
                        ],
                        "declared_evidence_requirement_ids": [
                            str(requirement.get("requirement_id") or "")
                            for item in obligations
                            if str(item.get("obligation_id") or "")
                            in target_id_set
                            for requirement in (item.get("evidence_requirements") or [])
                            if str(requirement.get("requirement_id") or "")
                        ],
                        "repair_contract": {
                            **({"subject_selection_invariant": CALCULATION_PROMPT_POLICY[
                                "semantic_program_subject_selection_repair_invariant"]}
                               if any("source_selection_check" in subject for draft in narrative_retry_drafts
                                   for subject in draft.get("subject_bindings") or []) else {}),
                            "target_obligation_ids": retry_target_ids,
                            "dependency_ids_by_obligation": {
                                str(item.get("obligation_id") or ""): [
                                    str(dependency) for dependency in item.get("depends_on") or []
                                    if str(dependency) in target_id_set
                                    or str(dependency) in read_only_dependency_outputs
                                ]
                                for item in obligations
                                if str(item.get("obligation_id") or "") in target_id_set
                            },
                            "dependency_input_invariant": (
                                "Use a declared dependency output as source_ref in inputs.dependencies "
                                "when requirements exist, otherwise in inputs.own. "
                                "Read-only dependency values are execution values, not source displays. "
                                "Their candidate IDs are provenance only, not additional candidate permissions. "
                                "Do not re-emit or modify accepted dependency outputs."
                            ),
                            "evidence_requirement_ids_by_obligation": (
                                evidence_requirement_ids_by_obligation
                            ),
                            "validation_errors_by_obligation": (
                                validation_errors_by_obligation
                            ),
                            "formula_variable_binding_invariant": (
                                "The set of formula AST variable names must be "
                                "exactly equal to source/dependency input variables plus code-lowered inline request operands "
                                "and binding_count. Emit formula as operation/arguments steps, referencing only earlier "
                                "one-based steps; every step contributes to the final step. Each request quantity carries "
                                "value, owned request_unit_id and interpretation at its argument position. No separate request_inputs "
                                "or binding_count_variable field. Never copy source/dependency values into request operands."
                            ),
                            "candidate_requirement_binding_invariant": (
                                "Place each candidate selection in its declared input requirement key. "
                                "Do not repeat requirement IDs inside selections."
                            ),
                            "required_evidence_binding_invariant": (
                                "Bind every required evidence requirement exactly once; "
                                "do not invent candidate, obligation, or requirement IDs."
                            ),
                            "source_assertion_invariant": (
                                "For each prose numeric selection, use its visible source_ref and "
                                "code preserves that candidate's complete exact value span. "
                                "Do not emit selection.evidence_text; interpretation support remains separate."
                            ),
                            "numeric_context_invariant": (
                                "Code attaches the selected cell's complete axes. Do not emit axis_refs or context_bindings. "
                                "For attached outside context use selection.context_evidence once per exact quote, "
                                "choosing only context_ref values offered in this input's schema. "
                                "supports_interpretation links that quote to interpretation; resolves carries only "
                                "explicit field/value scope interpretations. If context_evidence is absent from the schema, omit it. "
                                "Internal context_bindings/source_interpretation error locations refer to these assembled proofs."
                            ),
                            "narrative_claim_invariant": CALCULATION_PROMPT_POLICY[
                                "semantic_program_narrative_repair_invariant"
                            ],
                        },
                        "instruction": "Only emit repairs for the listed obligations.",
                    },
                    ensure_ascii=False,
                    indent=2,
                )

        active_bundle_constraints = [
            constraint.to_projection()
            for constraint in validation_visibility.evidence_bundle_constraints
        ]
        active_bundle_selections = (
            _active_evidence_bundle_selection_diagnostics(
                constraints=validation_visibility.evidence_bundle_constraints,
                initial_selections=list(
                    cohort_plan.get("evidence_bundle_option_selections") or []
                ),
                attempts=attempt_candidate_diagnostics,
            )
        )
        # Transport failures belong to attempt diagnostics, not the reproducible
        # execution validation fingerprint of the lowered final program.
        validation = validate_semantic_calculation_program(program=program_data, obligations=obligations,
            candidate_catalog=catalog, query=query, candidate_visibility=validation_visibility, require_narrative_claims=True)
        compilation_envelope = CompilationEnvelopeV2.create(
            visibility=validation_visibility,
            program=program_data,
            validation=validation,
            candidate_catalog=catalog, obligations=obligations, query=query,
        )
        candidate_stage_diagnostics = {
            **semantic_candidate_stage_diagnostics(
                state=state,
                source_candidates=source_candidates,
                catalog=catalog,
                prompt_catalog=prompt_source_catalog_rows,
                cohorts=list(cohort_plan.get("cohorts") or []),
                attempts=attempt_candidate_diagnostics,
            ),
            "schema": "semantic_candidate_stage_diagnostics_v10",
            "evidence_bundle_constraints": active_bundle_constraints,
            "evidence_bundle_option_selections": active_bundle_selections,
            "source_bundle_count": len(
                dict(prompt_payload.get("source_bundles_by_id") or {})
            ),
            "source_context_count": len(prompt_payload.get("source_contexts_by_id") or {}),
            "source_context_fingerprint": prompt_payload.get("source_context_fingerprint", ""),
            "source_bundle_member_count": sum(
                len(dict(bundle).get("candidate_ids") or [])
                for bundle in dict(
                    prompt_payload.get("source_bundles_by_id") or {}
                ).values()
                if isinstance(bundle, Mapping)
            ),
            "source_bundle_fingerprint": str(
                prompt_payload.get("source_bundle_fingerprint") or ""
            ),
            "source_assertion_coverage_count": len(
                validation.get("valid_source_assertions") or []
            ),
            "source_assertion_error_count": sum(
                "source_assertion" in str(error.get("code") or "")
                or str(error.get("code") or "") == "unknown_source_bundle"
                for error in (validation.get("errors") or [])
                if isinstance(error, Mapping)
            ),
        }

        selected_candidate_ids = list(validation.get("selected_candidate_ids") or [])
        selected_candidates = [candidate_by_id[item] for item in selected_candidate_ids if item in candidate_by_id]
        proposed_candidate_ids = [
            item
            for item in _semantic_program_candidate_ids(program_data)
            if item in candidate_by_id
        ]
        proposed_candidates = [
            candidate_by_id[item]
            for item in proposed_candidate_ids
            if item in candidate_by_id
        ]
        obligation_by_id = {
            str(item.get("obligation_id") or ""): item
            for item in obligations
            if str(item.get("obligation_id") or "")
        }
        direct_binding_by_candidate_id: Dict[str, Dict[str, Any]] = {}
        for binding in validation.get("valid_direct_bindings") or []:
            candidate_id = str(binding.get("candidate_id") or "")
            if candidate_id and candidate_id not in direct_binding_by_candidate_id:
                direct_binding_by_candidate_id[candidate_id] = dict(binding)
        operand_rows: List[Dict[str, Any]] = []
        description_only_ids = narrative_description_only_ids(validation)
        for item in selected_candidates:
            if str(item.get("kind") or "") != "numeric" or item.get("candidate_id") in description_only_ids:
                continue
            candidate_id = str(item.get("candidate_id") or "")
            binding = direct_binding_by_candidate_id.get(candidate_id)
            obligation_id = str((binding or {}).get("obligation_id") or "")
            operand_rows.append(
                project_semantic_program_operand(
                    item,
                    obligation_id=obligation_id,
                    obligation=obligation_by_id.get(obligation_id),
                    validated_binding=binding,
                )
            )
        calculation_plan = {
            "status": "ok" if validation.get("status") == "ready" else "incomplete",
            "mode": "semantic_program",
            "operation": "semantic_program",
            "ordered_operand_ids": [str(item.get("operand_id") or "") for item in operand_rows],
            "program_mode": "semantic_program",
            "answer_obligations": obligations,
            "semantic_program": program_data,
            "program_validation": validation,
            "program_validation_history": validation_history,
            "program_retry_count": retry_count,
            "candidate_catalog_fingerprint": semantic_candidate_catalog_fingerprint(catalog),
            "candidate_visibility": validation_visibility.to_projection(),
            "compile_validation_fingerprint": (
                compilation_envelope.validation_fingerprint
            ),
            "execution_content_fingerprint": compilation_envelope.execution_content_fingerprint,
            "candidate_count": len(catalog),
            "prompt_candidate_count": len(prompt_catalog_rows),
            "prompt_candidate_ids": prompt_candidate_ids,
            "prompt_candidate_strategy": "source_bundle_compilation_v1",
            "prompt_candidate_payload_bytes": len(
                prompt_catalog_json.encode("utf-8")
            ),
            "candidate_cohort_status": str(cohort_plan.get("status") or ""),
            "candidate_cohort_reservation": dict(
                cohort_plan.get("reservation") or {}
            ),
            "candidate_cohorts": list(cohort_plan.get("cohorts") or []),
            "evidence_bundle_constraints": active_bundle_constraints,
            "evidence_bundle_option_selections": active_bundle_selections,
            "prompt_excerpt_strategy": "source_bundle_exact_span_v1",
            "candidate_stage_diagnostics": candidate_stage_diagnostics,
            "proposed_candidates": proposed_candidates,
            "selected_candidates": selected_candidates,
            "explanation": str(program_data.get("rationale") or ""),
            "missing_info": list(validation.get("missing_obligation_ids") or []),
        }
        trace_update = runtime_trace_state_update(
            state,
            calculation_operands=operand_rows,
            calculation_plan=calculation_plan,
            calculation_result={},
        )
        logger.info(
            "[semantic_program] compile status=%s candidates=%s selected=%s retry=%s errors=%s",
            validation.get("status"), len(catalog), len(selected_candidate_ids), retry_count,
            len(validation.get("errors") or []),
        )
        return {
            "resolved_calculation_trace": trace_update["resolved_calculation_trace"],
            "semantic_program": program_data,
            **({"compiler_attempts": compiler_attempts} if capture_attempts else {}),
            "semantic_program_validation": validation,
            "semantic_compilation_envelope": compilation_envelope,
            "semantic_program_retry_count": retry_count,
            "missing_info": list(validation.get("missing_obligation_ids") or []),
            "planner_debug_trace": {
                **dict(state.get("planner_debug_trace") or {}),
                "program_compiler_invoked": bool(validation_history),
                "program_compiler_call_count": len(validation_history),
                "program_compiler_retry_count": retry_count,
                "candidate_count": len(catalog),
                "prompt_candidate_count": len(prompt_catalog_rows),
                "candidate_cohort_status": str(cohort_plan.get("status") or ""),
                "prompt_candidate_payload_bytes": len(
                    prompt_catalog_json.encode("utf-8")
                ),
                "candidate_stage_diagnostics_schema": str(
                    candidate_stage_diagnostics.get("schema") or ""
                ),
                "selected_candidate_count": len(selected_candidate_ids),
                "program_validation_status": str(validation.get("status") or ""),
                "program_validation_errors": list(validation.get("errors") or []),
                "program_validation_history": validation_history,
                "program_invocation_errors": invocation_errors,
            },
        }

    def _compile_semantic_calculation_program(
        self,
        state: CompilationInput,
    ) -> CompilationPhase:
        """Preflight and compile deterministic obligation islands in order."""

        obligations = [
            dict(item)
            for item in (
                state.get("answer_obligations")
                or dict(state.get("semantic_plan") or {}).get(
                    "answer_obligations"
                )
                or []
            )
            if isinstance(item, Mapping)
            and str(item.get("obligation_id") or "").strip()
        ]
        query = str(state.get("query") or "")
        catalog_prebuilt = bool(
            state.get("semantic_candidate_catalog_prebuilt")
        )
        source_candidates = (
            [
                dict(item)
                for item in (state.get("semantic_source_candidates") or [])
                if isinstance(item, Mapping)
            ]
            if catalog_prebuilt
            else self._semantic_source_candidates_for_state(state)
        )
        catalog = (
            [
                dict(item)
                for item in (state.get("semantic_candidate_catalog") or [])
                if isinstance(item, Mapping)
            ]
            if catalog_prebuilt
            else self._semantic_candidate_catalog_for_state(
                state,
                source_candidates=source_candidates,
            )
        )
        candidate_by_id = {
            str(item.get("candidate_id") or ""): dict(item)
            for item in catalog
            if str(item.get("candidate_id") or "")
        }
        global_cohort_plan = _semantic_candidate_cohorts(
            catalog,
            obligations,
        )
        island_plan = build_semantic_compilation_islands(
            obligations,
            query=str(state.get("query") or ""),
            evidence_bundle_constraints=list(
                global_cohort_plan.get("evidence_bundle_constraints") or []
            ),
        )
        islands = [dict(item) for item in island_plan.get("islands") or []]
        request_errors = request_unit_errors(build_request_units(query), obligations)
        global_block_reason = ""
        if request_errors:
            global_block_reason = "invalid request unit ownership"
        elif len(islands) > MAX_SEMANTIC_COMPILATION_ISLANDS:
            global_block_reason = "semantic compilation island limit exceeded"
        elif global_cohort_plan.get("status") == "capacity_exceeded":
            global_block_reason = "semantic candidate cohort capacity exceeded"
        # An immutable presentation of the full plan, shared by narrative calls
        # and retries. It is neither island input state nor execution authority.
        output_responsibility_context_json = (
            _compiler_json(project_output_responsibility_context(query, obligations))
            if not global_block_reason and len(obligations) > 1
            and any(item.get("kind") == "narrative" for item in obligations)
            else ""
        )
        obligation_by_id = {
            str(item.get("obligation_id") or ""): item
            for item in obligations
        }
        island_results: List[Dict[str, Any]] = []
        compiler_attempts: List[CompilerAttemptDebugV1] = []
        total_retry_count = 0
        total_call_count = 0
        invocation_errors: List[str] = []
        query_selectable_by_owner = {
            owner_id: list(ids) for owner_id, ids in
            dict(global_cohort_plan.get("candidate_ids_by_owner") or {}).items()
        }
        for island in islands:
            island_ids = [
                str(item)
                for item in (island.get("obligation_ids") or [])
                if str(item)
            ]
            island_obligations = [
                obligation_by_id[obligation_id]
                for obligation_id in island_ids
                if obligation_id in obligation_by_id
            ]
            blocked_reason = global_block_reason
            if not blocked_reason and island.get("errors"):
                blocked_reason = "invalid semantic compilation island"
            if blocked_reason:
                island_cohorts = _semantic_candidate_cohorts(
                    catalog,
                    island_obligations,
                )
                visibility = _semantic_candidate_visibility(
                    catalog,
                    visible_candidate_ids=list(
                        island_cohorts.get("visible_candidate_ids") or []
                    ),
                    candidate_ids_by_owner=dict(
                        island_cohorts.get("candidate_ids_by_owner") or {}
                    ),
                    evidence_bundle_constraints=list(
                        island_cohorts.get("evidence_bundle_constraints") or []
                    ),
                )
                program = {
                    "status": "incomplete",
                    "direct_bindings": [],
                    "expressions": [],
                    "narrative_bindings": [],
                    "source_assertions": [],
                    "missing_obligation_ids": island_ids,
                    "ambiguous_obligation_ids": [],
                    "rationale": blocked_reason,
                }
                validation = validate_semantic_calculation_program(
                    program=program,
                    require_narrative_claims=True,
                    obligations=island_obligations,
                    candidate_catalog=catalog,
                    query=query,
                    candidate_visibility=visibility,
                )
                envelope = CompilationEnvelopeV2.create(
                    visibility=visibility,
                    program=program,
                    validation=validation,
                    candidate_catalog=catalog, obligations=island_obligations, query=query,
                )
                island_results.append(
                    {
                        "island": island,
                        "program": program,
                        "validation": validation,
                        "envelope": envelope,
                        "retry_count": 0,
                        "call_count": 0,
                        "prompt_bytes": 0,
                        "attempts": [],
                        "validation_history": [],
                        "blocked_reason": blocked_reason,
                    }
                )
                continue

            island_owner_ids = set(island_ids)
            island_owner_ids.update(
                str(requirement.get("requirement_id") or "")
                for obligation in island_obligations
                for requirement in obligation.get("evidence_requirements") or []
            )
            with diagnostic_location(island_id=str(island["island_id"])):
                compiled = self._compile_semantic_calculation_island(
                    {
                        **dict(state),
                        "answer_obligations": island_obligations,
                        "semantic_candidate_catalog": catalog,
                        "semantic_source_candidates": source_candidates,
                        "semantic_candidate_catalog_prebuilt": True,
                    },
                    other_selectable_ids=[
                        candidate_id for owner_id, ids in query_selectable_by_owner.items()
                        if owner_id not in island_owner_ids for candidate_id in ids
                    ],
                    output_responsibility_context_json=output_responsibility_context_json,
                )
                if diagnostics_enabled():
                    attempts = compiled.get("compiler_attempts", [])
                    record_diagnostic("compiler_island_completed", {
                        "program_json": (_compiler_json(compiled["semantic_program"])
                            if attempts and attempts[-1]["response_status"] == "parsed" else None),
                        "validation": compiled["semantic_program_validation"],
                    })
            compiler_attempts.extend(
                {**row, "island_id": str(island["island_id"])}
                for row in compiled.get("compiler_attempts", [])
            )
            island_envelope = compiled.get("semantic_compilation_envelope")
            if isinstance(island_envelope, CompilationEnvelopeV2):
                query_selectable_by_owner.update(island_envelope.visibility.candidate_ids_by_owner())
            runtime_trace = resolve_runtime_calculation_trace(
                compiled,
                allow_legacy_top_level=False,
            )
            island_calculation_plan = dict(
                runtime_trace.get("calculation_plan") or {}
            )
            retry_count = int(
                compiled.get("semantic_program_retry_count") or 0
            )
            raw_program = dict(compiled.get("semantic_program") or {})
            island_validation = dict(
                compiled.get("semantic_program_validation") or {}
            )
            valid_ids_by_program_key = {
                "direct_bindings": {
                    str(item.get("obligation_id") or "")
                    for item in (
                        island_validation.get("valid_direct_bindings") or []
                    )
                },
                "expressions": {
                    str(item.get("obligation_id") or "")
                    for item in (
                        island_validation.get("valid_expressions") or []
                    )
                },
                "narrative_bindings": {
                    str(item.get("obligation_id") or "")
                    for item in (
                        island_validation.get("valid_narrative_bindings")
                        or []
                    )
                },
            }
            accepted_program = {
                **raw_program,
                **{
                    program_key: [
                        dict(item)
                        for item in (raw_program.get(program_key) or [])
                        if isinstance(item, Mapping)
                        and str(item.get("obligation_id") or "")
                        in valid_obligation_ids
                    ]
                    for program_key, valid_obligation_ids in (
                        valid_ids_by_program_key.items()
                    )
                },
                "source_assertions": [
                    {
                        key: value
                        for key, value in dict(assertion).items()
                        if key
                        not in {
                            "assertion_fingerprint",
                            "covered_obligation_ids",
                        }
                    }
                    for assertion in (
                        island_validation.get("valid_source_assertions") or []
                    )
                    if isinstance(assertion, Mapping)
                ],
                "missing_obligation_ids": list(
                    island_validation.get("missing_obligation_ids") or []
                ),
                "ambiguous_obligation_ids": list(
                    island_validation.get("ambiguous_obligation_ids") or []
                ),
            }
            call_count = int(
                dict(compiled.get("planner_debug_trace") or {}).get(
                    "program_compiler_call_count"
                )
                or 0
            )
            total_retry_count += retry_count
            total_call_count += call_count
            island_invocation_errors = list(
                dict(compiled.get("planner_debug_trace") or {}).get(
                    "program_invocation_errors"
                )
                or []
            )
            invocation_errors.extend(str(item) for item in island_invocation_errors)
            island_attempts = list(
                dict(
                    island_calculation_plan.get(
                        "candidate_stage_diagnostics"
                    )
                    or {}
                ).get("attempts")
                or []
            )
            island_results.append(
                {
                    "island": island,
                    "program": accepted_program,
                    "validation": island_validation,
                    "envelope": compiled.get(
                        "semantic_compilation_envelope"
                    ),
                    "retry_count": retry_count,
                    "call_count": call_count,
                    "prompt_bytes": sum(
                        int(attempt.get("serialized_candidate_bytes") or 0)
                        for attempt in island_attempts
                        if isinstance(attempt, Mapping)
                    ),
                    "attempts": island_attempts,
                    "validation_history": list(
                        island_calculation_plan.get(
                            "program_validation_history"
                        )
                        or []
                    ),
                    "blocked_reason": "",
                }
            )

        order = {
            str(item.get("obligation_id") or ""): index
            for index, item in enumerate(obligations)
        }

        def merged_program_rows(key: str) -> List[Dict[str, Any]]:
            rows = [
                dict(row)
                for result in island_results
                for row in (dict(result.get("program") or {}).get(key) or [])
                if isinstance(row, Mapping)
            ]
            return sorted(
                rows,
                key=lambda row: order.get(
                    str(row.get("obligation_id") or ""),
                    len(order),
                ),
            )

        missing_ids = list(
            dict.fromkeys(
                str(obligation_id)
                for result in island_results
                for obligation_id in (
                    dict(result.get("program") or {}).get(
                        "missing_obligation_ids"
                    )
                    or []
                )
                if str(obligation_id)
            )
        )
        ambiguous_ids = list(
            dict.fromkeys(
                str(obligation_id)
                for result in island_results
                for obligation_id in (
                    dict(result.get("program") or {}).get(
                        "ambiguous_obligation_ids"
                    )
                    or []
                )
                if str(obligation_id)
            )
        )
        missing_ids.sort(key=lambda item: order.get(item, len(order)))
        ambiguous_ids.sort(key=lambda item: order.get(item, len(order)))
        merged_source_assertions: List[Dict[str, Any]] = []
        seen_source_assertions: set[str] = set()
        for result in island_results:
            for raw_assertion in (
                dict(result.get("program") or {}).get("source_assertions") or []
            ):
                if not isinstance(raw_assertion, Mapping):
                    continue
                assertion = dict(raw_assertion)
                serialized = json.dumps(
                    assertion,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                if serialized in seen_source_assertions:
                    continue
                seen_source_assertions.add(serialized)
                merged_source_assertions.append(assertion)
        merged_program: Dict[str, Any] = {
            "status": (
                "ready"
                if obligations and not missing_ids and not ambiguous_ids
                else "incomplete"
            ),
            "direct_bindings": merged_program_rows("direct_bindings"),
            "expressions": merged_program_rows("expressions"),
            "narrative_bindings": merged_program_rows(
                "narrative_bindings"
            ),
            "source_assertions": merged_source_assertions,
            "missing_obligation_ids": missing_ids,
            "ambiguous_obligation_ids": ambiguous_ids,
            "rationale": (
                str(dict(island_results[0].get("program") or {}).get("rationale") or "")
                if len(island_results) == 1 else ""
            ),
        }

        selectable_by_owner: Dict[str, List[str]] = {}
        merged_bundle_constraints: List[Dict[str, Any]] = []
        merged_bundle_constraint_ids: set[str] = set()
        for result in island_results:
            envelope = result.get("envelope")
            if not isinstance(envelope, CompilationEnvelopeV2):
                continue
            for owner_id, candidate_ids in (
                envelope.visibility.candidate_ids_by_owner().items()
            ):
                selectable_by_owner.setdefault(owner_id, [])
                selectable_by_owner[owner_id].extend(
                    candidate_id
                    for candidate_id in candidate_ids
                    if candidate_id not in selectable_by_owner[owner_id]
                )
            for constraint in envelope.visibility.evidence_bundle_constraints:
                if constraint.constraint_id in merged_bundle_constraint_ids:
                    continue
                merged_bundle_constraint_ids.add(constraint.constraint_id)
                merged_bundle_constraints.append(constraint.to_projection())
        merged_visibility = _semantic_candidate_visibility(
            catalog,
            visible_candidate_ids=[
                candidate_id
                for candidate_ids in selectable_by_owner.values()
                for candidate_id in candidate_ids
            ],
            candidate_ids_by_owner=selectable_by_owner,
            evidence_bundle_constraints=merged_bundle_constraints,
        )
        validation = validate_semantic_calculation_program(
            program=merged_program,
            require_narrative_claims=True,
            obligations=obligations,
            candidate_catalog=catalog,
            query=query,
            candidate_visibility=merged_visibility,
        )
        if len(island_results) > 1:
            # Model explanations are island-local, not a query-wide resolution verdict.
            # Bind the deterministic summary before freezing execution authority.
            valid_ids = {
                str(row.get("obligation_id") or "")
                for key in ("valid_direct_bindings", "valid_expressions", "valid_narrative_bindings")
                for row in validation.get(key) or []
            }
            merged_program["rationale"] = _compiler_json({
                "validation_status": validation.get("status"),
                "valid_obligation_ids": [owner_id for owner_id in order if owner_id in valid_ids],
                "missing_obligation_ids": list(validation.get("missing_obligation_ids") or []),
                "ambiguous_obligation_ids": list(validation.get("ambiguous_obligation_ids") or []),
                "error_codes": list(dict.fromkeys(error["code"] for error in validation.get("errors") or [])),
            })
        compilation_envelope = CompilationEnvelopeV2.create(
            visibility=merged_visibility,
            program=merged_program,
            validation=validation,
            candidate_catalog=catalog, obligations=obligations, query=query,
        )
        final_bundle_selections = _active_evidence_bundle_selection_diagnostics(
            constraints=merged_bundle_constraints,
            initial_selections=list(
                global_cohort_plan.get("evidence_bundle_option_selections")
                or []
            ),
            attempts=[
                dict(attempt)
                for result in island_results
                for attempt in (result.get("attempts") or [])
                if isinstance(attempt, Mapping)
            ],
        )

        selected_candidate_ids = list(
            validation.get("selected_candidate_ids") or []
        )
        selected_candidates = [
            candidate_by_id[candidate_id]
            for candidate_id in selected_candidate_ids
            if candidate_id in candidate_by_id
        ]
        proposed_candidate_ids = [
            candidate_id
            for candidate_id in _semantic_program_candidate_ids(merged_program)
            if candidate_id in candidate_by_id
        ]
        proposed_candidates = [
            candidate_by_id[candidate_id]
            for candidate_id in proposed_candidate_ids
        ]
        direct_binding_by_candidate_id = {
            str(binding.get("candidate_id") or ""): dict(binding)
            for binding in (validation.get("valid_direct_bindings") or [])
            if str(binding.get("candidate_id") or "")
        }
        operand_rows: List[Dict[str, Any]] = []
        description_only_ids = narrative_description_only_ids(validation)
        for candidate in selected_candidates:
            if str(candidate.get("kind") or "") != "numeric" or candidate.get("candidate_id") in description_only_ids:
                continue
            candidate_id = str(candidate.get("candidate_id") or "")
            binding = direct_binding_by_candidate_id.get(candidate_id)
            obligation_id = str((binding or {}).get("obligation_id") or "")
            operand_rows.append(
                project_semantic_program_operand(
                    candidate,
                    obligation_id=obligation_id,
                    obligation=obligation_by_id.get(obligation_id),
                    validated_binding=binding,
                )
            )

        prompt_visible_ids = list(merged_visibility.visible_candidate_ids)
        prompt_catalog_rows = [
            candidate_by_id[candidate_id]
            for candidate_id in prompt_visible_ids
            if candidate_id in candidate_by_id
        ]
        base_candidate_diagnostics = semantic_candidate_stage_diagnostics(
            state=state,
            source_candidates=source_candidates,
            catalog=catalog,
            prompt_catalog=prompt_catalog_rows,
            cohorts=list(global_cohort_plan.get("cohorts") or []),
            attempts=[],
        )
        prompt_source_bundles = build_semantic_source_bundles(
            prompt_catalog_rows,
            candidate_ids=prompt_visible_ids,
        )
        island_diagnostics = []
        for result in island_results:
            island = dict(result.get("island") or {})
            envelope = result.get("envelope")
            program_bytes = json.dumps(
                dict(result.get("program") or {}),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            island_diagnostics.append(
                {
                    "island_id": str(island.get("island_id") or ""),
                    "obligation_ids": list(
                        island.get("obligation_ids") or []
                    ),
                    "dependency_edges": list(
                        island.get("dependency_edges") or []
                    ),
                    "output_relationships": dict(island.get("output_relationships") or {}),
                    "evidence_bundle_constraint_ids": list(
                        island.get("evidence_bundle_constraint_ids") or []
                    ),
                    "evidence_bundle_edges": list(
                        island.get("evidence_bundle_edges") or []
                    ),
                    "preflight_errors": list(island.get("errors") or []),
                    "blocked_reason": str(result.get("blocked_reason") or ""),
                    "call_count": int(result.get("call_count") or 0),
                    "retry_count": int(result.get("retry_count") or 0),
                    "visibility_fingerprint": (
                        envelope.visibility.cohort_fingerprint
                        if isinstance(envelope, CompilationEnvelopeV2)
                        else ""
                    ),
                    "prompt_bytes": int(result.get("prompt_bytes") or 0),
                    "accepted_program_bytes": len(program_bytes),
                    "program_rationale": str(dict(result.get("program") or {}).get("rationale") or ""),
                    "accepted_program_fingerprint": (
                        envelope.program_fingerprint
                        if isinstance(envelope, CompilationEnvelopeV2)
                        else ""
                    ),
                }
            )
        candidate_stage_diagnostics = {
            **base_candidate_diagnostics,
            "schema": "semantic_candidate_stage_diagnostics_v10",
            "island_count": len(islands),
            "compiler_call_count": total_call_count,
            "compiler_retry_count": total_retry_count,
            "request_unit_errors": request_errors,
            "source_bundle_count": len(prompt_source_bundles),
            "source_bundle_member_count": sum(
                len(bundle.candidate_ids) for bundle in prompt_source_bundles
            ),
            "source_bundle_fingerprint": semantic_source_bundle_fingerprint(
                prompt_source_bundles
            ),
            "source_assertion_coverage_count": len(
                validation.get("valid_source_assertions") or []
            ),
            "source_assertion_error_count": sum(
                "source_assertion" in str(error.get("code") or "")
                or str(error.get("code") or "") == "unknown_source_bundle"
                for error in (validation.get("errors") or [])
                if isinstance(error, Mapping)
            ),
            "evidence_bundle_constraints": merged_bundle_constraints,
            "evidence_bundle_option_selections": final_bundle_selections,
            "attempts": [
                {
                    **dict(attempt),
                    "island_id": str(
                        dict(result.get("island") or {}).get("island_id")
                        or ""
                    ),
                }
                for result in island_results
                for attempt in (result.get("attempts") or [])
                if isinstance(attempt, Mapping)
            ],
            "islands": island_diagnostics,
        }

        calculation_plan = {
            "status": (
                "ok" if validation.get("status") == "ready" else "incomplete"
            ),
            "mode": "semantic_program",
            "operation": "semantic_program",
            "ordered_operand_ids": [
                str(item.get("operand_id") or "") for item in operand_rows
            ],
            "program_mode": "semantic_program",
            "answer_obligations": obligations,
            "semantic_program": merged_program,
            "program_validation": validation,
            "program_validation_history": [
                {
                    **dict(history),
                    "island_id": str(
                        dict(result.get("island") or {}).get("island_id")
                        or ""
                    ),
                }
                for result in island_results
                for history in (result.get("validation_history") or [])
                if isinstance(history, Mapping)
            ],
            "program_retry_count": total_retry_count,
            "candidate_catalog_fingerprint": (
                semantic_candidate_catalog_fingerprint(catalog)
            ),
            "candidate_visibility": merged_visibility.to_projection(),
            "compile_validation_fingerprint": (
                compilation_envelope.validation_fingerprint
            ),
            "execution_content_fingerprint": compilation_envelope.execution_content_fingerprint,
            "candidate_count": len(catalog),
            "prompt_candidate_count": len(prompt_visible_ids),
            "prompt_candidate_ids": prompt_visible_ids,
            "prompt_candidate_strategy": "source_bundle_compilation_islands_v1",
            "prompt_candidate_payload_bytes": sum(
                int(result.get("prompt_bytes") or 0)
                for result in island_results
            ),
            "candidate_cohort_status": str(
                global_cohort_plan.get("status") or ""
            ),
            "candidate_cohort_reservation": dict(
                global_cohort_plan.get("reservation") or {}
            ),
            "candidate_cohorts": list(
                global_cohort_plan.get("cohorts") or []
            ),
            "evidence_bundle_constraints": merged_bundle_constraints,
            "evidence_bundle_option_selections": final_bundle_selections,
            "compilation_islands": islands,
            "candidate_stage_diagnostics": candidate_stage_diagnostics,
            "proposed_candidates": proposed_candidates,
            "selected_candidates": selected_candidates,
            "explanation": str(merged_program.get("rationale") or ""),
            "missing_info": list(
                validation.get("missing_obligation_ids") or []
            ),
        }
        trace_update = runtime_trace_state_update(
            state,
            calculation_operands=operand_rows,
            calculation_plan=calculation_plan,
            calculation_result={},
        )
        logger.info(
            "[semantic_program] compile islands=%s calls=%s retries=%s status=%s",
            len(islands),
            total_call_count,
            total_retry_count,
            validation.get("status"),
        )
        return {
            "resolved_calculation_trace": trace_update["resolved_calculation_trace"],
            "semantic_program": merged_program,
            **({"compiler_attempts": compiler_attempts} if state.get("include_debug_bundle") else {}),
            "semantic_program_validation": validation,
            "semantic_compilation_envelope": compilation_envelope,
            "semantic_program_retry_count": total_retry_count,
            "missing_info": list(
                validation.get("missing_obligation_ids") or []
            ),
            "planner_debug_trace": {
                **dict(state.get("planner_debug_trace") or {}),
                "program_compiler_invoked": bool(total_call_count),
                "program_compiler_call_count": total_call_count,
                "program_compiler_retry_count": total_retry_count,
                "request_unit_errors": request_errors,
                "candidate_count": len(catalog),
                "prompt_candidate_count": len(prompt_visible_ids),
                "candidate_cohort_status": str(
                    global_cohort_plan.get("status") or ""
                ),
                "prompt_candidate_payload_bytes": calculation_plan[
                    "prompt_candidate_payload_bytes"
                ],
                "candidate_stage_diagnostics_schema": (
                    "semantic_candidate_stage_diagnostics_v9"
                ),
                "selected_candidate_count": len(selected_candidate_ids),
                "program_validation_status": str(
                    validation.get("status") or ""
                ),
                "program_validation_errors": list(
                    validation.get("errors") or []
                ),
                "program_validation_history": calculation_plan["program_validation_history"],
                "program_invocation_errors": invocation_errors,
                "compilation_islands": island_diagnostics,
            },
        }

    def _execute_semantic_calculation_program(
        self,
        state: NumericExecutionInput,
    ) -> NumericResultPhase:
        obligations = list(state.get("answer_obligations") or [])
        catalog = list(state.get("semantic_candidate_catalog") or [])
        current_trace = resolve_runtime_calculation_trace(state, allow_legacy_top_level=False)
        envelope = state.get("semantic_compilation_envelope")
        execution = execute_semantic_calculation_program(
            program=dict(state.get("semantic_program") or {}),
            obligations=obligations, candidate_catalog=catalog,
            query=str(state.get("query") or ""),
            compilation_envelope=envelope if isinstance(envelope, CompilationEnvelopeV2) else None,
            require_compilation_envelope=True,
        )
        selected_ids = list(execution.get("selected_candidate_ids") or [])
        logger.info(
            "[semantic_program] execute status=%s outputs=%s missing=%s",
            execution.get("status"), len(execution.get("outputs") or []),
            len(execution.get("missing_obligation_ids") or []),
        )
        return {
            "execution": execution,
            "calculation_plan": dict(current_trace.get("calculation_plan") or {}),
            "evidence_items": self._semantic_program_evidence_items(catalog, selected_ids, validation=execution["validation"]),
        }

    def _format_citations(self, state: FinancialAgentState) -> Dict[str, Any]:
        seen: set[Any] = set()
        citations: List[str] = []
        selected_ids = {
            str(value).strip()
            for value in (state.get("selected_claim_ids") or [])
            if str(value).strip()
        }
        for evidence in list(state.get("evidence_items") or []):
            if not isinstance(evidence, dict):
                continue
            evidence_id = str(evidence.get("evidence_id") or "").strip()
            if selected_ids and evidence_id not in selected_ids:
                continue
            anchor = _normalise_spaces(str(evidence.get("source_anchor") or ""))
            metadata = dict(evidence.get("metadata") or {})
            metadata_anchor = self._build_source_anchor(metadata) if metadata else ""
            if metadata_anchor and (not anchor or len(metadata_anchor) > len(anchor)):
                anchor = metadata_anchor
            if anchor and anchor not in seen:
                seen.add(anchor)
                citations.append(anchor)
        for doc, score in state.get("retrieved_docs", []):
            metadata = dict(getattr(doc, "metadata", {}) or {})
            key = (
                metadata.get("company"), metadata.get("year"),
                metadata.get("section_path"), metadata.get("chunk_uid"),
            )
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                f"[{metadata.get('company', '?')}] {metadata.get('year', '?')}년 "
                f"{metadata.get('report_type', '?')} / "
                f"{metadata.get('section_path', metadata.get('section', '?'))} / "
                f"{metadata.get('block_type', '?')} (score: {score:.3f})"
            )
        return {"citations": citations}
