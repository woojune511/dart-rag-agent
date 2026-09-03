"""Audit candidate-ranking ambiguity from saved calculation plans.

The command is read-only unless ``--output`` is supplied.  It never initializes
an embedding or language-model provider.  Current diagnostics expose the full
eligible-catalog rank summary.  For immutable v6 artifacts, the command first
rebuilds the catalog from the saved source window and structure-graph store and
uses it only when every saved fingerprint matches.  Otherwise it falls back to
the saved, admitted cohort candidates and labels that narrower population.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.agent.financial_calculation_execution import (
    semantic_candidate_applicability,
)
from src.agent.financial_candidate_matching import (
    build_candidate_matches,
    rank_candidate_matches,
    summarize_candidate_match_ranking,
)
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    build_semantic_source_candidates,
    semantic_candidate_catalog_fingerprint,
    semantic_candidate_id_fingerprint,
)
from src.storage.graph_persistence import load_structure_graph
from src.storage.metadata_payloads import (
    load_table_payloads,
    metadata_with_table_payload,
)


SUPPORTED_DIAGNOSTIC_SCHEMAS = frozenset(
    {
        "semantic_candidate_stage_diagnostics_v6",
        "semantic_candidate_stage_diagnostics_v7",
        "semantic_candidate_stage_diagnostics_v8",
    }
)


@dataclass(frozen=True, slots=True)
class _StoredDocument:
    page_content: str
    metadata: dict[str, Any]


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _fingerprint(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _result_files(paths: Sequence[Path]) -> list[Path]:
    files: list[Path] = []
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_file():
            files.append(path)
            continue
        if not path.is_dir():
            raise FileNotFoundError(path)
        files.extend(sorted(path.rglob("results.json")))
    return list(dict.fromkeys(files))


def _iter_calculation_plans(
    value: Any,
    *,
    question_id: str = "",
    question: str = "",
    store: Mapping[str, Any] | None = None,
) -> Iterable[tuple[str, str, Mapping[str, Any], Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        local_question_id = question_id
        local_question = question
        local_store = dict(store or {})
        if isinstance(value.get("store"), Mapping):
            local_store = dict(value.get("store") or {})
        if value.get("question") and value.get("id"):
            local_question_id = str(value.get("id") or "")
            local_question = str(value.get("question") or "")
        diagnostics = value.get("candidate_stage_diagnostics")
        if (
            isinstance(diagnostics, Mapping)
            and str(diagnostics.get("schema") or "")
            in SUPPORTED_DIAGNOSTIC_SCHEMAS
            and isinstance(value.get("candidate_cohorts"), Sequence)
        ):
            yield local_question_id, local_question, value, local_store
        for child in value.values():
            yield from _iter_calculation_plans(
                child,
                question_id=local_question_id,
                question=local_question,
                store=local_store,
            )
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        for child in value:
            yield from _iter_calculation_plans(
                child,
                question_id=question_id,
                question=question,
                store=store,
            )


def load_saved_plans(
    paths: Sequence[Path],
    *,
    question_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Load and de-duplicate calculation plans from result bundles."""

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in _result_files(paths):
        payload = _read_json(path)
        for question_id, question, plan, store in _iter_calculation_plans(payload):
            if question_ids and question_id not in question_ids:
                continue
            diagnostics = dict(plan.get("candidate_stage_diagnostics") or {})
            key = (question_id, _fingerprint(diagnostics))
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "question_id": question_id or "unknown",
                    "question": question,
                    "source_file": path.as_posix(),
                    "plan": dict(plan),
                    "store": dict(store),
                }
            )
    return sorted(
        rows,
        key=lambda row: (row["question_id"], row["source_file"]),
    )


def _source_anchor(metadata: Mapping[str, Any]) -> str:
    relation = str(metadata.get("graph_relation") or "").strip()
    relation_suffix = f" | {relation}" if relation else ""
    return (
        f"[{metadata.get('company', '?')} | {metadata.get('year', '?')} | "
        f"{metadata.get('section_path', metadata.get('section', '?'))}"
        f"{relation_suffix}]"
    )


def _verified_catalog_replay(
    plan: Mapping[str, Any],
    store: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rebuild a saved catalog from read-only structure artifacts."""

    persist_directory = str(store.get("persist_directory") or "").strip()
    if not persist_directory:
        return [], {
            "status": "unavailable",
            "source": "provider_free_structure_graph_replay",
            "reason": "store_path_not_saved",
        }

    store_path = Path(persist_directory)
    graph_path = store_path / "document_structure_graph.json"
    payload_path = store_path / "table_payloads.json"
    if not graph_path.is_file():
        return [], {
            "status": "unavailable",
            "source": "provider_free_structure_graph_replay",
            "reason": "structure_graph_not_found",
        }

    diagnostics = dict(plan.get("candidate_stage_diagnostics") or {})
    source_window = dict(diagnostics.get("source_window") or {})
    retrieved_ids = [
        str(item).strip()
        for item in (source_window.get("retrieved_source_ids") or [])
        if str(item or "").strip()
    ]
    seed_ids = [
        str(item).strip()
        for item in (source_window.get("seed_source_ids") or [])
        if str(item or "").strip()
    ]
    if not retrieved_ids and not seed_ids:
        return [], {
            "status": "unavailable",
            "source": "provider_free_structure_graph_replay",
            "reason": "source_window_not_saved",
        }

    graph = load_structure_graph(graph_path)
    nodes = dict(graph.get("nodes") or {})
    table_payloads = load_table_payloads(payload_path)

    def documents(source_ids: Sequence[str]) -> list[tuple[_StoredDocument, float]]:
        rows: list[tuple[_StoredDocument, float]] = []
        for source_id in source_ids:
            node = dict(nodes.get(source_id) or {})
            if not node:
                continue
            metadata = metadata_with_table_payload(
                dict(node.get("metadata") or {}),
                table_payloads,
            )
            rows.append(
                (
                    _StoredDocument(
                        page_content=str(node.get("text") or ""),
                        metadata=metadata,
                    ),
                    0.0,
                )
            )
        return rows

    all_source_ids = list(dict.fromkeys([*retrieved_ids, *seed_ids]))
    missing_source_ids = [
        source_id for source_id in all_source_ids if source_id not in nodes
    ]
    if missing_source_ids:
        return [], {
            "status": "mismatch",
            "source": "provider_free_structure_graph_replay",
            "reason": "source_ids_not_found",
            "missing_source_id_count": len(missing_source_ids),
        }

    source_candidates = build_semantic_source_candidates(
        {
            "evidence_items": [],
            "retrieved_docs": documents(retrieved_ids),
            "seed_retrieved_docs": documents(seed_ids),
        },
        source_anchor_builder=_source_anchor,
    )
    catalog = build_semantic_candidate_catalog(source_candidates)
    observed = {
        "source_candidate_count": len(source_candidates),
        "source_candidate_id_fingerprint": semantic_candidate_id_fingerprint(
            [item.get("candidate_id") for item in source_candidates]
        ),
        "catalog_candidate_count": len(catalog),
        "catalog_candidate_id_fingerprint": semantic_candidate_id_fingerprint(
            [item.get("candidate_id") for item in catalog]
        ),
        "catalog_fingerprint": semantic_candidate_catalog_fingerprint(catalog),
    }
    expected = {
        "source_candidate_count": int(
            diagnostics.get("source_candidate_count") or 0
        ),
        "source_candidate_id_fingerprint": str(
            diagnostics.get("source_candidate_id_fingerprint") or ""
        ),
        "catalog_candidate_count": int(
            diagnostics.get("catalog_candidate_count") or 0
        ),
        "catalog_candidate_id_fingerprint": str(
            diagnostics.get("catalog_candidate_id_fingerprint") or ""
        ),
        "catalog_fingerprint": str(plan.get("candidate_catalog_fingerprint") or ""),
    }
    mismatch_fields = [
        field
        for field, expected_value in expected.items()
        if expected_value != observed[field]
    ]
    projection = {
        "status": "verified" if not mismatch_fields else "mismatch",
        "source": "provider_free_structure_graph_replay",
        "reason": "" if not mismatch_fields else "saved_fingerprint_mismatch",
        "source_candidate_count": observed["source_candidate_count"],
        "catalog_candidate_count": observed["catalog_candidate_count"],
        "mismatch_fields": mismatch_fields,
    }
    return (catalog if not mismatch_fields else []), projection


def _owner_for_cohort(
    obligations: Sequence[Mapping[str, Any]],
    cohort: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    parent_id = str(cohort.get("parent_obligation_id") or "")
    owner_id = str(cohort.get("owner_id") or "")
    parent = next(
        (
            dict(obligation)
            for obligation in obligations
            if str(obligation.get("obligation_id") or "") == parent_id
        ),
        {},
    )
    if str(cohort.get("owner_type") or "") != "requirement":
        return parent, None
    requirement = next(
        (
            dict(item)
            for item in (parent.get("evidence_requirements") or [])
            if isinstance(item, Mapping)
            and str(item.get("requirement_id") or "") == owner_id
        ),
        {},
    )
    if requirement:
        requirement["scope"] = {
            **dict(parent.get("scope") or {}),
            **dict(requirement.get("scope") or {}),
        }
    return requirement, parent or None


def replay_verified_candidate_catalog(
    plan: Mapping[str, Any],
    store: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Public read-only catalog replay shared by ambiguity tooling."""

    return _verified_catalog_replay(plan, store)


def resolve_saved_candidate_owner(
    obligations: Sequence[Mapping[str, Any]],
    cohort: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Resolve a saved cohort owner without changing its inherited scope."""

    return _owner_for_cohort(obligations, cohort)


def _reproject_full_catalog_ranking(
    plan: Mapping[str, Any],
    cohort: Mapping[str, Any],
    catalog: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, int], list[str]]:
    obligations = [
        dict(item)
        for item in (plan.get("answer_obligations") or [])
        if isinstance(item, Mapping)
    ]
    owner, parent_owner = _owner_for_cohort(obligations, cohort)
    if not owner:
        return (
            {
                "schema": "candidate_ranking_diagnostics_v1",
                "status": "unavailable",
                "population": "eligible_catalog",
                "source": "provider_free_structure_graph_replay",
                "reason": "owner_not_saved",
            },
            {},
            [],
        )

    candidate_kind = str(cohort.get("candidate_kind") or "")
    allowed_kinds = (
        {"numeric", "narrative"}
        if candidate_kind == "evidence"
        else {candidate_kind}
    )
    candidates = [
        dict(candidate)
        for candidate in catalog
        if isinstance(candidate, Mapping)
        and str(candidate.get("candidate_id") or "").strip()
    ]
    base_applicability_by_id = {
        str(candidate.get("candidate_id") or ""): (
            semantic_candidate_applicability(candidate, owner)
        )
        for candidate in candidates
    }
    matches = build_candidate_matches(
        candidates,
        owner=owner,
        parent_owner=parent_owner,
        base_applicability_by_id=base_applicability_by_id,
    )
    ranked_candidates = rank_candidate_matches(
        candidates,
        matches,
        allowed_kinds=tuple(sorted(allowed_kinds)),
        limit=max(1, int(cohort.get("limit") or len(candidates))),
    )
    candidate_by_id = {
        str(candidate.get("candidate_id") or ""): candidate
        for candidate in candidates
    }
    ids_by_state: dict[str, list[str]] = {
        "compatible": [],
        "unknown_only": [],
        "explicit_conflict": [],
    }
    for candidate_id, match in matches.items():
        if (
            str(candidate_by_id[candidate_id].get("kind") or "")
            not in allowed_kinds
        ):
            continue
        ids_by_state[match.state].append(candidate_id)

    ranking = summarize_candidate_match_ranking(
        matches,
        [*ids_by_state["compatible"], *ids_by_state["unknown_only"]],
    )
    ranking.update(
        {
            "status": "available",
            "population": "eligible_catalog",
            "source": "provider_free_structure_graph_replay",
        }
    )
    return (
        ranking,
        {
            state: len(candidate_ids)
            for state, candidate_ids in ids_by_state.items()
        },
        [
            str(candidate.get("candidate_id") or "")
            for candidate in ranked_candidates
            if str(candidate.get("candidate_id") or "")
        ],
    )


def _reproject_saved_cohort_ranking(
    plan: Mapping[str, Any],
    cohort: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = [
        dict(candidate)
        for candidate in (plan.get("proposed_candidates") or [])
        if isinstance(candidate, Mapping)
        and str(candidate.get("candidate_id") or "")
    ]
    candidate_by_id = {
        str(candidate.get("candidate_id") or ""): candidate
        for candidate in candidates
    }
    candidate_ids = [
        str(candidate_id)
        for candidate_id in (cohort.get("candidate_ids") or [])
        if str(candidate_id or "").strip()
    ]
    missing_ids = [
        candidate_id
        for candidate_id in candidate_ids
        if candidate_id not in candidate_by_id
    ]
    obligations = [
        dict(item)
        for item in (plan.get("answer_obligations") or [])
        if isinstance(item, Mapping)
    ]
    owner, parent_owner = _owner_for_cohort(obligations, cohort)
    if not owner or not candidates:
        return {
            "schema": "candidate_ranking_diagnostics_v1",
            "status": "unavailable",
            "population": "admitted_cohort",
            "source": "provider_free_saved_plan_reprojection",
            "reason": (
                "owner_not_saved" if not owner else "prompt_candidates_not_saved"
            ),
        }

    base_applicability_by_id = {
        candidate_id: semantic_candidate_applicability(candidate, owner)
        for candidate_id, candidate in candidate_by_id.items()
    }
    matches = build_candidate_matches(
        candidates,
        owner=owner,
        parent_owner=parent_owner,
        base_applicability_by_id=base_applicability_by_id,
    )
    summary = summarize_candidate_match_ranking(matches, candidate_ids)
    summary.update(
        {
            "status": "partial" if missing_ids else "available",
            "population": "admitted_cohort",
            "source": "provider_free_saved_plan_reprojection",
            "saved_candidate_count": len(candidate_ids),
            "resolved_candidate_count": len(candidate_ids) - len(missing_ids),
            "missing_candidate_count": len(missing_ids),
        }
    )
    return summary


def _unknown_only_projection(match_counts: Mapping[str, Any]) -> dict[str, Any]:
    compatible = int(match_counts.get("compatible") or 0)
    unknown_only = int(match_counts.get("unknown_only") or 0)
    denominator = compatible + unknown_only
    return {
        "compatible_count": compatible,
        "unknown_only_count": unknown_only,
        "explicit_conflict_count": int(
            match_counts.get("explicit_conflict") or 0
        ),
        "denominator": denominator,
        "share": unknown_only / denominator if denominator else None,
    }


def _cohort_rows(
    question_id: str,
    plan: Mapping[str, Any],
    *,
    replayed_catalog: Sequence[Mapping[str, Any]] = (),
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    diagnostics = dict(plan.get("candidate_stage_diagnostics") or {})
    diagnostic_cohorts = {
        str(item.get("cohort_id") or ""): dict(item)
        for item in (diagnostics.get("cohorts") or [])
        if isinstance(item, Mapping) and str(item.get("cohort_id") or "")
    }
    rows: list[dict[str, Any]] = []
    positions_by_owner: dict[str, dict[str, int]] = {}
    for raw_cohort in plan.get("candidate_cohorts") or []:
        if not isinstance(raw_cohort, Mapping):
            continue
        cohort = dict(raw_cohort)
        cohort_id = str(cohort.get("cohort_id") or "")
        diagnostic_cohort = diagnostic_cohorts.get(cohort_id, {})
        ranking = dict(
            diagnostic_cohort.get("ranking_diagnostics")
            or cohort.get("ranking_diagnostics")
            or {}
        )
        match_counts = dict(
            diagnostic_cohort.get("match_counts")
            or cohort.get("match_counts")
            or {}
        )
        if not ranking:
            if replayed_catalog:
                ranking, replayed_match_counts, ranked_candidate_ids = (
                    _reproject_full_catalog_ranking(
                        plan,
                        cohort,
                        replayed_catalog,
                    )
                )
                if replayed_match_counts:
                    match_counts = replayed_match_counts
                if str(cohort.get("owner_type") or "") == "obligation":
                    positions_by_owner[str(cohort.get("owner_id") or "")] = {
                        candidate_id: index
                        for index, candidate_id in enumerate(
                            ranked_candidate_ids
                        )
                    }
            else:
                ranking = _reproject_saved_cohort_ranking(plan, cohort)
        else:
            ranking.setdefault("status", "available")
        source_group = dict(
            diagnostic_cohort.get("source_defined_group_selection")
            or cohort.get("source_defined_group_selection")
            or {}
        )
        rows.append(
            {
                "question_id": question_id,
                "cohort_id": cohort_id,
                "owner_id": str(cohort.get("owner_id") or ""),
                "owner_type": str(cohort.get("owner_type") or ""),
                "candidate_kind": str(cohort.get("candidate_kind") or ""),
                "admitted_candidate_count": len(
                    cohort.get("candidate_ids") or []
                ),
                "match_counts": match_counts,
                "unknown_only": _unknown_only_projection(match_counts),
                "ranking": ranking,
                "source_defined_group": {
                    "selection_mode": str(
                        source_group.get("selection_mode") or ""
                    ),
                    "complete_option_count": (
                        int(source_group.get("complete_option_count") or 0)
                        if source_group
                        else None
                    ),
                    "selected_physical_table_id": str(
                        source_group.get("physical_table_id") or ""
                    ),
                    "selected_physical_row_id": str(
                        source_group.get("physical_row_id") or ""
                    ),
                },
            }
        )
    return rows, positions_by_owner


def _bundle_rows(
    question_id: str,
    plan: Mapping[str, Any],
    *,
    positions_by_owner: Mapping[str, Mapping[str, int]] | None = None,
) -> list[dict[str, Any]]:
    diagnostics = dict(plan.get("candidate_stage_diagnostics") or {})
    selections = (
        diagnostics.get("evidence_bundle_option_selections")
        or plan.get("evidence_bundle_option_selections")
        or []
    )
    rows: list[dict[str, Any]] = []
    for raw_selection in selections:
        if not isinstance(raw_selection, Mapping):
            continue
        selection = dict(raw_selection)
        options = [
            dict(item)
            for item in (selection.get("ranked_options") or [])
            if isinstance(item, Mapping)
        ]
        option_diagnostics = [
            dict(item)
            for item in (selection.get("ranked_option_diagnostics") or [])
            if isinstance(item, Mapping)
        ]
        margin_source = (
            "persisted_runtime_diagnostics"
            if option_diagnostics
            else "saved_selection_only"
        )
        if (
            not option_diagnostics
            and len(options) > 1
            and positions_by_owner
        ):
            for option in options:
                candidate_ids_by_owner = dict(
                    option.get("candidate_ids_by_owner") or {}
                )
                owner_positions = {
                    str(owner_id): min(
                        (
                            int(
                                positions_by_owner.get(
                                    str(owner_id), {}
                                ).get(str(candidate_id), 10**6)
                            )
                            for candidate_id in (candidate_ids or [])
                        ),
                        default=10**6,
                    )
                    for owner_id, candidate_ids in (
                        candidate_ids_by_owner.items()
                    )
                }
                option_diagnostics.append(
                    {
                        "option_id": str(option.get("option_id") or ""),
                        "position_sum": sum(owner_positions.values()),
                        "worst_position": max(
                            owner_positions.values(),
                            default=10**6,
                        ),
                    }
                )
            margin_source = "provider_free_structure_graph_replay"
        top = option_diagnostics[0] if option_diagnostics else {}
        runner_up = option_diagnostics[1] if len(option_diagnostics) >= 2 else {}
        if runner_up:
            position_sum_delta = int(runner_up.get("position_sum") or 0) - int(
                top.get("position_sum") or 0
            )
            worst_position_delta = int(
                runner_up.get("worst_position") or 0
            ) - int(top.get("worst_position") or 0)
            margin_status = (
                "identity_tiebreak"
                if position_sum_delta == 0 and worst_position_delta == 0
                else "separated"
            )
        else:
            position_sum_delta = None
            worst_position_delta = None
            margin_status = (
                "single_option" if len(options) <= 1 else "unavailable_legacy"
            )
        rows.append(
            {
                "question_id": question_id,
                "constraint_id": str(selection.get("constraint_id") or ""),
                "selected_option_id": str(
                    selection.get("selected_option_id") or ""
                ),
                "selected_physical_table_id": str(
                    selection.get("selected_physical_table_id")
                    or (options[0].get("physical_table_id") if options else "")
                    or ""
                ),
                "selected_physical_row_id": str(
                    selection.get("selected_physical_row_id")
                    or (options[0].get("physical_row_id") if options else "")
                    or ""
                ),
                "complete_option_count": int(
                    selection.get("complete_option_count") or len(options)
                ),
                "top_two_margin": {
                    "status": margin_status,
                    "source": margin_source,
                    "position_sum_delta": position_sum_delta,
                    "worst_position_delta": worst_position_delta,
                },
            }
        )
    return rows


def _failure_class(island: Mapping[str, Any]) -> str:
    if str(island.get("blocked_reason") or ""):
        return "blocked"
    if island.get("preflight_errors"):
        return "preflight_invalid"
    if int(island.get("retry_count") or 0):
        return (
            "recovered_after_retry"
            if str(island.get("accepted_program_fingerprint") or "")
            else "retry_incomplete"
        )
    if int(island.get("call_count") or 0) == 0:
        return "not_invoked"
    return "none"


def _island_rows(question_id: str, plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    diagnostics = dict(plan.get("candidate_stage_diagnostics") or {})
    return [
        {
            "question_id": question_id,
            "island_id": str(island.get("island_id") or ""),
            "obligation_ids": list(island.get("obligation_ids") or []),
            "call_count": int(island.get("call_count") or 0),
            "retry_count": int(island.get("retry_count") or 0),
            "prompt_bytes": int(island.get("prompt_bytes") or 0),
            "failure_class": _failure_class(island),
        }
        for island in (diagnostics.get("islands") or [])
        if isinstance(island, Mapping)
    ]


def build_candidate_ambiguity_audit(
    saved_plans: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Project a deterministic ambiguity report from saved calculation plans."""

    questions: list[dict[str, Any]] = []
    all_cohorts: list[dict[str, Any]] = []
    all_bundles: list[dict[str, Any]] = []
    all_islands: list[dict[str, Any]] = []
    diagnostic_schemas: Counter[str] = Counter()
    catalog_replay_statuses: Counter[str] = Counter()
    for saved in saved_plans:
        question_id = str(saved.get("question_id") or "unknown")
        plan = dict(saved.get("plan") or {})
        diagnostics = dict(plan.get("candidate_stage_diagnostics") or {})
        diagnostic_schema = str(diagnostics.get("schema") or "")
        diagnostic_schemas[diagnostic_schema] += 1
        diagnostic_cohorts = [
            dict(item)
            for item in (diagnostics.get("cohorts") or [])
            if isinstance(item, Mapping)
        ]
        has_full_catalog_ranking = bool(diagnostic_cohorts) and all(
            str(
                dict(item.get("ranking_diagnostics") or {}).get("population")
                or ""
            )
            == "eligible_catalog"
            for item in diagnostic_cohorts
        )
        if has_full_catalog_ranking:
            replayed_catalog: list[dict[str, Any]] = []
            catalog_replay = {
                "status": "not_needed",
                "source": "persisted_runtime_diagnostics",
                "reason": "eligible_catalog_ranking_saved",
            }
        else:
            replayed_catalog, catalog_replay = _verified_catalog_replay(
                plan,
                dict(saved.get("store") or {}),
            )
        replay_status = str(catalog_replay.get("status") or "unknown")
        catalog_replay_statuses[replay_status] += 1
        cohorts, positions_by_owner = _cohort_rows(
            question_id,
            plan,
            replayed_catalog=replayed_catalog,
        )
        bundles = _bundle_rows(
            question_id,
            plan,
            positions_by_owner=positions_by_owner,
        )
        islands = _island_rows(question_id, plan)
        all_cohorts.extend(cohorts)
        all_bundles.extend(bundles)
        all_islands.extend(islands)
        questions.append(
            {
                "question_id": question_id,
                "source_file": str(saved.get("source_file") or ""),
                "diagnostic_schema": diagnostic_schema,
                "catalog_candidate_count": int(
                    diagnostics.get("catalog_candidate_count") or 0
                ),
                "prompt_candidate_count": int(
                    diagnostics.get("prompt_candidate_count") or 0
                ),
                "catalog_replay": catalog_replay,
                "cohorts": cohorts,
                "complete_row_bundles": bundles,
                "islands": islands,
            }
        )

    def full_catalog_ranking_available(row: Mapping[str, Any]) -> bool:
        ranking = dict(row.get("ranking") or {})
        return (
            ranking.get("status") == "available"
            and ranking.get("population") == "eligible_catalog"
            and int(ranking.get("unresolved_rank_vector_count") or 0) == 0
        )

    eligible_ranking_count = sum(
        1
        for row in all_cohorts
        if full_catalog_ranking_available(row)
    )
    reprojected_ranking_count = sum(
        1
        for row in all_cohorts
        if row["ranking"].get("source")
        == "provider_free_saved_plan_reprojection"
    )
    ambiguous_top_tier_count = sum(
        1
        for row in all_cohorts
        if int(row["ranking"].get("top_tier_candidate_count") or 0) > 1
    )
    unknown_numerator = sum(
        int(row["unknown_only"].get("unknown_only_count") or 0)
        for row in all_cohorts
    )
    unknown_denominator = sum(
        int(row["unknown_only"].get("denominator") or 0)
        for row in all_cohorts
    )
    failure_classes = Counter(row["failure_class"] for row in all_islands)
    return {
        "schema": "candidate_ambiguity_audit_v1",
        "mode": "provider_free_saved_artifact_projection",
        "question_count": len(questions),
        "diagnostic_schema_counts": dict(sorted(diagnostic_schemas.items())),
        "catalog_replay_status_counts": dict(
            sorted(catalog_replay_statuses.items())
        ),
        "summary": {
            "cohort_count": len(all_cohorts),
            "eligible_catalog_ranking_count": eligible_ranking_count,
            "admitted_cohort_reprojection_count": reprojected_ranking_count,
            "ambiguous_top_tier_count": ambiguous_top_tier_count,
            "unknown_only_numerator": unknown_numerator,
            "unknown_only_denominator": unknown_denominator,
            "unknown_only_share": (
                unknown_numerator / unknown_denominator
                if unknown_denominator
                else None
            ),
            "complete_row_bundle_count": len(all_bundles),
            "multi_option_bundle_count": sum(
                1 for row in all_bundles if row["complete_option_count"] > 1
            ),
            "prompt_bytes": sum(row["prompt_bytes"] for row in all_islands),
            "compiler_retry_count": sum(row["retry_count"] for row in all_islands),
            "failure_class_counts": dict(sorted(failure_classes.items())),
            "full_catalog_ranking_available": (
                bool(all_cohorts) and eligible_ranking_count == len(all_cohorts)
            ),
        },
        "questions": questions,
    }


def render_markdown(audit: Mapping[str, Any]) -> str:
    summary = dict(audit.get("summary") or {})
    unknown_share = summary.get("unknown_only_share")
    lines = [
        "# Candidate Ambiguity Audit",
        "",
        f"- Mode: `{audit.get('mode')}`",
        f"- Questions: {audit.get('question_count', 0)}",
        f"- Cohorts: {summary.get('cohort_count', 0)}",
        "- Catalog replay statuses: "
        f"`{json.dumps(audit.get('catalog_replay_status_counts') or {}, sort_keys=True)}`",
        "- Full-catalog ranking available: "
        f"`{str(bool(summary.get('full_catalog_ranking_available'))).lower()}`",
        f"- Ambiguous top tiers: {summary.get('ambiguous_top_tier_count', 0)}",
        "- Unknown-only share: "
        + (
            f"{unknown_share:.3f}"
            if isinstance(unknown_share, (int, float))
            else "-"
        ),
        f"- Multi-option row bundles: {summary.get('multi_option_bundle_count', 0)}",
        f"- Prompt bytes: {summary.get('prompt_bytes', 0)}",
        f"- Compiler retries: {summary.get('compiler_retry_count', 0)}",
        "",
        "| Question | Cohort | Population | Top two | Top tier | Unknown-only | First differing factor |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for question in audit.get("questions") or []:
        for cohort in question.get("cohorts") or []:
            ranking = dict(cohort.get("ranking") or {})
            unknown = dict(cohort.get("unknown_only") or {})
            share = unknown.get("share")
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{question.get('question_id')}`",
                        f"`{cohort.get('cohort_id')}`",
                        f"`{ranking.get('population', 'unavailable')}`",
                        f"`{ranking.get('top_two_relation', 'unavailable')}`",
                        str(ranking.get("top_tier_candidate_count", "-")),
                        f"{share:.3f}" if isinstance(share, (int, float)) else "-",
                        f"`{ranking.get('first_differing_factor') or '-'}`",
                    ]
                )
                + " |"
            )
    bundle_rows = [
        bundle
        for question in (audit.get("questions") or [])
        for bundle in (question.get("complete_row_bundles") or [])
    ]
    if bundle_rows:
        lines.extend(
            [
                "",
                "## Complete row bundles",
                "",
                "| Question | Constraint | Options | Selected table | Selected row | Margin |",
                "| --- | --- | ---: | --- | --- | --- |",
            ]
        )
        for bundle in bundle_rows:
            margin = dict(bundle.get("top_two_margin") or {})
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{bundle.get('question_id')}`",
                        f"`{bundle.get('constraint_id')}`",
                        str(bundle.get("complete_option_count", 0)),
                        f"`{bundle.get('selected_physical_table_id') or '-'}`",
                        f"`{bundle.get('selected_physical_row_id') or '-'}`",
                        f"`{margin.get('status') or '-'}`",
                    ]
                )
                + " |"
            )
    island_rows = [
        island
        for question in (audit.get("questions") or [])
        for island in (question.get("islands") or [])
    ]
    if island_rows:
        lines.extend(
            [
                "",
                "## Compilation islands",
                "",
                "| Question | Island | Prompt bytes | Calls | Retries | Failure class |",
                "| --- | --- | ---: | ---: | ---: | --- |",
            ]
        )
        for island in island_rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{island.get('question_id')}`",
                        f"`{island.get('island_id')}`",
                        str(island.get("prompt_bytes", 0)),
                        str(island.get("call_count", 0)),
                        str(island.get("retry_count", 0)),
                        f"`{island.get('failure_class') or '-'}`",
                    ]
                )
                + " |"
            )
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Saved results.json files or directories containing them.",
    )
    parser.add_argument(
        "--question-id",
        action="append",
        default=[],
        help="Question id to include. May be passed multiple times.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plans = load_saved_plans(
        args.paths,
        question_ids=set(args.question_id) if args.question_id else None,
    )
    if not plans:
        raise SystemExit("No supported saved calculation plans were found.")
    audit = build_candidate_ambiguity_audit(plans)
    rendered = (
        render_markdown(audit)
        if args.format == "markdown"
        else json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
