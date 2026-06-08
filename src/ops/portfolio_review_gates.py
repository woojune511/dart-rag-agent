"""Run the reviewer-facing portfolio gate bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from src.ops.portfolio_demo import build_demo
from src.ops.reflection_promotion_gate import run_gate_suite
from src.ops.report_cache_promotion_evidence_gate import run_gate as run_cache_promotion_gate
from src.ops.review_report_cache_index_contract import run_review


def _is_ready(value: Any) -> bool:
    return str(value or "").strip() in {"ready", "ok"}


def run_review_gates() -> Dict[str, Any]:
    portfolio_demo = build_demo()
    cache_review = run_review()
    cache_promotion = run_cache_promotion_gate()
    reflection_gate = run_gate_suite()
    checks = {
        "portfolio_demo_ready": _is_ready(
            dict(portfolio_demo.get("readiness") or {}).get("status")
        ),
        "cache_reviewer_ok": str(cache_review.get("status") or "") == "ok",
        "cache_handoff_ready": _is_ready(
            dict(cache_review.get("reviewer_handoff") or {}).get("status")
        ),
        "cache_promotion_evidence_ready": _is_ready(cache_promotion.get("status")),
        "reflection_promotion_ready": _is_ready(reflection_gate.get("status")),
    }
    status = "ready" if all(checks.values()) else "needs_review"
    return {
        "status": status,
        "checks": checks,
        "portfolio_demo": {
            "readiness": dict(portfolio_demo.get("readiness") or {}).get("status"),
            "task_artifact_integrity": dict(
                portfolio_demo.get("task_artifact_integrity") or {}
            ).get("integrity_status"),
            "critic_acceptance": dict(portfolio_demo.get("critic_acceptance") or {}).get("status"),
            "cache_reviewer_handoff": dict(
                portfolio_demo.get("cache_reviewer_handoff") or {}
            ).get("status"),
        },
        "cache_reviewer": {
            "status": cache_review.get("status"),
            "difference_count": cache_review.get("difference_count"),
            "reviewer_handoff_status": dict(
                cache_review.get("reviewer_handoff") or {}
            ).get("status"),
            "mode": dict(cache_review.get("reviewer_handoff") or {}).get("mode"),
            "producer_policy_ready_count": dict(
                cache_review.get("reviewer_handoff") or {}
            ).get("producer_policy_ready_count"),
            "producer_policy_fallback_count": dict(
                cache_review.get("reviewer_handoff") or {}
            ).get("producer_policy_fallback_count"),
            "serving_enabled": bool(
                dict(cache_review.get("reviewer_handoff") or {}).get("serving_enabled")
            ),
            "ledger_insertion_enabled": bool(
                dict(cache_review.get("reviewer_handoff") or {}).get(
                    "ledger_insertion_enabled"
                )
            ),
        },
        "cache_promotion_evidence": {
            "status": cache_promotion.get("status"),
            "scenario_count": cache_promotion.get("scenario_count"),
            "ready_count": cache_promotion.get("ready_count"),
            "fallback_count": cache_promotion.get("fallback_count"),
            "disabled_flags_ok": bool(cache_promotion.get("disabled_flags_ok")),
            "producer_contract_ok": bool(cache_promotion.get("producer_contract_ok")),
            "fallback_safety_ok": bool(cache_promotion.get("fallback_safety_ok")),
            "trace_summary_count": cache_promotion.get("trace_summary_count"),
        },
        "reflection_promotion": {
            "status": reflection_gate.get("status"),
            "fixture_count": reflection_gate.get("fixture_count"),
            "case_count": reflection_gate.get("case_count"),
            "trace_summary_count": reflection_gate.get("trace_summary_count"),
            "source_coverage_ok": bool(reflection_gate.get("source_coverage_ok")),
            "report_contract_ok": bool(reflection_gate.get("report_contract_ok")),
            "promotion_signals": dict(reflection_gate.get("promotion_signals") or {}),
        },
    }


def render_text(result: Dict[str, Any]) -> str:
    portfolio = dict(result.get("portfolio_demo") or {})
    cache = dict(result.get("cache_reviewer") or {})
    cache_promotion = dict(result.get("cache_promotion_evidence") or {})
    reflection = dict(result.get("reflection_promotion") or {})
    signals = dict(reflection.get("promotion_signals") or {})
    lines = [
        "# Portfolio Review Gates",
        "",
        f"Status: {result.get('status')}",
        "",
        "Portfolio Demo:",
        f"  - readiness: {portfolio.get('readiness')}",
        f"  - task_artifact_integrity: {portfolio.get('task_artifact_integrity')}",
        f"  - critic_acceptance: {portfolio.get('critic_acceptance')}",
        "",
        "Cache Reviewer:",
        f"  - status: {cache.get('status')}",
        f"  - reviewer_handoff_status: {cache.get('reviewer_handoff_status')}",
        f"  - mode: {cache.get('mode')}",
        f"  - producer_policy_ready_count: {cache.get('producer_policy_ready_count')}",
        f"  - producer_policy_fallback_count: {cache.get('producer_policy_fallback_count')}",
        "",
        "Cache Promotion Evidence:",
        f"  - status: {cache_promotion.get('status')}",
        f"  - scenario_count: {cache_promotion.get('scenario_count')}",
        f"  - ready_count: {cache_promotion.get('ready_count')}",
        f"  - fallback_count: {cache_promotion.get('fallback_count')}",
        f"  - disabled_flags_ok: {str(bool(cache_promotion.get('disabled_flags_ok'))).lower()}",
        f"  - producer_contract_ok: {str(bool(cache_promotion.get('producer_contract_ok'))).lower()}",
        f"  - fallback_safety_ok: {str(bool(cache_promotion.get('fallback_safety_ok'))).lower()}",
        f"  - trace_summary_count: {cache_promotion.get('trace_summary_count')}",
        "",
        "Reflection Promotion:",
        f"  - status: {reflection.get('status')}",
        f"  - fixture_count: {reflection.get('fixture_count')}",
        f"  - case_count: {reflection.get('case_count')}",
        f"  - trace_summary_count: {reflection.get('trace_summary_count')}",
        f"  - source_coverage_ok: {str(bool(reflection.get('source_coverage_ok'))).lower()}",
        f"  - report_contract_ok: {str(bool(reflection.get('report_contract_ok'))).lower()}",
        f"  - false_recovery_rate: {signals.get('false_recovery_rate'):.3f}",
        f"  - integrity_preservation_rate: {signals.get('integrity_preservation_rate'):.3f}",
    ]
    return "\n".join(lines) + "\n"


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the reviewer-facing portfolio gate bundle.",
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
    result = run_review_gates()
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
