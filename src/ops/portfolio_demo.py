"""Render a fixture-backed portfolio demo for the runtime contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from src.experimental.mas.types import critic_report_runtime_acceptance_state
from src.ops.review_report_cache_index_contract import run_review


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEMO_PAYLOAD_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "portfolio_demo" / "demo_payload.json"
)


def _read_json_object(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"demo payload must be a JSON object: {path}")
    return dict(payload)


def _first_mapping(items: Any) -> Dict[str, Any]:
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                return dict(item)
    return {}


def _summarize_task_artifact_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "integrity_status": trace.get("integrity_status"),
        "integrity_issue_count": int(trace.get("integrity_issue_count") or 0),
        "task_count": int(trace.get("task_count") or 0),
        "artifact_count": int(trace.get("artifact_count") or 0),
        "missing_artifact_ids": list(trace.get("missing_artifact_ids") or []),
        "orphan_artifact_ids": list(trace.get("orphan_artifact_ids") or []),
        "integrity_issues": list(trace.get("integrity_issues") or []),
    }


def _summarize_critic_acceptance(report: Dict[str, Any]) -> Dict[str, Any]:
    acceptance = critic_report_runtime_acceptance_state(dict(report))
    blocking_issues = list(report.get("blocking_issues") or [])
    target_artifact_ids = list(report.get("target_artifact_ids") or [])
    return {
        "status": acceptance.get("runtime_acceptance_status"),
        "verdict": report.get("verdict"),
        "target_task_id": report.get("target_task_id"),
        "target_artifact_ids": target_artifact_ids,
        "target_refs": list(acceptance.get("target_refs") or []),
        "acceptance_reason": str(report.get("acceptance_reason") or ""),
        "blocking_issues": blocking_issues,
        "runtime_acceptance_reasons": list(acceptance.get("reasons") or []),
        "deterministic_score": acceptance.get("deterministic_score"),
        "deterministic_score_used_for_acceptance": bool(
            acceptance.get("deterministic_score_used_for_acceptance")
        ),
    }


def _checks(
    *,
    answer_package: Dict[str, Any],
    task_artifact: Dict[str, Any],
    critic_acceptance: Dict[str, Any],
    cache_review: Dict[str, Any] | None,
) -> Dict[str, Any]:
    trace = dict(answer_package.get("resolved_calculation_trace") or {})
    calculation_result = dict(trace.get("calculation_result") or {})
    checks = {
        "answer_present": bool(str(answer_package.get("answer") or "").strip()),
        "citations_present": bool(answer_package.get("citations") or []),
        "calculation_trace_ok": calculation_result.get("status") == "ok",
        "task_artifact_integrity_ok": task_artifact.get("integrity_status") == "ok",
        "critic_accepted": critic_acceptance.get("status") == "accepted",
        "cache_reviewer_ready": (
            cache_review is None
            or dict(cache_review.get("reviewer_handoff") or {}).get("status") == "ready"
        ),
    }
    return {
        "status": "ready" if all(checks.values()) else "needs_review",
        "checks": checks,
    }


def build_demo(
    *,
    demo_payload_path: str | Path = DEFAULT_DEMO_PAYLOAD_PATH,
    include_cache_review: bool = True,
) -> Dict[str, Any]:
    payload_path = Path(demo_payload_path)
    payload = _read_json_object(payload_path)
    answer_package = dict(payload.get("answer_package") or {})
    task_artifact = _summarize_task_artifact_trace(
        dict(answer_package.get("task_artifact_trace") or {})
    )
    critic_acceptance = _summarize_critic_acceptance(
        _first_mapping(answer_package.get("critic_reports"))
    )
    cache_review = run_review() if include_cache_review else None
    return {
        "demo_id": payload.get("demo_id"),
        "question": payload.get("question"),
        "source_payload": str(payload_path),
        "answer": answer_package.get("answer"),
        "citations": list(answer_package.get("citations") or []),
        "evidence_items": list(answer_package.get("evidence_items") or []),
        "structured_result": dict(answer_package.get("structured_result") or {}),
        "resolved_calculation_trace": dict(
            answer_package.get("resolved_calculation_trace") or {}
        ),
        "task_artifact_integrity": task_artifact,
        "critic_acceptance": critic_acceptance,
        "cache_reviewer_handoff": (
            dict(cache_review.get("reviewer_handoff") or {}) if cache_review else None
        ),
        "readiness": _checks(
            answer_package=answer_package,
            task_artifact=task_artifact,
            critic_acceptance=critic_acceptance,
            cache_review=cache_review,
        ),
    }


def _format_list(items: List[str]) -> List[str]:
    return [f"  - {item}" for item in items] if items else ["  - -"]


def _format_bool(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def render_text(demo: Dict[str, Any]) -> str:
    trace = dict(demo.get("resolved_calculation_trace") or {})
    plan = dict(trace.get("calculation_plan") or {})
    result = dict(trace.get("calculation_result") or {})
    operands = [
        dict(item)
        for item in list(trace.get("calculation_operands") or [])
        if isinstance(item, dict)
    ]
    task_artifact = dict(demo.get("task_artifact_integrity") or {})
    critic = dict(demo.get("critic_acceptance") or {})
    cache_handoff = dict(demo.get("cache_reviewer_handoff") or {})
    readiness = dict(demo.get("readiness") or {})

    lines = [
        "# Portfolio Runtime Demo",
        "",
        f"Readiness: {readiness.get('status')}",
        f"Question: {demo.get('question')}",
        f"Answer: {demo.get('answer')}",
        "",
        "Citations:",
        *_format_list([str(item) for item in demo.get("citations") or []]),
        "",
        "Calculation Trace:",
        f"  - operation: {plan.get('operation')}",
        f"  - result: {result.get('rendered_value')} ({result.get('status')})",
        "  - operands:",
    ]
    for operand in operands:
        lines.append(
            "    - "
            f"{operand.get('label')}: {operand.get('raw_value')} "
            f"from {operand.get('source_anchor')}"
        )

    lines.extend(
        [
            "",
            "Task/Artifact Integrity:",
            f"  - status: {task_artifact.get('integrity_status')}",
            f"  - tasks: {task_artifact.get('task_count')}",
            f"  - artifacts: {task_artifact.get('artifact_count')}",
            f"  - issue_count: {task_artifact.get('integrity_issue_count')}",
            "",
            "Critic Acceptance:",
            f"  - status: {critic.get('status')}",
            f"  - target_task_id: {critic.get('target_task_id')}",
            f"  - target_artifact_ids: {', '.join(critic.get('target_artifact_ids') or [])}",
            f"  - reason: {critic.get('acceptance_reason') or '-'}",
            "",
            "Cache Reviewer Handoff:",
            f"  - status: {cache_handoff.get('status')}",
            f"  - mode: {cache_handoff.get('mode')}",
            (
                "  - retrieval_bypass_enabled: "
                f"{_format_bool(cache_handoff.get('retrieval_bypass_enabled'))}"
            ),
            f"  - write_enabled: {_format_bool(cache_handoff.get('write_enabled'))}",
            f"  - serving_enabled: {_format_bool(cache_handoff.get('serving_enabled'))}",
            (
                "  - ledger_insertion_enabled: "
                f"{_format_bool(cache_handoff.get('ledger_insertion_enabled'))}"
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def _write_output(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the fixture-backed portfolio runtime demo.",
    )
    parser.add_argument(
        "--demo-payload",
        type=Path,
        default=DEFAULT_DEMO_PAYLOAD_PATH,
        help="Fixture JSON containing the representative runtime projection.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--skip-cache-review",
        action="store_true",
        help="Render the demo without running the cache reviewer handoff check.",
    )
    parser.add_argument("--output", type=Path, help="Optional output file path.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    demo = build_demo(
        demo_payload_path=args.demo_payload,
        include_cache_review=not args.skip_cache_review,
    )
    if args.format == "json":
        rendered = f"{json.dumps(demo, ensure_ascii=False, indent=2)}\n"
    else:
        rendered = render_text(demo)

    if args.output:
        _write_output(args.output, rendered)
    print(rendered, end="")
    return 0 if dict(demo.get("readiness") or {}).get("status") == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
