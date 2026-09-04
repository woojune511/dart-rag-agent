"""Export strongest-factor candidate ties as a reviewable labeling template.

The exporter is provider-free and read-only unless ``--output`` is supplied.
It rebuilds each saved catalog from immutable structure artifacts, verifies the
saved fingerprints, and exports only the exact top factor tier for each owner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from src.agent.financial_calculation_execution import (
    semantic_candidate_applicability,
)
from src.agent.financial_candidate_matching import (
    build_candidate_matches,
    candidate_cell_local_source_text,
    project_candidate_match,
    rank_candidate_matches,
    resolve_owner_target,
    summarize_candidate_match_ranking,
)
from src.agent.financial_candidate_tiebreaker import (
    SEMANTIC_TIE_BREAK_PAIR_SCHEMA,
    SemanticTieBreakPairV5,
    semantic_tie_break_cohort_eligibility,
)
from src.config.retrieval_policy import CALCULATION_PROMPT_POLICY
from src.ops.audit_candidate_ambiguity import (
    load_saved_plans,
    replay_verified_candidate_catalog,
    resolve_saved_candidate_owner,
)


LABELING_TEMPLATE_SCHEMA = "semantic_candidate_tiebreak_labeling_template_v2"
_CANDIDATE_FIELDS = (
    "kind",
    "candidate_kind",
    "source_candidate_id",
    "evidence_id",
    "source_anchor",
    "row_label",
    "row_headers",
    "column_headers",
    "local_entity_surfaces",
    "raw_value",
    "raw_unit",
    "normalized_value",
    "normalized_unit",
    "period",
    "period_role",
    "period_label_surfaces",
    "period_source",
    "source_period_surface",
    "year",
    "value_year",
    "company",
    "document_company",
    "consolidation_scope",
    "segment",
    "basis",
    "statement_type",
    "table_context",
    "value_role",
    "aggregation_stage",
    "aggregate_label",
    "table_source_id",
    "physical_table_id",
    "physical_row_id",
    "physical_cell_id",
    "physical_value_id",
    "source_row_id",
    "source_span",
    "context_fingerprint",
)


def _fingerprint(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _resolved_target_projection(owner: Any) -> dict[str, Any]:
    return {
        "local_subjects": list(owner.local_subjects),
        "document_company": owner.document_company,
        "concept_keys": list(owner.concept_keys),
        "concept_aliases": list(owner.concept_aliases),
        "metric_surfaces": list(owner.metric_surfaces),
        "expected_unit_family": owner.expected_unit_family,
    }


def _candidate_projection(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: candidate.get(field)
        for field in _CANDIDATE_FIELDS
        if candidate.get(field) not in (None, "", [], {})
    }


def _strongest_tier(
    *,
    catalog: Sequence[Mapping[str, Any]],
    cohort: Mapping[str, Any],
    owner: Mapping[str, Any],
    parent_owner: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
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
    candidate_by_id = {
        str(candidate.get("candidate_id") or ""): candidate
        for candidate in candidates
    }
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
    eligible_ids = [
        candidate_id
        for candidate_id, match in matches.items()
        if match.state != "explicit_conflict"
        and str(candidate_by_id.get(candidate_id, {}).get("kind") or "")
        in allowed_kinds
    ]
    ranking = summarize_candidate_match_ranking(matches, eligible_ids)
    top_count = int(ranking.get("top_tier_candidate_count") or 0)
    ranked = rank_candidate_matches(
        candidates,
        matches,
        allowed_kinds=tuple(sorted(allowed_kinds)),
        limit=len(candidates),
    )
    strongest = ranked[:top_count] if top_count >= 2 else []
    return (
        strongest,
        ranking,
        {
            candidate_id: project_candidate_match(matches[candidate_id])
            for candidate_id in eligible_ids
        },
    )


def build_labeling_template(
    saved_plans: Sequence[Mapping[str, Any]],
    *,
    catalog_replay: Callable[
        [Mapping[str, Any], Mapping[str, Any]],
        tuple[list[dict[str, Any]], dict[str, Any]],
    ] = replay_verified_candidate_catalog,
) -> dict[str, Any]:
    """Build an unlabeled template from fingerprint-verified saved catalogs."""

    policy = dict(
        CALCULATION_PROMPT_POLICY.get("semantic_top_tier_tiebreaker") or {}
    )
    query_text_limit = int(policy.get("query_text_chars") or 260)
    candidate_text_limit = int(policy.get("candidate_text_chars") or 180)
    max_candidates_per_cohort = int(
        policy.get("max_candidates_per_cohort") or 12
    )
    max_pairs_per_query = int(policy.get("max_pairs_per_query") or 64)
    cases: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    excluded_cohorts: list[dict[str, Any]] = []
    pair_count_by_question: dict[str, int] = {}

    for saved in sorted(
        (dict(row) for row in saved_plans),
        key=lambda row: (
            str(row.get("question_id") or ""),
            str(row.get("source_file") or ""),
        ),
    ):
        question_id = str(saved.get("question_id") or "unknown")
        plan = dict(saved.get("plan") or {})
        catalog, replay = catalog_replay(
            plan,
            dict(saved.get("store") or {}),
        )
        if str(replay.get("status") or "") != "verified":
            skipped.append(
                {
                    "question_id": question_id,
                    "source_file": str(saved.get("source_file") or ""),
                    "reason": str(replay.get("reason") or "catalog_not_verified"),
                    "catalog_replay": dict(replay),
                }
            )
            continue
        obligations = [
            dict(item)
            for item in (plan.get("answer_obligations") or [])
            if isinstance(item, Mapping)
        ]
        for raw_cohort in plan.get("candidate_cohorts") or []:
            if not isinstance(raw_cohort, Mapping):
                continue
            cohort = dict(raw_cohort)
            owner, parent_owner = resolve_saved_candidate_owner(
                obligations,
                cohort,
            )
            if not owner:
                continue
            strongest, ranking, matches = _strongest_tier(
                catalog=catalog,
                cohort=cohort,
                owner=owner,
                parent_owner=parent_owner,
            )
            if len(strongest) < 2:
                continue
            tie_eligible, tie_eligibility_reason = (
                semantic_tie_break_cohort_eligibility(
                    candidate_kind=str(cohort.get("candidate_kind") or ""),
                    owner=owner,
                    parent_owner=parent_owner,
                )
            )
            if not tie_eligible:
                excluded_cohorts.append(
                    {
                        "question_id": question_id,
                        "cohort_id": str(cohort.get("cohort_id") or ""),
                        "owner_id": str(cohort.get("owner_id") or ""),
                        "reason": tie_eligibility_reason,
                    }
                )
                continue
            resolved_target = resolve_owner_target(
                owner,
                parent_owner=parent_owner,
            )
            resolved_projection = _resolved_target_projection(resolved_target)
            candidate_rows: list[dict[str, Any]] = []
            baseline_ids: list[str] = []
            for candidate in strongest:
                candidate_id = str(candidate.get("candidate_id") or "")
                candidate_text = candidate_cell_local_source_text(candidate)
                pair = SemanticTieBreakPairV5.create(
                    cohort_id=str(cohort.get("cohort_id") or ""),
                    owner_id=str(cohort.get("owner_id") or ""),
                    candidate_id=candidate_id,
                    query=str(saved.get("question") or ""),
                    owner=owner,
                    parent_owner=parent_owner,
                    resolved_target=resolved_projection,
                    candidate=candidate,
                    candidate_text=candidate_text,
                    query_text_limit=query_text_limit,
                    candidate_text_limit=candidate_text_limit,
                )
                baseline_ids.append(candidate_id)
                candidate_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "candidate_text": candidate_text,
                        "candidate": _candidate_projection(candidate),
                        "deterministic_match": dict(matches.get(candidate_id) or {}),
                        "projected_evidence_text": pair.evidence_text,
                        "candidate_context": pair.candidate_context,
                        "fact_role": pair.fact_role.to_projection(),
                        "fact_role_fingerprint": pair.fact_role_fingerprint,
                        "evidence_locator": pair.evidence_locator,
                        "pair_fingerprint": pair.pair_fingerprint,
                    }
                )
            case_material = {
                "question_id": question_id,
                "cohort_id": str(cohort.get("cohort_id") or ""),
                "owner_id": str(cohort.get("owner_id") or ""),
                "baseline_candidate_ids": baseline_ids,
                "pair_fingerprints": [
                    candidate["pair_fingerprint"] for candidate in candidate_rows
                ],
            }
            case = {
                "case_id": "case_" + _fingerprint(case_material)[:16],
                "label_status": "unlabeled",
                "expected_action": "",
                "acceptable_top_candidate_ids": [],
                "review_notes": "",
                "question_id": question_id,
                "query": str(saved.get("question") or ""),
                "source_file": str(saved.get("source_file") or ""),
                "cohort_id": str(cohort.get("cohort_id") or ""),
                "owner_id": str(cohort.get("owner_id") or ""),
                "owner_type": str(cohort.get("owner_type") or ""),
                "candidate_kind": str(cohort.get("candidate_kind") or ""),
                "owner": owner,
                "parent_owner": parent_owner,
                "resolved_target": resolved_projection,
                "baseline_candidate_ids": baseline_ids,
                "top_rank_vector": list(ranking.get("top_rank_vector") or []),
                "runtime_cohort_capacity_eligible": (
                    len(candidate_rows) <= max_candidates_per_cohort
                ),
                "candidates": candidate_rows,
                "semantic_case_fingerprint": _fingerprint(case_material),
            }
            cases.append(case)
            pair_count_by_question[question_id] = (
                pair_count_by_question.get(question_id, 0) + len(candidate_rows)
            )

    over_capacity_question_ids = sorted(
        question_id
        for question_id, pair_count in pair_count_by_question.items()
        if pair_count > max_pairs_per_query
    )
    material = {
        "schema": LABELING_TEMPLATE_SCHEMA,
        "pair_schema": SEMANTIC_TIE_BREAK_PAIR_SCHEMA,
        "cases": cases,
        "skipped": skipped,
        "excluded_cohorts": excluded_cohorts,
    }
    fingerprint_material = {
        "schema": LABELING_TEMPLATE_SCHEMA,
        "pair_schema": SEMANTIC_TIE_BREAK_PAIR_SCHEMA,
        "semantic_case_fingerprints": [
            case["semantic_case_fingerprint"] for case in cases
        ],
        "skipped": [
            {
                "question_id": row.get("question_id"),
                "reason": row.get("reason"),
            }
            for row in skipped
        ],
        "excluded_cohorts": excluded_cohorts,
    }
    return {
        **material,
        "summary": {
            "case_count": len(cases),
            "candidate_pair_count": sum(
                len(case.get("candidates") or []) for case in cases
            ),
            "question_count": len(pair_count_by_question),
            "skipped_plan_count": len(skipped),
            "excluded_cohort_count": len(excluded_cohorts),
            "excluded_cohort_reason_counts": {
                reason: sum(
                    row.get("reason") == reason for row in excluded_cohorts
                )
                for reason in sorted(
                    {str(row.get("reason") or "") for row in excluded_cohorts}
                )
                if reason
            },
            "over_capacity_question_ids": over_capacity_question_ids,
            "label_status": "unlabeled",
        },
        "template_fingerprint": _fingerprint(fingerprint_material),
    }


def render_summary(template: Mapping[str, Any]) -> str:
    summary = dict(template.get("summary") or {})
    return (
        "# Semantic Tie-Break Labeling Template\n\n"
        f"Cases: {summary.get('case_count', 0)}\n"
        f"Candidate pairs: {summary.get('candidate_pair_count', 0)}\n"
        f"Questions: {summary.get('question_count', 0)}\n"
        f"Skipped plans: {summary.get('skipped_plan_count', 0)}\n"
        f"Excluded non-atomic cohorts: {summary.get('excluded_cohort_count', 0)}\n"
        f"Fingerprint: {template.get('template_fingerprint', '')}\n"
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
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
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print only counts and the template fingerprint.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    plans = load_saved_plans(
        args.paths,
        question_ids=set(args.question_id) if args.question_id else None,
    )
    if not plans:
        raise SystemExit("No supported saved calculation plans were found.")
    template = build_labeling_template(plans)
    rendered = json.dumps(
        template,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(render_summary(template) if args.summary_only else rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LABELING_TEMPLATE_SCHEMA",
    "build_labeling_template",
    "render_summary",
]
