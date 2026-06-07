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
REQUIRED_ACTIONS = {
    "retry_retrieval",
    "synthesize_from_task_outputs",
    "stop_insufficient",
}


def _read_json_object(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"reflection promotion fixture must be a JSON object: {path}")
    return dict(payload)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _case_action(case: Dict[str, Any]) -> str:
    report = case.get("reflection_report") if isinstance(case.get("reflection_report"), dict) else {}
    return str(report.get("action_taken") or case.get("expected_action") or "").strip()


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


def evaluate_cases(payload: Dict[str, Any]) -> Dict[str, Any]:
    cases = [dict(case) for case in list(payload.get("cases") or []) if isinstance(case, dict)]
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
    for case in cases:
        action = _case_action(case)
        if action:
            action_counts[action] = action_counts.get(action, 0) + 1
        expected = str(case.get("expected_action") or "").strip()
        if expected and expected != "none" and action != expected:
            action_mismatches.append(str(case.get("case_id") or "unknown"))

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
        and not action_mismatches
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
        "case_count": len(cases),
        "eligible_case_count": len(eligible_cases),
        "triggered_case_count": len(triggered_cases),
        "accepted_reflected_case_count": len(accepted_reflected_cases),
        "false_recovery_case_ids": [
            str(case.get("case_id") or "unknown") for case in false_recovery_cases
        ],
        "action_counts": action_counts,
        "action_mismatch_case_ids": action_mismatches,
        "required_actions_present": required_actions_present,
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
    return result


def render_text(result: Dict[str, Any]) -> str:
    signals = dict(result.get("promotion_signals") or {})
    lines = [
        "# Reflection Promotion Gate",
        "",
        f"Status: {result.get('status')}",
        f"Cases: {result.get('case_count')}",
        f"Required actions present: {str(result.get('required_actions_present')).lower()}",
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
        default=DEFAULT_CASES_PATH,
        help="Path to reflection promotion gate cases JSON.",
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
    result = run_gate(cases_path=args.cases)
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
