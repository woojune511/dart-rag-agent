"""Semantic calculation-program nodes for the financial graph."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.agent.financial_candidate_matching import (
    build_physical_evidence_bundle_constraints,
    build_candidate_matches,
    candidate_cell_local_source_text,
    project_candidate_match,
    rank_candidate_matches,
    select_source_defined_physical_row_group,
)
from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program,
    project_semantic_program_operand,
    semantic_candidate_applicability,
    validate_semantic_calculation_program,
)
from src.agent.financial_graph_model_loaders import semantic_calculation_program_model
from src.agent.financial_graph_state import FinancialAgentState
from src.agent.financial_langchain_loaders import chat_prompt_template_from_template
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    build_semantic_source_candidates,
    semantic_candidate_id_fingerprint,
    semantic_candidate_catalog_fingerprint,
    semantic_candidate_stage_diagnostics,
)
from src.agent.financial_runtime_normalization import _normalise_spaces
from src.agent.financial_runtime_contracts import (
    CandidateVisibilityV1,
    CompilationEnvelopeV1,
    EvidenceBundleConstraintV1,
)
from src.agent.financial_runtime_trace import resolve_runtime_calculation_trace, runtime_trace_state_update
from src.agent.financial_task_artifacts import (
    calculation_plan_artifact_update,
    calculation_result_artifact_update,
    operand_set_artifact_update,
)
from src.config.retrieval_policy import CALCULATION_PROMPT_POLICY


logger = logging.getLogger(__name__)

MAX_SEMANTIC_COMPILATION_ISLANDS = 8


def build_semantic_compilation_islands(
    obligations: Sequence[Mapping[str, Any]],
    *,
    evidence_bundle_constraints: Sequence[Mapping[str, Any]] = (),
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
    dependency_edges: List[tuple[str, str]] = []
    for obligation_id, obligation in obligation_by_id.items():
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

    coupling_groups: Dict[str, List[str]] = {}
    for obligation_id, obligation in obligation_by_id.items():
        coupling_key = _normalise_spaces(
            str(obligation.get("coupling_key") or "")
        )
        if coupling_key:
            coupling_groups.setdefault(coupling_key, []).append(obligation_id)
    for obligation_ids in coupling_groups.values():
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
        island_coupling_keys = [
            coupling_key
            for coupling_key, obligation_ids in coupling_groups.items()
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
                "coupling_keys": island_coupling_keys,
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
        selections.append(
            {
                "constraint_id": active_constraint.constraint_id,
                "source_constraint_id": constraint.constraint_id,
                "selected_option_id": selected_option.option_id,
                "selection_strategy": (
                    "owner_cohort_sum_then_worst_rank_v1"
                ),
                "ranked_options": [
                    option.to_projection() for option in constraint.options
                ],
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


def _rank_applicable_owner_candidates(
    catalog: Sequence[Mapping[str, Any]],
    *,
    owner: Mapping[str, Any],
    candidate_kind: str,
    limit: int,
    parent_owner: Optional[Mapping[str, Any]] = None,
    excluded_candidate_ids: Sequence[str] = (),
) -> tuple[List[Dict[str, Any]], Dict[str, int], Dict[str, Dict[str, Any]]]:
    allowed_kinds = (
        {"numeric", "narrative"}
        if candidate_kind == "evidence"
        else {candidate_kind}
    )
    base_applicability_by_id: Dict[str, Dict[str, Any]] = {}
    for raw_candidate in catalog:
        candidate = dict(raw_candidate or {})
        candidate_id = str(candidate.get("candidate_id") or "").strip()
        if not candidate_id:
            continue
        base_applicability_by_id[candidate_id] = semantic_candidate_applicability(
            candidate,
            owner,
        )
    matches_by_id = build_candidate_matches(
        catalog,
        owner=owner,
        parent_owner=parent_owner,
        base_applicability_by_id=base_applicability_by_id,
    )
    selected = rank_candidate_matches(
        catalog,
        matches_by_id,
        allowed_kinds=tuple(sorted(allowed_kinds)),
        limit=limit,
        excluded_candidate_ids=excluded_candidate_ids,
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
    return (
        selected,
        counts,
        {
            candidate_id: project_candidate_match(match)
            for candidate_id, match in matches_by_id.items()
            if str(candidate_by_id.get(candidate_id, {}).get("kind") or "")
            in allowed_kinds
        },
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
        int(limits.get("numeric_candidates_per_owner") or 4),
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
        is_source_defined_group = (
            is_narrative
            and str(obligation.get("evidence_mode") or "declared_inputs")
            == "source_defined_group"
        )
        narrative_candidate_kind = (
            "evidence" if is_source_defined_group else "narrative"
        )
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

    numeric_reservation = sum(
        int(item["limit"])
        for item in specifications
        if item["candidate_kind"] in {"numeric", "evidence"}
    )
    narrative_reservation = sum(
        int(item["limit"])
        for item in specifications
        if item["candidate_kind"] in {"narrative", "evidence"}
    )
    reservation = {
        "numeric": numeric_reservation,
        "narrative": narrative_reservation,
        "numeric_limit": global_numeric_limit,
        "narrative_limit": global_narrative_limit,
    }
    if (
        numeric_reservation > global_numeric_limit
        or narrative_reservation > global_narrative_limit
    ):
        return {
            "schema": "semantic_candidate_cohorts_v2",
            "status": "capacity_exceeded",
            "reservation": reservation,
            "cohorts": [],
            "candidate_ids_by_owner": {},
            "visible_candidate_ids": [],
            "candidate_match_by_id": {},
            "evidence_bundle_constraints": [],
            "evidence_bundle_option_selections": [],
        }

    cohorts: List[Dict[str, Any]] = []
    match_by_id: Dict[str, Dict[str, Dict[str, Any]]] = {}
    visible_ids: List[str] = []
    for specification in specifications:
        owner_id = str(specification["owner_id"])
        selected, counts, owner_matches = _rank_applicable_owner_candidates(
            catalog,
            owner=specification["owner"],
            parent_owner=specification.get("parent_owner"),
            candidate_kind=str(specification["candidate_kind"]),
            limit=int(specification["limit"]),
            excluded_candidate_ids=excluded_by_owner.get(owner_id, []),
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
            catalog,
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

    for cohort in cohorts:
        parent_id = str(cohort.get("parent_obligation_id") or "")
        selection = source_group_selection_by_parent.get(parent_id)
        if not selection:
            continue
        owner_excluded_ids = set(
            excluded_by_owner.get(str(cohort.get("owner_id") or ""), [])
        )
        candidate_ids = [
            candidate_id
            for candidate_id in (selection.get("candidate_ids") or [])
            if candidate_id not in owner_excluded_ids
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

    return {
        "schema": "semantic_candidate_cohorts_v2",
        "status": "ok",
        "reservation": reservation,
        "cohorts": atomic_projection["cohorts"],
        "candidate_ids_by_owner": atomic_projection[
            "candidate_ids_by_owner"
        ],
        "visible_candidate_ids": atomic_projection["visible_candidate_ids"],
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


def _merge_targeted_program_retry(
    *,
    previous_validation: Dict[str, Any],
    retry_program: Dict[str, Any],
    target_obligation_ids: List[str],
) -> Dict[str, Any]:
    """Preserve valid prior outputs and accept retry edits only for targets."""

    targets = {
        str(item).strip() for item in target_obligation_ids if str(item).strip()
    }

    def merged_rows(validation_key: str, program_key: str) -> List[Dict[str, Any]]:
        preserved = [
            dict(item)
            for item in previous_validation.get(validation_key) or []
            if str((item or {}).get("obligation_id") or "").strip() not in targets
        ]
        replacements = [
            dict(item)
            for item in retry_program.get(program_key) or []
            if str((item or {}).get("obligation_id") or "").strip() in targets
        ]
        return [*preserved, *replacements]

    return {
        "status": str(retry_program.get("status") or "incomplete"),
        "direct_bindings": merged_rows(
            "valid_direct_bindings", "direct_bindings"
        ),
        "expressions": merged_rows("valid_expressions", "expressions"),
        "narrative_bindings": merged_rows(
            "valid_narrative_bindings", "narrative_bindings"
        ),
        "missing_obligation_ids": [
            str(item)
            for item in retry_program.get("missing_obligation_ids") or []
            if str(item).strip() in targets
        ],
        "ambiguous_obligation_ids": [
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
            values.extend(str(item or "") for item in (binding.get("candidate_ids") or []))
    return list(dict.fromkeys(item for item in values if item))


_CANDIDATE_REJECTION_ERROR_CODES = {
    "candidate_subject_mismatch",
    "candidate_scope_mismatch",
    "candidate_requirement_scope_mismatch",
    "direct_result_unit_mismatch",
    "empty_direct_rendering",
    "unknown_or_nonnumeric_candidate",
    "source_display_scope_mismatch",
    "source_display_unit_mismatch",
    "empty_source_display_rendering",
    "invalid_source_display_candidate",
    "nonnumeric_expression_source",
    "invalid_compatibility_candidate",
    "compatibility_scope_mismatch",
    "direct_compatibility_context_mismatch",
    "unknown_narrative_candidate",
    "evidence_bundle_mismatch",
}


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
        for candidate_id in binding.get("candidate_ids") or []:
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
    roles_by_code = {
        "candidate_subject_mismatch": ("direct_primary",),
        "candidate_scope_mismatch": ("direct_primary", "narrative"),
        "direct_result_unit_mismatch": ("direct_primary",),
        "empty_direct_rendering": ("direct_primary",),
        "unknown_or_nonnumeric_candidate": ("direct_primary",),
        "candidate_requirement_scope_mismatch": (
            "expression_input",
            "narrative",
        ),
        "nonnumeric_expression_source": ("expression_input",),
        "source_display_scope_mismatch": ("source_display",),
        "source_display_unit_mismatch": ("source_display",),
        "empty_source_display_rendering": ("source_display",),
        "invalid_source_display_candidate": ("source_display",),
        "invalid_compatibility_candidate": ("compatibility",),
        "compatibility_scope_mismatch": ("compatibility",),
        "direct_compatibility_context_mismatch": ("compatibility",),
        "unknown_narrative_candidate": ("narrative",),
        "evidence_bundle_mismatch": (
            "direct_primary",
            "narrative",
        ),
    }
    exclusions: Dict[str, List[str]] = {}
    for error in validation_errors:
        code = str(error.get("code") or "")
        obligation_id = str(error.get("obligation_id") or "").strip()
        if code not in _CANDIDATE_REJECTION_ERROR_CODES:
            continue
        if not obligation_id or obligation_id not in target_set:
            continue
        obligation_roles = candidate_roles.get(obligation_id, {})
        candidate_rows = [
            row
            for role in roles_by_code.get(code, ())
            for row in obligation_roles.get(role, [])
        ]
        detail = str(error.get("detail") or "").strip()
        exact_rows = [row for row in candidate_rows if row[1] == detail]
        if exact_rows:
            candidate_rows = exact_rows
        elif code == "unknown_narrative_candidate":
            candidate_rows = []
        elif code == "candidate_requirement_scope_mismatch":
            requirement_id = detail.partition(": scope mismatch:")[0].strip()
            requirement_rows = [
                row for row in candidate_rows if row[0] == requirement_id
            ]
            if requirement_rows:
                candidate_rows = requirement_rows
        for owner_id, candidate_id in candidate_rows:
            exclusions.setdefault(owner_id, [])
            if candidate_id not in exclusions[owner_id]:
                exclusions[owner_id].append(candidate_id)
    return exclusions


class FinancialAgentCalculationMixin:
    """Compile and execute one grounded program for all answer obligations."""

    def _operand_set_artifact_update(
        self,
        state: FinancialAgentState,
        active_subtask: Dict[str, Any],
        operand_rows: List[Dict[str, Any]],
        *,
        status: str,
        summary: str,
        payload: Dict[str, Any],
        evidence_refs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        task_id = str(active_subtask.get("task_id") or "task_1")
        return operand_set_artifact_update(
            tasks=list(state.get("tasks") or []),
            artifacts=list(state.get("artifacts") or []),
            task_id=task_id,
            task_label=str(active_subtask.get("metric_label") or task_id),
            query=self._calc_query(state),
            metric_family="semantic_program",
            operand_rows=operand_rows,
            status=status,
            summary=summary,
            payload=payload,
            evidence_refs=evidence_refs,
        )

    def _calculation_plan_artifact_update(
        self,
        state: FinancialAgentState,
        calculation_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        active_subtask = dict(state.get("active_subtask") or {})
        task_id = str(active_subtask.get("task_id") or "task_1")
        return calculation_plan_artifact_update(
            tasks=list(state.get("tasks") or []),
            artifacts=list(state.get("artifacts") or []),
            task_id=task_id,
            task_label=str(active_subtask.get("metric_label") or task_id),
            query=self._calc_query(state),
            metric_family="semantic_program",
            calculation_plan=calculation_plan,
        )

    def _semantic_source_candidates_for_state(
        self,
        state: FinancialAgentState,
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
        candidate_match_by_id: Optional[
            Mapping[str, Mapping[str, Mapping[str, Any]]]
        ] = None,
    ) -> List[Dict[str, Any]]:
        limits = dict(CALCULATION_PROMPT_POLICY.get("semantic_program_prompt_limits") or {})
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
                "raw_value": str(item.get("raw_value") or ""),
                "raw_unit": str(item.get("raw_unit") or ""),
                "normalized_unit": str(item.get("normalized_unit") or ""),
                "period": str(item.get("period") or ""),
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
                "table_source_id": str(item.get("table_source_id") or ""),
                "physical_table_id": str(item.get("physical_table_id") or ""),
                "physical_row_id": str(item.get("physical_row_id") or ""),
                "physical_cell_id": str(item.get("physical_cell_id") or ""),
                "physical_value_id": str(item.get("physical_value_id") or ""),
                "source_row_id": str(item.get("source_row_id") or ""),
                "context_fingerprint": str(item.get("context_fingerprint") or ""),
                "source_anchor": str(item.get("source_anchor") or ""),
                "candidate_kind": str(item.get("candidate_kind") or ""),
                "aggregation_stage": str(item.get("aggregation_stage") or ""),
                "aggregate_label": str(item.get("aggregate_label") or ""),
                "match_by_owner": {
                    str(owner_id): dict(match)
                    for owner_id, match in dict(
                        (candidate_match_by_id or {}).get(
                            str(item.get("candidate_id") or ""),
                            {},
                        )
                    ).items()
                },
                "source_text": _bounded_relevance_excerpt(
                    candidate_cell_local_source_text(item),
                    [
                        str(item.get("row_label") or ""),
                        str(item.get("raw_value") or ""),
                        *[
                            str(value)
                            for value in (item.get("local_entity_surfaces") or [])
                        ],
                    ],
                    limit=max(
                        0,
                        int(
                            limits.get(
                                "numeric_source_chars"
                                if str(item.get("kind") or "") == "numeric"
                                else "narrative_source_chars"
                            )
                            or (
                                280
                                if str(item.get("kind") or "") == "numeric"
                                else 600
                            )
                        ),
                    ),
                ),
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
        prompt_rows = FinancialAgentCalculationMixin._semantic_program_prompt_rows(
            visible_catalog,
            candidate_match_by_id=dict(
                cohort_plan.get("candidate_match_by_id") or {}
            ),
        )
        row_by_id = {
            str(item.get("candidate_id") or ""): item
            for item in prompt_rows
            if str(item.get("candidate_id") or "")
        }
        return {
            "schema": "semantic_program_candidate_payload_v4",
            "reservation": dict(cohort_plan.get("reservation") or {}),
            "cohorts": [
                dict(item) for item in (cohort_plan.get("cohorts") or [])
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
        }

    @staticmethod
    def _semantic_program_evidence_items(
        catalog: List[Dict[str, Any]],
        selected_candidate_ids: List[str],
    ) -> List[Dict[str, Any]]:
        candidate_by_id = {
            str(item.get("candidate_id") or ""): dict(item)
            for item in catalog
            if str(item.get("candidate_id") or "")
        }
        rows: List[Dict[str, Any]] = []
        for candidate_id in dict.fromkeys(selected_candidate_ids):
            candidate = candidate_by_id.get(str(candidate_id or ""))
            if not candidate:
                continue
            source_text = _normalise_spaces(str(candidate.get("source_text") or ""))
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
                    "raw_value": str(candidate.get("raw_value") or ""),
                    "raw_unit": str(candidate.get("raw_unit") or ""),
                    "source_row_id": str(candidate.get("source_row_id") or ""),
                    "source_candidate_id": str(candidate.get("source_candidate_id") or ""),
                    "metadata": {
                        key: candidate.get(key)
                        for key in (
                            "company", "year", "value_year", "period",
                            "consolidation_scope", "consolidation_scope_source", "segment",
                            "basis", "table_source_id", "statement_type", "context_fingerprint",
                        )
                        if candidate.get(key) not in (None, "")
                    },
                }
            )
        return rows

    def _compile_semantic_calculation_island(
        self,
        state: FinancialAgentState,
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
        cohort_plan = _semantic_candidate_cohorts(catalog, obligations)
        prompt_payload = self._semantic_program_prompt_payload(catalog, cohort_plan)
        prompt_catalog_json = json.dumps(
            prompt_payload,
            ensure_ascii=False,
            indent=2,
        )
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
            "missing_obligation_ids": required_ids,
            "ambiguous_obligation_ids": [],
            "rationale": (
                "no answer obligations"
                if not obligations
                else "candidate cohort capacity exceeded"
                if cohort_plan.get("status") == "capacity_exceeded"
                else ""
            ),
        }
        validation = validate_semantic_calculation_program(
            program=program_data,
            obligations=obligations,
            candidate_catalog=catalog,
            query=query,
            candidate_visibility=validation_visibility,
        )
        retry_count = 0
        invocation_errors: List[str] = []
        validation_history: List[Dict[str, Any]] = []
        attempt_candidate_diagnostics: List[Dict[str, Any]] = []
        catalog_candidate_ids = set(candidate_by_id)
        if cohort_plan.get("status") == "capacity_exceeded":
            invocation_errors.append("semantic candidate cohort capacity exceeded")
        if obligations and cohort_plan.get("status") == "ok":
            structured_llm = self._llm_for_phase("program_compilation").with_structured_output(
                semantic_calculation_program_model()
            )
            prompt = chat_prompt_template_from_template(
                str(CALCULATION_PROMPT_POLICY.get("semantic_program_prompt_template") or "")
            )
            retry_feedback = "-"
            retry_target_ids: List[str] = []
            previous_validation: Dict[str, Any] = {}
            active_cohort_plan = dict(cohort_plan)
            active_prompt_payload = dict(prompt_payload)
            validation_selectable_ids_by_owner = dict(
                initial_selectable_ids_by_owner
            )
            for attempt in range(2):
                active_prompt_candidate_ids = [
                    str(item)
                    for item in (
                        active_cohort_plan.get("visible_candidate_ids") or []
                    )
                    if str(item or "").strip()
                ]
                active_prompt_catalog_json = json.dumps(
                    active_prompt_payload,
                    ensure_ascii=False,
                    indent=2,
                )
                try:
                    prompt_obligations = (
                        [
                            item
                            for item in obligations
                            if str(item.get("obligation_id") or "")
                            in set(retry_target_ids)
                        ]
                        if attempt and retry_target_ids
                        else obligations
                    )
                    prompt_value = prompt.invoke(
                        {
                            "query": query,
                            "obligations": json.dumps(
                                prompt_obligations,
                                ensure_ascii=False,
                                indent=2,
                            ),
                            "candidate_catalog": active_prompt_catalog_json,
                            "retry_feedback": retry_feedback,
                        }
                    )
                    compiled: Any = structured_llm.invoke(prompt_value)
                    compiled_program = compiled.model_dump()
                    program_data = (
                        _merge_targeted_program_retry(
                            previous_validation=previous_validation,
                            retry_program=compiled_program,
                            target_obligation_ids=retry_target_ids,
                        )
                        if attempt and retry_target_ids
                        else compiled_program
                    )
                except Exception as exc:
                    invocation_errors.append(str(exc))
                    failed_program = {
                        "status": "incomplete",
                        "direct_bindings": [],
                        "expressions": [],
                        "narrative_bindings": [],
                        "missing_obligation_ids": (
                            retry_target_ids if attempt else required_ids
                        ),
                        "ambiguous_obligation_ids": [],
                        "rationale": str(exc),
                    }
                    program_data = (
                        _merge_targeted_program_retry(
                            previous_validation=previous_validation,
                            retry_program=failed_program,
                            target_obligation_ids=retry_target_ids,
                        )
                        if attempt and retry_target_ids
                        else failed_program
                    )
                validation = validate_semantic_calculation_program(
                    program=program_data,
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
                    }
                )
                retry_target_ids = list(
                    dict.fromkeys(
                        [
                            *list(validation.get("missing_obligation_ids") or []),
                            *list(validation.get("ambiguous_obligation_ids") or []),
                        ]
                    )
                )
                retry_target_set = set(retry_target_ids)
                for constraint in validation_visibility.evidence_bundle_constraints:
                    if retry_target_set.intersection(constraint.owner_ids):
                        retry_target_set.update(constraint.owner_ids)
                retry_target_ids = [
                    str(obligation.get("obligation_id") or "")
                    for obligation in obligations
                    if str(obligation.get("obligation_id") or "")
                    in retry_target_set
                ]
                needs_retry = (
                    str(validation.get("status") or "") != "ready"
                    and bool(retry_target_ids)
                )
                if not needs_retry or attempt == 1:
                    break
                retry_count = 1
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
                active_prompt_payload = self._semantic_program_prompt_payload(
                    catalog,
                    active_cohort_plan,
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
                        "declared_obligation_ids": [
                            str(item.get("obligation_id") or "")
                            for item in obligations
                            if str(item.get("obligation_id") or "")
                            in target_id_set
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
                            "target_obligation_ids": retry_target_ids,
                            "evidence_requirement_ids_by_obligation": (
                                evidence_requirement_ids_by_obligation
                            ),
                            "validation_errors_by_obligation": (
                                validation_errors_by_obligation
                            ),
                            "formula_variable_binding_invariant": (
                                "The set of formula AST variable names must be "
                                "exactly equal to the set of variable_bindings.variable values."
                            ),
                            "candidate_requirement_binding_invariant": (
                                "Every candidate source must bind one requirement ID "
                                "declared for the same target obligation."
                            ),
                            "required_evidence_binding_invariant": (
                                "Bind every required evidence requirement exactly once; "
                                "do not invent candidate, obligation, or requirement IDs."
                            ),
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
        compilation_envelope = CompilationEnvelopeV1.create(
            visibility=validation_visibility,
            program=program_data,
            validation=validation,
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
            "schema": "semantic_candidate_stage_diagnostics_v6",
            "evidence_bundle_constraints": active_bundle_constraints,
            "evidence_bundle_option_selections": active_bundle_selections,
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
        for item in selected_candidates:
            if str(item.get("kind") or "") != "numeric":
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
            "candidate_count": len(catalog),
            "prompt_candidate_count": len(prompt_catalog_rows),
            "prompt_candidate_ids": prompt_candidate_ids,
            "prompt_candidate_strategy": "atomic_evidence_bundle_option_v1",
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
            "prompt_excerpt_strategy": "cell_local_fact_projection_v1",
            "candidate_stage_diagnostics": candidate_stage_diagnostics,
            "proposed_candidates": proposed_candidates,
            "selected_candidates": selected_candidates,
            "explanation": str(program_data.get("rationale") or ""),
            "missing_info": list(validation.get("missing_obligation_ids") or []),
        }
        active_subtask = dict(state.get("active_subtask") or {})
        operand_update = self._operand_set_artifact_update(
            state,
            active_subtask,
            operand_rows,
            status="sufficient" if validation.get("status") == "ready" else "partial",
            summary=f"{len(operand_rows)} grounded semantic-program operand(s)",
            payload={
                "calculation_operands": operand_rows,
                "candidate_catalog_fingerprint": calculation_plan["candidate_catalog_fingerprint"],
                "candidate_count": len(catalog),
                "prompt_candidate_count": len(prompt_catalog_rows),
                "prompt_candidate_strategy": "atomic_evidence_bundle_option_v1",
                "prompt_candidate_payload_bytes": len(
                    prompt_catalog_json.encode("utf-8")
                ),
                "candidate_cohort_status": str(cohort_plan.get("status") or ""),
                "prompt_excerpt_strategy": "cell_local_fact_projection_v1",
                "candidate_stage_diagnostics": candidate_stage_diagnostics,
                "selected_candidate_ids": selected_candidate_ids,
                "semantic_status": str(validation.get("status") or ""),
                "missing_obligation_ids": list(
                    validation.get("missing_obligation_ids") or []
                ),
            },
            evidence_refs=selected_candidate_ids,
        )
        plan_update = self._calculation_plan_artifact_update(
            {**dict(state), **operand_update},
            calculation_plan,
        )
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
            **trace_update,
            "answer_obligations": obligations,
            "semantic_candidate_catalog": catalog,
            "semantic_program": program_data,
            "semantic_program_validation": validation,
            "semantic_compilation_envelope": compilation_envelope,
            "semantic_program_retry_count": retry_count,
            "missing_info": list(validation.get("missing_obligation_ids") or []),
            "planner_debug_trace": {
                **dict(state.get("planner_debug_trace") or {}),
                "program_compiler_invoked": bool(obligations),
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
            "tasks": list(plan_update["tasks"]),
            "artifacts": list(plan_update["artifacts"]),
        }

    def _compile_semantic_calculation_program(
        self,
        state: FinancialAgentState,
    ) -> Dict[str, Any]:
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
        global_cohort_plan = _semantic_candidate_cohorts(catalog, obligations)
        island_plan = build_semantic_compilation_islands(
            obligations,
            evidence_bundle_constraints=list(
                global_cohort_plan.get("evidence_bundle_constraints") or []
            ),
        )
        islands = [dict(item) for item in island_plan.get("islands") or []]
        global_block_reason = ""
        if len(islands) > MAX_SEMANTIC_COMPILATION_ISLANDS:
            global_block_reason = "semantic compilation island limit exceeded"
        elif global_cohort_plan.get("status") == "capacity_exceeded":
            global_block_reason = "semantic candidate cohort capacity exceeded"

        obligation_by_id = {
            str(item.get("obligation_id") or ""): item
            for item in obligations
        }
        island_results: List[Dict[str, Any]] = []
        total_retry_count = 0
        total_call_count = 0
        invocation_errors: List[str] = []
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
                    "missing_obligation_ids": island_ids,
                    "ambiguous_obligation_ids": [],
                    "rationale": blocked_reason,
                }
                validation = validate_semantic_calculation_program(
                    program=program,
                    obligations=island_obligations,
                    candidate_catalog=catalog,
                    query=query,
                    candidate_visibility=visibility,
                )
                envelope = CompilationEnvelopeV1.create(
                    visibility=visibility,
                    program=program,
                    validation=validation,
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

            compiled = self._compile_semantic_calculation_island(
                {
                    **dict(state),
                    "answer_obligations": island_obligations,
                    "semantic_candidate_catalog": catalog,
                    "semantic_source_candidates": source_candidates,
                    "semantic_candidate_catalog_prebuilt": True,
                    "tasks": [],
                    "artifacts": [],
                }
            )
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
                "missing_obligation_ids": list(
                    island_validation.get("missing_obligation_ids") or []
                ),
                "ambiguous_obligation_ids": list(
                    island_validation.get("ambiguous_obligation_ids") or []
                ),
            }
            call_count = 1 + retry_count if island_obligations else 0
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
            "missing_obligation_ids": missing_ids,
            "ambiguous_obligation_ids": ambiguous_ids,
            "rationale": " | ".join(
                str(dict(result.get("program") or {}).get("rationale") or "")
                for result in island_results
                if str(
                    dict(result.get("program") or {}).get("rationale") or ""
                )
            ),
        }

        selectable_by_owner: Dict[str, List[str]] = {}
        merged_bundle_constraints: List[Dict[str, Any]] = []
        merged_bundle_constraint_ids: set[str] = set()
        for result in island_results:
            envelope = result.get("envelope")
            if not isinstance(envelope, CompilationEnvelopeV1):
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
            obligations=obligations,
            candidate_catalog=catalog,
            query=query,
            candidate_visibility=merged_visibility,
        )
        compilation_envelope = CompilationEnvelopeV1.create(
            visibility=merged_visibility,
            program=merged_program,
            validation=validation,
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
        for candidate in selected_candidates:
            if str(candidate.get("kind") or "") != "numeric":
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
                    "coupling_keys": list(island.get("coupling_keys") or []),
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
                        if isinstance(envelope, CompilationEnvelopeV1)
                        else ""
                    ),
                    "prompt_bytes": int(result.get("prompt_bytes") or 0),
                    "accepted_program_bytes": len(program_bytes),
                    "accepted_program_fingerprint": (
                        envelope.program_fingerprint
                        if isinstance(envelope, CompilationEnvelopeV1)
                        else ""
                    ),
                }
            )
        candidate_stage_diagnostics = {
            **base_candidate_diagnostics,
            "schema": "semantic_candidate_stage_diagnostics_v6",
            "island_count": len(islands),
            "compiler_call_count": total_call_count,
            "compiler_retry_count": total_retry_count,
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
            "candidate_count": len(catalog),
            "prompt_candidate_count": len(prompt_visible_ids),
            "prompt_candidate_ids": prompt_visible_ids,
            "prompt_candidate_strategy": "compilation_islands_v2",
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
        active_subtask = dict(state.get("active_subtask") or {})
        operand_update = self._operand_set_artifact_update(
            state,
            active_subtask,
            operand_rows,
            status=(
                "sufficient"
                if validation.get("status") == "ready"
                else "partial"
            ),
            summary=f"{len(operand_rows)} grounded semantic-program operand(s)",
            payload={
                "calculation_operands": operand_rows,
                "candidate_catalog_fingerprint": calculation_plan[
                    "candidate_catalog_fingerprint"
                ],
                "candidate_stage_diagnostics": candidate_stage_diagnostics,
                "selected_candidate_ids": selected_candidate_ids,
                "semantic_status": str(validation.get("status") or ""),
            },
            evidence_refs=selected_candidate_ids,
        )
        plan_update = self._calculation_plan_artifact_update(
            {**dict(state), **operand_update},
            calculation_plan,
        )
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
            **trace_update,
            "answer_obligations": obligations,
            "semantic_candidate_catalog": catalog,
            "semantic_program": merged_program,
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
                "candidate_count": len(catalog),
                "prompt_candidate_count": len(prompt_visible_ids),
                "candidate_cohort_status": str(
                    global_cohort_plan.get("status") or ""
                ),
                "prompt_candidate_payload_bytes": calculation_plan[
                    "prompt_candidate_payload_bytes"
                ],
                "candidate_stage_diagnostics_schema": (
                    "semantic_candidate_stage_diagnostics_v6"
                ),
                "selected_candidate_count": len(selected_candidate_ids),
                "program_validation_status": str(
                    validation.get("status") or ""
                ),
                "program_validation_errors": list(
                    validation.get("errors") or []
                ),
                "program_invocation_errors": invocation_errors,
                "compilation_islands": island_diagnostics,
            },
            "tasks": list(plan_update["tasks"]),
            "artifacts": list(plan_update["artifacts"]),
        }

    def _execute_semantic_calculation_program(
        self,
        state: FinancialAgentState,
    ) -> Dict[str, Any]:
        obligations = [dict(item) for item in (state.get("answer_obligations") or [])]
        catalog = [dict(item) for item in (state.get("semantic_candidate_catalog") or [])]
        current_trace = resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        calculation_plan = dict(current_trace.get("calculation_plan") or {})
        compilation_envelope = state.get("semantic_compilation_envelope")
        execution = execute_semantic_calculation_program(
            program=dict(state.get("semantic_program") or {}),
            obligations=obligations,
            candidate_catalog=catalog,
            query=str(state.get("query") or ""),
            compilation_envelope=(
                compilation_envelope
                if isinstance(compilation_envelope, CompilationEnvelopeV1)
                else None
            ),
            require_compilation_envelope=True,
        )
        calculation_operands = list(execution.get("calculation_operands") or [])
        calculation_result = dict(execution.get("calculation_result") or {})
        derived_operation_family = str(
            dict(calculation_result.get("derived_metrics") or {}).get(
                "operation_family"
            )
            or "formula"
        )
        calculation_plan = {
            **calculation_plan,
            "operation_family": derived_operation_family,
        }
        calculation_result = {
            **calculation_result,
            "operation_family": derived_operation_family,
        }
        selected_candidate_ids = list(execution.get("selected_candidate_ids") or [])
        evidence_items = self._semantic_program_evidence_items(catalog, selected_candidate_ids)

        output_rows: List[Dict[str, Any]] = []
        for output in execution.get("outputs") or []:
            obligation_id = str(output.get("obligation_id") or "")
            answer_text = (
                str(output.get("text") or "")
                if str(output.get("kind") or "") == "narrative"
                else f"{str(output.get('label') or obligation_id)}: {str(output.get('rendered_value') or '')}"
            )
            output_rows.append(
                {
                    "task_id": f"task_1:{obligation_id}",
                    "metric_family": "semantic_program",
                    "metric_label": str(output.get("label") or obligation_id),
                    "operation_family": str(output.get("operation_family") or "formula"),
                    "status": str(output.get("status") or "ok"),
                    "answer": _normalise_spaces(answer_text),
                    "calculation_result": {
                        "status": str(output.get("status") or "ok"),
                        "operation_family": str(
                            output.get("operation_family") or "formula"
                        ),
                        "result_value": output.get("normalized_value"),
                        "result_unit": str(output.get("result_unit") or ""),
                        "rendered_value": str(output.get("rendered_value") or ""),
                        "answer_slots": (
                            {
                                "operation_family": (
                                    "lookup"
                                    if str(output.get("operation_family") or "")
                                    == "lookup"
                                    else "single_value"
                                ),
                                "metric_label": str(output.get("label") or obligation_id),
                                "primary_value": dict(output.get("answer_slot") or {}),
                            }
                            if output.get("answer_slot")
                            else {}
                        ),
                        "derived_metrics": {
                            "operation_family": str(
                                output.get("operation_family") or "formula"
                            )
                        },
                        "source_row_ids": list(output.get("source_row_ids") or []),
                    },
                    "source_row_ids": list(output.get("source_row_ids") or []),
                    "source_evidence_ids": list(output.get("candidate_ids") or []),
                }
            )

        answer = _normalise_spaces(str(execution.get("answer") or ""))
        structured_result = {
            "status": str(execution.get("status") or "incomplete"),
            "answer": answer,
            "final_answer": answer,
            "subtask_results": output_rows,
            "answer_obligations": obligations,
            "missing_obligation_ids": list(execution.get("missing_obligation_ids") or []),
            "resolved_calculation_trace": {
                "calculation_operands": calculation_operands,
                "calculation_plan": calculation_plan,
                "calculation_result": calculation_result,
            },
        }
        active_subtask = dict(state.get("active_subtask") or {})
        task_id = str(active_subtask.get("task_id") or "task_1")
        result_update = calculation_result_artifact_update(
            tasks=list(state.get("tasks") or []),
            artifacts=list(state.get("artifacts") or []),
            task_id=task_id,
            task_label=str(active_subtask.get("metric_label") or task_id),
            query=self._calc_query(state),
            metric_family="semantic_program",
            calculation_result=calculation_result,
            evidence_refs=selected_candidate_ids,
        )
        trace_update = runtime_trace_state_update(
            state,
            calculation_operands=calculation_operands,
            calculation_plan=calculation_plan,
            calculation_result=calculation_result,
        )
        logger.info(
            "[semantic_program] execute status=%s outputs=%s missing=%s",
            execution.get("status"), len(output_rows), len(execution.get("missing_obligation_ids") or []),
        )
        return {
            **trace_update,
            "answer": answer,
            "compressed_answer": answer,
            "draft_points": [answer] if answer else [],
            "structured_result": structured_result,
            "subtask_results": output_rows,
            "subtask_loop_complete": True,
            "missing_info": list(execution.get("missing_obligation_ids") or []),
            "evidence_items": evidence_items,
            "runtime_evidence": evidence_items,
            "selected_claim_ids": selected_candidate_ids,
            "kept_claim_ids": selected_candidate_ids,
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "evidence_bullets": [
                f"- {item.get('source_anchor', '?')} {item.get('claim', '')} (direct)"
                for item in evidence_items
            ],
            "evidence_status": "sufficient" if execution.get("status") == "ok" else "sparse",
            "tasks": list(result_update.get("tasks") or []),
            "artifacts": list(result_update.get("artifacts") or []),
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
