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

from src.ops.portfolio_fixture_contract import evaluate_fixture_contract
from src.ops.review_report_cache_index_contract import run_review


DEFAULT_DEMO_PAYLOAD_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "portfolio_demo" / "demo_payload.json"
)
DEFAULT_DEMO_EVIDENCE_MANIFEST_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "portfolio_demo"
    / "evidence_manifest.json"
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


def build_demo(
    *,
    demo_payload_path: str | Path = DEFAULT_DEMO_PAYLOAD_PATH,
    evidence_manifest_path: str | Path = DEFAULT_DEMO_EVIDENCE_MANIFEST_PATH,
    include_cache_review: bool = False,
) -> Dict[str, Any]:
    payload_path = Path(demo_payload_path)
    manifest_path = Path(evidence_manifest_path)
    payload = _read_json_object(payload_path)
    answer_package = dict(payload.get("answer_package") or {})
    fixture_contract = evaluate_fixture_contract(
        answer_package=answer_package,
        manifest_path=manifest_path,
        payload_path=payload_path,
    )
    cache_review = run_review() if include_cache_review else None
    return {
        "demo_id": payload.get("demo_id"),
        "question": payload.get("question"),
        "source_payload": str(payload_path),
        "fixture_evidence": dict(fixture_contract.get("fixture_evidence") or {}),
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
        "task_artifact_integrity": dict(
            fixture_contract.get("task_artifact_integrity") or {}
        ),
        "critic_acceptance": dict(
            fixture_contract.get("critic_acceptance") or {}
        ),
        "cache_reviewer_handoff": (
            dict(cache_review.get("reviewer_handoff") or {}) if cache_review else None
        ),
        "readiness": dict(fixture_contract.get("readiness") or {}),
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
    fixture_evidence = dict(demo.get("fixture_evidence") or {})
    readiness_checks = dict(readiness.get("checks") or {})

    lines = [
        "# Portfolio Runtime Demo",
        "",
        f"Fixture Contract Readiness: {readiness.get('status')}",
        "Scope: checked-in fixture contract; this command does not replay a live runtime run",
        f"Question: {demo.get('question')}",
        f"Answer: {demo.get('answer')}",
        "",
        "Fixture Evidence:",
        f"  - status: {fixture_evidence.get('status')}",
        f"  - evidence_kind: {fixture_evidence.get('evidence_kind')}",
        (
            "  - upstream_artifact_availability: "
            f"{fixture_evidence.get('upstream_artifact_availability')}"
        ),
        (
            "  - fixture_sha256_matches: "
            f"{_format_bool(fixture_evidence.get('fixture_sha256_matches'))}"
        ),
        "  - limitations:",
        *_format_list(
            [str(item) for item in fixture_evidence.get("limitations") or []]
        ),
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
            "",
            "Cross-Surface Contract Checks:",
            *[
                f"  - {name}: {_format_bool(value)}"
                for name, value in readiness_checks.items()
            ],
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
        "--evidence-manifest",
        type=Path,
        default=DEFAULT_DEMO_EVIDENCE_MANIFEST_PATH,
        help="Evidence manifest containing the SHA-256 fixture binding.",
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
        evidence_manifest_path=args.evidence_manifest,
        include_cache_review=args.include_cache_review,
    )
    if args.format == "json":
        rendered = f"{json.dumps(demo, ensure_ascii=False, indent=2)}\n"
    else:
        rendered = render_text(demo)

    if args.output:
        _write_output(args.output, rendered)
    print(rendered, end="")
    return (
        0
        if dict(demo.get("readiness") or {}).get("status")
        == "fixture_contract_ready"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
