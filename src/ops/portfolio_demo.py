"""Render a fixture-backed portfolio demo for the runtime contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""} and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.financial_artifact_contracts import critic_report_runtime_acceptance_state
from src.ops.review_report_cache_index_contract import run_review


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
) -> Dict[str, Any]:
    semantic_plan = dict(answer_package.get("semantic_plan") or {})
    retrieval_trace = dict(answer_package.get("retrieval_debug_trace") or {})
    trace = dict(answer_package.get("resolved_calculation_trace") or {})
    calculation_result = dict(trace.get("calculation_result") or {})
    checks = {
        "answer_present": bool(str(answer_package.get("answer") or "").strip()),
        "citations_present": bool(answer_package.get("citations") or []),
        "semantic_plan_present": bool(semantic_plan.get("tasks") or []),
        "retrieval_trace_present": bool(retrieval_trace.get("query_bundle") or [])
        and int(retrieval_trace.get("selected_count") or 0) > 0,
        "calculation_trace_ok": calculation_result.get("status") == "ok",
        "task_artifact_integrity_ok": task_artifact.get("integrity_status") == "ok",
        "critic_accepted": critic_acceptance.get("status") == "accepted",
    }
    return {
        "status": "ready" if all(checks.values()) else "needs_review",
        "checks": checks,
    }


def build_demo(
    *,
    demo_payload_path: str | Path = DEFAULT_DEMO_PAYLOAD_PATH,
    include_cache_review: bool = False,
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
        "semantic_plan": dict(answer_package.get("semantic_plan") or {}),
        "retrieval_queries": list(answer_package.get("retrieval_queries") or []),
        "retrieval_debug_trace": dict(
            answer_package.get("retrieval_debug_trace") or {}
        ),
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
        ),
    }


def _format_list(items: List[str]) -> List[str]:
    return [f"  - {item}" for item in items] if items else ["  - -"]


def _format_bool(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def render_text(demo: Dict[str, Any]) -> str:
    semantic_plan = dict(demo.get("semantic_plan") or {})
    semantic_task = _first_mapping(semantic_plan.get("tasks"))
    semantic_operands = [
        dict(item)
        for item in list(semantic_task.get("required_operands") or [])
        if isinstance(item, dict)
    ]
    planner_notes = [str(item) for item in semantic_plan.get("planner_notes") or []]
    planner_strategy = next(
        (item for item in planner_notes if "llm" in item.lower()),
        str(semantic_plan.get("status") or "-"),
    )
    retrieval_trace = dict(demo.get("retrieval_debug_trace") or {})
    executed_query = _first_mapping(retrieval_trace.get("executed_queries"))
    search_telemetry = dict(executed_query.get("search_telemetry") or {})
    selected_chunk = _first_mapping(retrieval_trace.get("selected_chunks"))
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
        "Semantic Plan:",
        f"  - planner: {planner_strategy}",
        f"  - operation: {semantic_task.get('operation_family')}",
        "  - required_operands:",
    ]
    for operand in semantic_operands:
        lines.append(
            "    - "
            f"{operand.get('role')}: {operand.get('label')}"
        )

    lines.extend(
        [
            "",
            "Retrieval Trace:",
            f"  - mode: {search_telemetry.get('retrieval_mode')}",
            f"  - queries: {len(retrieval_trace.get('query_bundle') or [])}",
            f"  - vector_results: {search_telemetry.get('vector_result_count')}",
            f"  - bm25_results: {search_telemetry.get('bm25_result_count')}",
            f"  - candidates: {retrieval_trace.get('candidate_count')}",
            f"  - selected: {retrieval_trace.get('selected_count')}",
            (
                "  - selected_source: "
                f"{selected_chunk.get('section_path')} [{selected_chunk.get('chunk_uid')}]"
            ),
            "",
            "Calculation Trace:",
            f"  - operation: {plan.get('operation')}",
            f"  - result: {result.get('rendered_value')} ({result.get('status')})",
            "  - operands:",
        ]
    )
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
        ]
    )
    if cache_handoff:
        lines.extend(
            [
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
    cache_group = parser.add_mutually_exclusive_group()
    cache_group.add_argument(
        "--include-cache-review",
        action="store_true",
        help="Also run and render the optional candidate-only cache review.",
    )
    cache_group.add_argument(
        "--skip-cache-review",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--output", type=Path, help="Optional output file path.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    demo = build_demo(
        demo_payload_path=args.demo_payload,
        include_cache_review=args.include_cache_review,
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
