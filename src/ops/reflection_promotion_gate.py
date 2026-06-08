"""Run the fixture-backed self-reflection promotion gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "reflection_promotion_gate" / "cases.json"
)
DEFAULT_STORE_FIXED_CASES_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "reflection_promotion_gate" / "store_fixed_cases.json"
)
DEFAULT_CASES_PATHS = (DEFAULT_CASES_PATH, DEFAULT_STORE_FIXED_CASES_PATH)
DEFAULT_TRACE_SUMMARY_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "promotion_trace_summary"
    / "store_fixed_candidate_summary.json"
)
DEFAULT_TRACE_SUMMARY_PATHS = (DEFAULT_TRACE_SUMMARY_PATH,)
REQUIRED_ACTIONS = {
    "retry_retrieval",
    "synthesize_from_task_outputs",
    "stop_insufficient",
}
REQUIRED_SUITE_CASE_SOURCES = {
    "base_fixture",
    "store_fixed_eval_only_candidate_surface",
    "store_fixed_eval_only_trace_summary",
}
MAX_REFLECTION_RETRY_BUDGET = 1
FINAL_ACCEPTANCE_AUTHORITY = "critic_orchestrator_handoff"


def _read_json_object(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"reflection promotion fixture must be a JSON object: {path}")
    return dict(payload)


def _combine_payloads(payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    gate_ids = [str(payload.get("gate_id") or "") for payload in payloads if payload.get("gate_id")]
    cases: List[Dict[str, Any]] = []
    for payload in payloads:
        source = str(
            payload.get("case_source")
            or payload.get("source_type")
            or "base_fixture"
        )
        for case in list(payload.get("cases") or []):
            if isinstance(case, dict):
                projected = dict(case)
                projected["_promotion_case_source"] = source
                cases.append(projected)
    return {
        "gate_id": "+".join(gate_ids),
        "fixture_count": len(payloads),
        "source_gate_ids": gate_ids,
        "cases": cases,
        "required_case_sources": sorted(REQUIRED_SUITE_CASE_SOURCES),
    }


def _payload_from_trace_summary(path: Path) -> Dict[str, Any]:
    payload = _read_json_object(path)
    source = str(payload.get("source_type") or "trace_summary")
    cases = [
        {
            **dict(case),
            "_promotion_case_source": source,
        }
        for case in list(payload.get("reflection_promotion_cases") or [])
        if isinstance(case, dict)
    ]
    return {
        "gate_id": str(payload.get("summary_id") or path.stem),
        "case_source": source,
        "cases": cases,
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _case_action(case: Dict[str, Any]) -> str:
    report = case.get("reflection_report") if isinstance(case.get("reflection_report"), dict) else {}
    return str(report.get("action_taken") or case.get("expected_action") or "").strip()


def _case_reflection_action(case: Dict[str, Any]) -> Dict[str, Any]:
    action = case.get("reflection_action")
    return dict(action) if isinstance(action, dict) else {}


def _case_integrity_status(case: Dict[str, Any]) -> str:
    trace = case.get("task_artifact_trace") if isinstance(case.get("task_artifact_trace"), dict) else {}
    return str(trace.get("integrity_status") or "").strip()


def _is_final_accepted(case: Dict[str, Any]) -> bool:
    return str(case.get("final_status") or "").strip() == "accepted"


def _is_false_recovery(case: Dict[str, Any]) -> bool:
    if not _is_final_accepted(case):
        return False
    return (
        not bool(case.get("evidence_supported"))
        or str(case.get("calculation_trace_status") or "").strip() != "ok"
        or _case_integrity_status(case) != "ok"
    )


def _reflection_report_contract_issues(case: Dict[str, Any]) -> List[str]:
    if not bool(case.get("reflection_triggered")):
        return []
    case_id = str(case.get("case_id") or "unknown")
    report = case.get("reflection_report") if isinstance(case.get("reflection_report"), dict) else {}
    issues: List[str] = []
    action = str(report.get("action_taken") or "").strip()
    outcome = str(report.get("outcome") or "").strip()
    if not report:
        issues.append("missing_reflection_report")
    if not outcome:
        issues.append("missing_report_outcome")
    if action not in REQUIRED_ACTIONS:
        issues.append("invalid_report_action")
    reflection_action = _case_reflection_action(case)
    action_type = str(reflection_action.get("action_type") or "").strip()
    if reflection_action and action_type != action:
        issues.append("reflection_action_mismatch")
    if action == "retry_retrieval":
        retry_queries = reflection_action.get("retry_queries")
        has_retry_queries = (
            isinstance(retry_queries, list)
            and any(str(item).strip() for item in retry_queries)
        )
        if not reflection_action:
            issues.append("missing_reflection_action")
        elif not has_retry_queries:
            issues.append("missing_retry_query_surface")
    if action == "synthesize_from_task_outputs":
        synthesis_source_ids = reflection_action.get("synthesis_source_ids")
        has_synthesis_source_ids = (
            isinstance(synthesis_source_ids, list)
            and any(str(item).strip() for item in synthesis_source_ids)
        )
        if not reflection_action:
            issues.append("missing_reflection_action")
        elif not has_synthesis_source_ids:
            issues.append("missing_synthesis_source_surface")
    if "budget_consumed" not in report:
        issues.append("missing_budget_consumed")
    else:
        try:
            budget_consumed = int(report.get("budget_consumed") or 0)
        except (TypeError, ValueError):
            budget_consumed = MAX_REFLECTION_RETRY_BUDGET + 1
        if budget_consumed < 0 or budget_consumed > MAX_REFLECTION_RETRY_BUDGET:
            issues.append("budget_out_of_bounds")

    if _is_final_accepted(case):
        target_task_ids = report.get("target_task_ids")
        target_artifact_ids = report.get("target_artifact_ids")
        has_target_refs = bool(
            isinstance(target_task_ids, list)
            and target_task_ids
            and isinstance(target_artifact_ids, list)
            and target_artifact_ids
        )
        if not has_target_refs:
            issues.append("missing_acceptance_target_refs")
        if str(report.get("final_acceptance_authority") or "").strip() != FINAL_ACCEPTANCE_AUTHORITY:
            issues.append("reflection_marked_or_missing_acceptance_authority")

    if action == "stop_insufficient":
        blocking_issues = report.get("blocking_issues")
        if not isinstance(blocking_issues, list) or not blocking_issues:
            issues.append("missing_stop_blocking_issues")

    return [f"{case_id}:{issue}" for issue in issues]


def evaluate_cases(payload: Dict[str, Any]) -> Dict[str, Any]:
    cases = [dict(case) for case in list(payload.get("cases") or []) if isinstance(case, dict)]
    default_case_source = str(
        payload.get("case_source")
        or payload.get("source_type")
        or "base_fixture"
    )
    case_source_counts: Dict[str, int] = {}
    for case in cases:
        source = str(case.get("_promotion_case_source") or default_case_source)
        if source:
            case_source_counts[source] = case_source_counts.get(source, 0) + 1
    required_case_sources = [
        str(source)
        for source in list(payload.get("required_case_sources") or [])
        if str(source).strip()
    ]
    source_coverage_issues = [
        f"missing_case_source:{source}"
        for source in required_case_sources
        if case_source_counts.get(source, 0) <= 0
    ]
    eligible_cases = [case for case in cases if bool(case.get("eligible"))]
    triggered_cases = [case for case in cases if bool(case.get("reflection_triggered"))]
    triggered_eligible_cases = [
        case for case in eligible_cases if bool(case.get("reflection_triggered"))
    ]
    accepted_reflected_cases = [
        case for case in triggered_cases if _is_final_accepted(case)
    ]
    false_recovery_cases = [
        case for case in accepted_reflected_cases if _is_false_recovery(case)
    ]
    integrity_ok_reflected_cases = [
        case for case in accepted_reflected_cases if _case_integrity_status(case) == "ok"
    ]
    latency_deltas = [
        int(case.get("reflected_step_count") or 0) - int(case.get("baseline_step_count") or 0)
        for case in triggered_cases
    ]
    action_counts: Dict[str, int] = {}
    action_mismatches: List[str] = []
    report_contract_issues: List[str] = []
    for case in cases:
        action = _case_action(case)
        if action:
            action_counts[action] = action_counts.get(action, 0) + 1
        expected = str(case.get("expected_action") or "").strip()
        if expected and expected != "none" and action != expected:
            action_mismatches.append(str(case.get("case_id") or "unknown"))
        report_contract_issues.extend(_reflection_report_contract_issues(case))

    clean_pass_cases = [
        case
        for case in cases
        if not bool(case.get("eligible")) and str(case.get("initial_status") or "") == "accepted"
    ]
    clean_pass_triggered = [
        case for case in clean_pass_cases if bool(case.get("reflection_triggered"))
    ]
    stop_cases = [case for case in triggered_cases if _case_action(case) == "stop_insufficient"]
    stop_cases_accepted = [case for case in stop_cases if _is_final_accepted(case)]

    signals = {
        "reflection_trigger_rate": _ratio(len(triggered_eligible_cases), len(eligible_cases)),
        "recovery_rate": _ratio(len(accepted_reflected_cases), len(triggered_cases)),
        "false_recovery_rate": _ratio(len(false_recovery_cases), len(accepted_reflected_cases)),
        "latency_delta": _ratio(sum(latency_deltas), len(latency_deltas)),
        "integrity_preservation_rate": _ratio(
            len(integrity_ok_reflected_cases),
            len(accepted_reflected_cases),
        ),
    }
    required_actions_present = all(action_counts.get(action, 0) > 0 for action in REQUIRED_ACTIONS)
    promotion_ready = (
        bool(cases)
        and required_actions_present
        and not source_coverage_issues
        and not action_mismatches
        and not report_contract_issues
        and not false_recovery_cases
        and signals["integrity_preservation_rate"] == 1.0
        and bool(clean_pass_cases)
        and not clean_pass_triggered
        and bool(stop_cases)
        and not stop_cases_accepted
    )

    return {
        "status": "ready" if promotion_ready else "needs_review",
        "gate_id": str(payload.get("gate_id") or ""),
        "fixture_count": int(payload.get("fixture_count") or 1),
        "source_gate_ids": list(
            payload.get("source_gate_ids") or [str(payload.get("gate_id") or "")]
        ),
        "case_count": len(cases),
        "eligible_case_count": len(eligible_cases),
        "triggered_case_count": len(triggered_cases),
        "accepted_reflected_case_count": len(accepted_reflected_cases),
        "false_recovery_case_ids": [
            str(case.get("case_id") or "unknown") for case in false_recovery_cases
        ],
        "action_counts": action_counts,
        "action_mismatch_case_ids": action_mismatches,
        "report_contract_ok": not report_contract_issues,
        "report_contract_issue_case_ids": report_contract_issues,
        "required_actions_present": required_actions_present,
        "source_coverage_ok": not source_coverage_issues,
        "source_coverage_issue_ids": source_coverage_issues,
        "case_source_counts": case_source_counts,
        "required_case_sources": required_case_sources,
        "clean_pass_no_trigger": bool(clean_pass_cases) and not clean_pass_triggered,
        "stop_insufficient_no_acceptance": bool(stop_cases) and not stop_cases_accepted,
        "promotion_signals": signals,
        "cases": [
            {
                "case_id": str(case.get("case_id") or ""),
                "eligible": bool(case.get("eligible")),
                "reflection_triggered": bool(case.get("reflection_triggered")),
                "action_taken": _case_action(case),
                "final_status": str(case.get("final_status") or ""),
                "integrity_status": _case_integrity_status(case),
            }
            for case in cases
        ],
    }


def run_gate(*, cases_path: str | Path = DEFAULT_CASES_PATH) -> Dict[str, Any]:
    path = Path(cases_path)
    result = evaluate_cases(_read_json_object(path))
    result["cases_path"] = str(path)
    result["cases_paths"] = [str(path)]
    return result


def run_gate_suite(
    *,
    cases_paths: List[str | Path] | None = None,
    trace_summary_paths: List[str | Path] | None = None,
) -> Dict[str, Any]:
    paths = [Path(path) for path in (cases_paths or list(DEFAULT_CASES_PATHS))]
    trace_paths = [
        Path(path)
        for path in (
            trace_summary_paths
            if trace_summary_paths is not None
            else list(DEFAULT_TRACE_SUMMARY_PATHS)
        )
    ]
    payloads = [_read_json_object(path) for path in paths]
    trace_payloads = [_payload_from_trace_summary(path) for path in trace_paths]
    result = evaluate_cases(_combine_payloads(payloads + trace_payloads))
    result["fixture_count"] = len(paths)
    result["cases_path"] = str(paths[0]) if len(paths) == 1 else ""
    result["cases_paths"] = [str(path) for path in paths]
    result["trace_summary_count"] = len(trace_paths)
    result["trace_summary_paths"] = [str(path) for path in trace_paths]
    return result


def render_text(result: Dict[str, Any]) -> str:
    signals = dict(result.get("promotion_signals") or {})
    lines = [
        "# Reflection Promotion Gate",
        "",
        f"Status: {result.get('status')}",
        f"Cases: {result.get('case_count')}",
        f"Required actions present: {str(result.get('required_actions_present')).lower()}",
        f"Source coverage ok: {str(result.get('source_coverage_ok')).lower()}",
        f"Report contract ok: {str(result.get('report_contract_ok')).lower()}",
        f"Clean pass no trigger: {str(result.get('clean_pass_no_trigger')).lower()}",
        (
            "Stop insufficient no acceptance: "
            f"{str(result.get('stop_insufficient_no_acceptance')).lower()}"
        ),
        "",
        "Promotion Signals:",
        f"  - reflection_trigger_rate: {signals.get('reflection_trigger_rate'):.3f}",
        f"  - recovery_rate: {signals.get('recovery_rate'):.3f}",
        f"  - false_recovery_rate: {signals.get('false_recovery_rate'):.3f}",
        f"  - latency_delta: {signals.get('latency_delta'):.3f}",
        f"  - integrity_preservation_rate: {signals.get('integrity_preservation_rate'):.3f}",
    ]
    return "\n".join(lines) + "\n"


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixture-backed self-reflection promotion gate.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        action="append",
        default=None,
        help=(
            "Path to reflection promotion gate cases JSON. May be repeated. "
            "Defaults to fixture and store-fixed candidate case sets."
        ),
    )
    parser.add_argument(
        "--trace-summary",
        type=Path,
        action="append",
        default=None,
        help=(
            "Path to a promotion trace summary JSON. May be repeated. "
            "Defaults to the reviewed store-fixed trace summary fixture."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    parser.add_argument("--output", type=Path, help="Optional output file path.")
    return parser.parse_args(argv)


def _write_output(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_gate_suite(cases_paths=args.cases, trace_summary_paths=args.trace_summary)
    if args.format == "json":
        rendered = f"{json.dumps(result, ensure_ascii=False, indent=2)}\n"
    else:
        rendered = render_text(result)
    if args.output:
        _write_output(args.output, rendered)
    print(rendered, end="")
    return 0 if result.get("status") == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
