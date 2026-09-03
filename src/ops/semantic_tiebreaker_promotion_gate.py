"""Evaluate the optional semantic candidate tie-breaker on labeled pairs.

The gate is local and provider-free.  By default it only loads already-cached
model files, keeps the runtime feature disabled, and writes nothing unless an
explicit output path is supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.agent.financial_candidate_tiebreaker import (
    SEMANTIC_TIE_BREAK_PAIR_SCHEMA,
    SUPPORTED_SCORE_TRANSFORMS,
    LocalCrossEncoderTieBreaker,
    SemanticTieBreakBatchV1,
    SemanticTieBreakPairV3,
)
from src.config.retrieval_policy import CALCULATION_PROMPT_POLICY


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "semantic_candidate_tiebreaker"
    / "hard_negatives_v1.json"
)
FIXTURE_SCHEMA = "semantic_candidate_tiebreak_hard_negatives_v1"
EXPECTED_ACTIONS = frozenset({"select", "abstain"})


def _fingerprint(value: Any) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_fixture(path: str | Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    fixture_path = Path(path)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != FIXTURE_SCHEMA:
        raise ValueError(f"unsupported semantic tie-break fixture: {fixture_path}")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("semantic tie-break fixture requires cases")

    seen_case_ids: set[str] = set()
    seen_cohort_ids: set[str] = set()
    for raw_case in cases:
        if not isinstance(raw_case, dict):
            raise ValueError("semantic tie-break fixture case must be an object")
        case_id = str(raw_case.get("case_id") or "").strip()
        cohort_id = str(raw_case.get("cohort_id") or "").strip()
        action = str(raw_case.get("expected_action") or "").strip()
        candidates = raw_case.get("candidates")
        if not case_id or case_id in seen_case_ids:
            raise ValueError(f"missing or duplicate case_id: {case_id or '<empty>'}")
        if not cohort_id or cohort_id in seen_cohort_ids:
            raise ValueError(
                f"missing or duplicate cohort_id: {cohort_id or '<empty>'}"
            )
        if action not in EXPECTED_ACTIONS:
            raise ValueError(f"unsupported expected_action for {case_id}: {action}")
        if not isinstance(candidates, list) or len(candidates) < 2:
            raise ValueError(f"case requires at least two candidates: {case_id}")
        candidate_ids = [
            str(candidate.get("candidate_id") or "").strip()
            for candidate in candidates
            if isinstance(candidate, dict)
        ]
        if (
            len(candidate_ids) != len(candidates)
            or any(not candidate_id for candidate_id in candidate_ids)
            or len(set(candidate_ids)) != len(candidate_ids)
        ):
            raise ValueError(f"invalid candidate ids: {case_id}")
        baseline_ids = [
            str(candidate_id).strip()
            for candidate_id in raw_case.get("baseline_candidate_ids") or []
        ]
        if len(baseline_ids) != len(candidate_ids) or set(baseline_ids) != set(
            candidate_ids
        ):
            raise ValueError(f"baseline must order every candidate: {case_id}")
        acceptable_ids = {
            str(candidate_id).strip()
            for candidate_id in raw_case.get("acceptable_top_candidate_ids") or []
            if str(candidate_id).strip()
        }
        if action == "select" and not acceptable_ids:
            raise ValueError(f"select case requires an acceptable candidate: {case_id}")
        if not acceptable_ids.issubset(set(candidate_ids)):
            raise ValueError(f"acceptable candidate is not visible: {case_id}")
        seen_case_ids.add(case_id)
        seen_cohort_ids.add(cohort_id)
    return dict(payload)


def build_pairs(
    payload: Mapping[str, Any],
) -> tuple[SemanticTieBreakPairV3, ...]:
    policy = dict(
        CALCULATION_PROMPT_POLICY.get("semantic_top_tier_tiebreaker") or {}
    )
    pairs: list[SemanticTieBreakPairV3] = []
    for raw_case in payload.get("cases") or []:
        case = dict(raw_case)
        owner = dict(case.get("owner") or {})
        parent_owner = case.get("parent_owner")
        resolved_target = dict(case.get("resolved_target") or {})
        for raw_candidate in case.get("candidates") or []:
            candidate_fixture = dict(raw_candidate)
            candidate = dict(candidate_fixture.get("candidate") or {})
            pairs.append(
                SemanticTieBreakPairV3.create(
                    cohort_id=str(case.get("cohort_id") or ""),
                    owner_id=str(case.get("owner_id") or ""),
                    candidate_id=str(candidate_fixture.get("candidate_id") or ""),
                    query=str(case.get("query") or ""),
                    owner=owner,
                    parent_owner=(
                        dict(parent_owner)
                        if isinstance(parent_owner, Mapping)
                        else None
                    ),
                    resolved_target=resolved_target,
                    candidate=candidate,
                    candidate_text=str(
                        candidate_fixture.get("candidate_text")
                        or candidate.get("source_text")
                        or ""
                    ),
                    query_text_limit=int(policy.get("query_text_chars") or 260),
                    candidate_text_limit=int(
                        policy.get("candidate_text_chars") or 180
                    ),
                )
            )
    return tuple(pairs)


def _nearest_rank_percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil((percentile / 100.0) * len(ordered)))
    return ordered[min(rank - 1, len(ordered) - 1)]


def calibrate_score_margin(
    payload: Mapping[str, Any],
    score_batch: SemanticTieBreakBatchV1,
) -> dict[str, Any]:
    """Find the best observed zero-error margin without changing runtime policy."""

    thresholds = dict(payload.get("thresholds") or {})
    current_margin = float(thresholds.get("min_score_margin") or 0.0)
    scores_by_cohort = score_batch.scores_by_cohort()
    observations: list[dict[str, Any]] = []
    missing_case_ids: list[str] = []
    for raw_case in payload.get("cases") or []:
        case = dict(raw_case)
        case_id = str(case.get("case_id") or "")
        cohort_id = str(case.get("cohort_id") or "")
        visible_ids = [
            str(candidate.get("candidate_id") or "")
            for candidate in case.get("candidates") or []
        ]
        cohort_scores = dict(scores_by_cohort.get(cohort_id) or {})
        if any(candidate_id not in cohort_scores for candidate_id in visible_ids):
            missing_case_ids.append(case_id)
            continue
        ordered_ids = sorted(
            visible_ids,
            key=lambda candidate_id: (
                -cohort_scores[candidate_id],
                candidate_id,
            ),
        )
        acceptable_ids = {
            str(candidate_id)
            for candidate_id in case.get("acceptable_top_candidate_ids") or []
        }
        observations.append(
            {
                "case_id": case_id,
                "expected_action": str(case.get("expected_action") or ""),
                "top_candidate_id": ordered_ids[0],
                "top_is_acceptable": ordered_ids[0] in acceptable_ids,
                "margin": float(
                    cohort_scores[ordered_ids[0]]
                    - cohort_scores[ordered_ids[1]]
                ),
            }
        )
    if score_batch.status != "applied" or missing_case_ids or not observations:
        return {
            "schema": "semantic_score_margin_calibration_v1",
            "status": "unavailable",
            "score_transform": score_batch.score_transform,
            "current_min_score_margin": current_margin,
            "recommended_min_score_margin": None,
            "missing_case_ids": missing_case_ids,
            "runtime_policy_changed": False,
        }

    candidate_thresholds = {0.0, current_margin}
    for observation in observations:
        margin = round(max(0.0, float(observation["margin"])), 8)
        candidate_thresholds.add(margin)
        candidate_thresholds.add(round(margin + 1e-8, 8))

    selection_count = sum(
        observation["expected_action"] == "select"
        for observation in observations
    )
    abstention_count = sum(
        observation["expected_action"] == "abstain"
        for observation in observations
    )
    max_confident_errors = int(
        thresholds.get("max_confident_error_count") or 0
    )
    min_abstention_accuracy = float(
        thresholds.get("min_abstention_accuracy") or 0.0
    )
    rows: list[dict[str, Any]] = []
    for margin_threshold in sorted(candidate_thresholds):
        confident_correct = 0
        confident_errors = 0
        correct_abstentions = 0
        for observation in observations:
            confident = float(observation["margin"]) >= margin_threshold
            expected_select = observation["expected_action"] == "select"
            correct_selection = bool(
                expected_select and observation["top_is_acceptable"]
            )
            if confident and correct_selection:
                confident_correct += 1
            elif confident:
                confident_errors += 1
            if not confident and not expected_select:
                correct_abstentions += 1
        coverage = confident_correct / selection_count if selection_count else 0.0
        abstention_accuracy = (
            correct_abstentions / abstention_count if abstention_count else 1.0
        )
        rows.append(
            {
                "min_score_margin": margin_threshold,
                "confident_correct_selection_rate": coverage,
                "confident_error_count": confident_errors,
                "abstention_accuracy": abstention_accuracy,
                "eligible": confident_errors <= max_confident_errors
                and abstention_accuracy >= min_abstention_accuracy,
            }
        )
    eligible = [row for row in rows if row["eligible"]]
    recommended = (
        max(
            eligible,
            key=lambda row: (
                row["confident_correct_selection_rate"],
                -row["min_score_margin"],
            ),
        )
        if eligible
        else None
    )
    return {
        "schema": "semantic_score_margin_calibration_v1",
        "status": "available" if recommended else "no_safe_margin",
        "score_transform": score_batch.score_transform,
        "current_min_score_margin": current_margin,
        "recommended_min_score_margin": (
            round(float(recommended["min_score_margin"]), 8)
            if recommended
            else None
        ),
        "confident_correct_selection_rate": (
            round(float(recommended["confident_correct_selection_rate"]), 6)
            if recommended
            else 0.0
        ),
        "confident_error_count": (
            int(recommended["confident_error_count"])
            if recommended
            else None
        ),
        "abstention_accuracy": (
            round(float(recommended["abstention_accuracy"]), 6)
            if recommended
            else None
        ),
        "observed_margin_min": round(
            min(float(row["margin"]) for row in observations),
            8,
        ),
        "observed_margin_max": round(
            max(float(row["margin"]) for row in observations),
            8,
        ),
        "missing_case_ids": [],
        "runtime_policy_changed": False,
        "note": "development fixture diagnostic; review before policy change",
    }


def evaluate_gate(
    payload: Mapping[str, Any],
    score_batch: SemanticTieBreakBatchV1,
    *,
    warm_latency_ms: Sequence[float],
    cold_load_ms: float | None = None,
    resolved_device: str = "",
) -> dict[str, Any]:
    thresholds = dict(payload.get("thresholds") or {})
    minimum_margin = float(thresholds.get("min_score_margin") or 0.0)
    scores_by_cohort = score_batch.scores_by_cohort()
    case_results: list[dict[str, Any]] = []
    selection_count = 0
    baseline_top1_correct_count = 0
    model_top1_correct_count = 0
    confident_selection_count = 0
    confident_error_case_ids: list[str] = []
    abstention_count = 0
    correct_abstention_count = 0
    missing_score_case_ids: list[str] = []

    for raw_case in payload.get("cases") or []:
        case = dict(raw_case)
        case_id = str(case.get("case_id") or "")
        cohort_id = str(case.get("cohort_id") or "")
        expected_action = str(case.get("expected_action") or "")
        acceptable_ids = {
            str(candidate_id)
            for candidate_id in case.get("acceptable_top_candidate_ids") or []
        }
        visible_ids = [
            str(candidate.get("candidate_id") or "")
            for candidate in case.get("candidates") or []
        ]
        cohort_scores = dict(scores_by_cohort.get(cohort_id) or {})
        missing_ids = [
            candidate_id
            for candidate_id in visible_ids
            if candidate_id not in cohort_scores
        ]
        if missing_ids:
            missing_score_case_ids.append(case_id)
            ordered_ids: list[str] = []
            margin = None
            decision = "unavailable"
            top_candidate_id = ""
        else:
            ordered_ids = sorted(
                visible_ids,
                key=lambda candidate_id: (
                    -cohort_scores[candidate_id],
                    candidate_id,
                ),
            )
            top_candidate_id = ordered_ids[0]
            margin = (
                cohort_scores[ordered_ids[0]] - cohort_scores[ordered_ids[1]]
            )
            decision = "select" if margin >= minimum_margin else "abstain"

        baseline_ids = [
            str(candidate_id)
            for candidate_id in case.get("baseline_candidate_ids") or []
        ]
        baseline_top1_correct = bool(
            expected_action == "select"
            and baseline_ids
            and baseline_ids[0] in acceptable_ids
        )
        model_top1_correct = bool(
            expected_action == "select" and top_candidate_id in acceptable_ids
        )
        case_passed = False
        if expected_action == "select":
            selection_count += 1
            baseline_top1_correct_count += int(baseline_top1_correct)
            model_top1_correct_count += int(model_top1_correct)
            if decision == "select":
                confident_selection_count += 1
                if not model_top1_correct:
                    confident_error_case_ids.append(case_id)
            case_passed = decision == "select" and model_top1_correct
        else:
            abstention_count += 1
            case_passed = decision == "abstain"
            correct_abstention_count += int(case_passed)
            if decision == "select":
                confident_error_case_ids.append(case_id)

        case_results.append(
            {
                "case_id": case_id,
                "expected_action": expected_action,
                "decision": decision,
                "passed": case_passed,
                "baseline_top_candidate_id": baseline_ids[0] if baseline_ids else "",
                "model_top_candidate_id": top_candidate_id,
                "model_top1_correct": model_top1_correct,
                "score_margin": round(margin, 8) if margin is not None else None,
                "ordered_candidate_ids": ordered_ids,
                "scores": {
                    candidate_id: cohort_scores[candidate_id]
                    for candidate_id in ordered_ids
                },
                "missing_candidate_ids": missing_ids,
            }
        )

    def ratio(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 0.0

    baseline_top1_accuracy = ratio(
        baseline_top1_correct_count,
        selection_count,
    )
    model_top1_accuracy = ratio(model_top1_correct_count, selection_count)
    top1_gain = model_top1_accuracy - baseline_top1_accuracy
    confident_selection_rate = ratio(confident_selection_count, selection_count)
    abstention_accuracy = ratio(correct_abstention_count, abstention_count)
    warm_p95_ms = _nearest_rank_percentile(warm_latency_ms, 95.0)

    checks = {
        "score_batch_applied": score_batch.status == "applied",
        "all_scores_present": not missing_score_case_ids,
        "top1_accuracy": model_top1_accuracy
        >= float(thresholds.get("min_top1_accuracy") or 0.0),
        "top1_gain": top1_gain >= float(thresholds.get("min_top1_gain") or 0.0),
        "confident_selection_rate": confident_selection_rate
        >= float(thresholds.get("min_confident_selection_rate") or 0.0),
        "abstention_accuracy": abstention_accuracy
        >= float(thresholds.get("min_abstention_accuracy") or 0.0),
        "confident_errors": len(confident_error_case_ids)
        <= int(thresholds.get("max_confident_error_count") or 0),
        "warm_latency": warm_p95_ms is not None
        and warm_p95_ms <= float(thresholds.get("max_warm_p95_ms") or 0.0),
    }
    promotion_ready = bool(checks) and all(checks.values())
    margin_calibration = calibrate_score_margin(payload, score_batch)
    return {
        "schema": "semantic_tiebreaker_promotion_gate_result_v1",
        "status": "ready" if promotion_ready else "needs_review",
        "promotion_ready": promotion_ready,
        "gate_id": str(payload.get("gate_id") or ""),
        "fixture_schema": str(payload.get("schema") or ""),
        "fixture_fingerprint": _fingerprint(payload),
        "pair_schema": SEMANTIC_TIE_BREAK_PAIR_SCHEMA,
        "scorer": score_batch.to_projection(),
        "resolved_device": resolved_device,
        "case_count": len(case_results),
        "selection_case_count": selection_count,
        "abstention_case_count": abstention_count,
        "thresholds": thresholds,
        "metrics": {
            "baseline_top1_accuracy": round(baseline_top1_accuracy, 6),
            "model_top1_accuracy": round(model_top1_accuracy, 6),
            "top1_gain": round(top1_gain, 6),
            "confident_selection_rate": round(confident_selection_rate, 6),
            "abstention_accuracy": round(abstention_accuracy, 6),
            "confident_error_count": len(confident_error_case_ids),
            "cold_load_ms": (
                round(float(cold_load_ms), 3)
                if cold_load_ms is not None
                else None
            ),
            "warm_latency_ms": [
                round(float(value), 3) for value in warm_latency_ms
            ],
            "warm_p95_ms": (
                round(float(warm_p95_ms), 3)
                if warm_p95_ms is not None
                else None
            ),
        },
        "margin_calibration": margin_calibration,
        "checks": checks,
        "confident_error_case_ids": confident_error_case_ids,
        "missing_score_case_ids": missing_score_case_ids,
        "cases": case_results,
    }


def run_gate(
    *,
    fixture_path: str | Path = DEFAULT_FIXTURE_PATH,
    local_files_only: bool = True,
    latency_runs: int = 3,
    device: str = "",
    score_transform: str = "",
) -> dict[str, Any]:
    payload = load_fixture(fixture_path)
    pairs = build_pairs(payload)
    policy = dict(
        CALCULATION_PROMPT_POLICY.get("semantic_top_tier_tiebreaker") or {}
    )
    scorer = LocalCrossEncoderTieBreaker(
        model_name=str(policy.get("model_name") or ""),
        revision=str(policy.get("revision") or ""),
        code_revision=str(policy.get("code_revision") or ""),
        score_transform=str(
            score_transform or policy.get("score_transform") or "sigmoid"
        ),
        max_length=int(policy.get("max_length") or 256),
        batch_size=int(policy.get("batch_size") or 32),
        cache_size=0,
        device=device,
        local_files_only=local_files_only,
        trust_remote_code=bool(policy.get("trust_remote_code", False)),
    )
    load_started = time.perf_counter_ns()
    prepared = scorer.prepare()
    cold_load_ms = (time.perf_counter_ns() - load_started) / 1_000_000.0
    if not prepared:
        batch = SemanticTieBreakBatchV1(
            status="unavailable",
            scorer_id=scorer.scorer_id,
            requested_pair_count=len(pairs),
            error_code=scorer.load_error_code or "model_unavailable",
            score_transform=scorer.score_transform,
        )
        return evaluate_gate(
            payload,
            batch,
            warm_latency_ms=(),
            cold_load_ms=cold_load_ms,
            resolved_device=scorer.resolved_device,
        )

    scorer.score_pairs(pairs)
    timings: list[float] = []
    batch = SemanticTieBreakBatchV1(
        status="unavailable",
        scorer_id=scorer.scorer_id,
        requested_pair_count=len(pairs),
        error_code="latency_run_missing",
        score_transform=scorer.score_transform,
    )
    for _ in range(max(1, int(latency_runs))):
        started = time.perf_counter_ns()
        batch = scorer.score_pairs(pairs)
        timings.append((time.perf_counter_ns() - started) / 1_000_000.0)
        if batch.status != "applied":
            break
    return evaluate_gate(
        payload,
        batch,
        warm_latency_ms=timings,
        cold_load_ms=cold_load_ms,
        resolved_device=scorer.resolved_device,
    )


def render_text(result: Mapping[str, Any]) -> str:
    metrics = dict(result.get("metrics") or {})
    checks = dict(result.get("checks") or {})
    calibration = dict(result.get("margin_calibration") or {})
    scorer = dict(result.get("scorer") or {})
    lines = [
        "# Semantic Tie-Breaker Promotion Gate",
        "",
        f"Status: {result.get('status')}",
        f"Cases: {result.get('case_count')}",
        f"Pair schema: {result.get('pair_schema')}",
        f"Scorer: {scorer.get('scorer_id', '')}",
        f"Score transform: {scorer.get('score_transform') or '-'}",
        f"Device: {result.get('resolved_device') or '-'}",
        "",
        "Metrics:",
        f"  - baseline_top1_accuracy: {metrics.get('baseline_top1_accuracy')}",
        f"  - model_top1_accuracy: {metrics.get('model_top1_accuracy')}",
        f"  - top1_gain: {metrics.get('top1_gain')}",
        f"  - confident_selection_rate: {metrics.get('confident_selection_rate')}",
        f"  - abstention_accuracy: {metrics.get('abstention_accuracy')}",
        f"  - confident_error_count: {metrics.get('confident_error_count')}",
        f"  - cold_load_ms: {metrics.get('cold_load_ms')}",
        f"  - warm_p95_ms: {metrics.get('warm_p95_ms')}",
        f"  - diagnostic_recommended_margin: {calibration.get('recommended_min_score_margin')}",
        "",
        "Checks:",
        *[
            f"  - {name}: {str(bool(value)).lower()}"
            for name, value in checks.items()
        ],
    ]
    return "\n".join(lines) + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="Permit model download. Default uses only the existing local cache.",
    )
    parser.add_argument("--device", default="")
    parser.add_argument(
        "--score-transform",
        choices=tuple(sorted(SUPPORTED_SCORE_TRANSFORMS)),
        default="",
        help="Override the explicit model-score transform for calibration.",
    )
    parser.add_argument("--latency-runs", type=int, default=3)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_gate(
        fixture_path=args.fixture,
        local_files_only=not args.allow_download,
        latency_runs=args.latency_runs,
        device=str(args.device or ""),
        score_transform=str(args.score_transform or ""),
    )
    rendered = (
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.format == "json"
        else render_text(result)
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result.get("promotion_ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_FIXTURE_PATH",
    "FIXTURE_SCHEMA",
    "build_pairs",
    "calibrate_score_margin",
    "evaluate_gate",
    "load_fixture",
    "render_text",
    "run_gate",
]
