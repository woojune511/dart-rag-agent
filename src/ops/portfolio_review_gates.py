"""Run the reviewer-facing portfolio gate bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""} and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ops.portfolio_demo import build_demo
from src.ops.promotion_trace_materiality_gate import run_gate as run_trace_materiality_gate
from src.ops.reference_note_capability_gate import run_gate as run_reference_note_gate
from src.ops.reflection_promotion_gate import run_gate_suite
from src.ops.report_cache_promotion_evidence_gate import run_gate as run_cache_promotion_gate
from src.ops.review_report_cache_index_contract import run_review


REVIEW_SURFACE_READY_STATUS = "review_surface_ready"


def _is_successful_gate_state(value: Any) -> bool:
    return str(value or "").strip() in {
        "ready",
        "ok",
        "fixture_contract_ready",
    }


def run_review_gates() -> Dict[str, Any]:
    portfolio_demo = build_demo()
    cache_review = run_review()
    cache_promotion = run_cache_promotion_gate()
    reflection_gate = run_gate_suite()
    reference_note = run_reference_note_gate()
    trace_materiality = run_trace_materiality_gate()
    portfolio_readiness = dict(portfolio_demo.get("readiness") or {})
    portfolio_checks = dict(portfolio_readiness.get("checks") or {})
    checks = {
        "portfolio_demo_fixture_contract_ready": _is_successful_gate_state(
            portfolio_readiness.get("status")
        ),
        "cache_reviewer_ok": str(cache_review.get("status") or "") == "ok",
        "cache_handoff_ready": _is_successful_gate_state(
            dict(cache_review.get("reviewer_handoff") or {}).get("status")
        ),
        "cache_promotion_evidence_ready": _is_successful_gate_state(
            cache_promotion.get("status")
        ),
        "reflection_promotion_ready": _is_successful_gate_state(
            reflection_gate.get("status")
        ),
        "reference_note_capability_ready": _is_successful_gate_state(
            reference_note.get("status")
        ),
        "promotion_trace_materiality_ready": _is_successful_gate_state(
            trace_materiality.get("status")
        ),
    }
    status = REVIEW_SURFACE_READY_STATUS if all(checks.values()) else "needs_review"
    return {
        "status": status,
        "scope": "review_surface_only",
        "publication_validation": {
            "status": "not_run",
            "unit_tests": "not_run",
            "runtime_domain_term_audit": "not_run",
            "publication_ready": None,
            "note": (
                "This command validates the reviewer-facing fixture and optional "
                "capability surfaces only; run unit tests and the runtime-domain "
                "audit separately for publication validation."
            ),
        },
        "checks": checks,
        "portfolio_demo": {
            "readiness": portfolio_readiness.get("status"),
            "scope": portfolio_readiness.get("scope"),
            "fixture_evidence": dict(portfolio_demo.get("fixture_evidence") or {}).get(
                "status"
            ),
            "contract_check_count": len(portfolio_checks),
            "contract_checks_passed": sum(
                1 for value in portfolio_checks.values() if value is True
            ),
            "task_artifact_integrity": dict(
                portfolio_demo.get("task_artifact_integrity") or {}
            ).get("integrity_status"),
            "critic_acceptance": dict(portfolio_demo.get("critic_acceptance") or {}).get("status"),
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
        "reference_note_capability": {
            "status": reference_note.get("status"),
            "owner": dict(reference_note.get("capability") or {}).get("owner"),
            "graph_relation": dict(reference_note.get("capability") or {}).get("graph_relation"),
            "artifact_kind": dict(reference_note.get("capability") or {}).get("artifact_kind"),
            "disabled_flags_ok": bool(reference_note.get("disabled_flags_ok")),
        },
        "promotion_trace_materiality": {
            "status": trace_materiality.get("status"),
            "summary_count": trace_materiality.get("summary_count"),
            "source_types": list(trace_materiality.get("source_types") or []),
            "reflection_actions": list(trace_materiality.get("reflection_actions") or []),
            "cache_fallback_reasons": list(trace_materiality.get("cache_fallback_reasons") or []),
            "materiality_ok": bool(trace_materiality.get("materiality_ok")),
        },
    }


def render_text(result: Dict[str, Any]) -> str:
    portfolio = dict(result.get("portfolio_demo") or {})
    cache = dict(result.get("cache_reviewer") or {})
    cache_promotion = dict(result.get("cache_promotion_evidence") or {})
    reflection = dict(result.get("reflection_promotion") or {})
    reference_note = dict(result.get("reference_note_capability") or {})
    trace_materiality = dict(result.get("promotion_trace_materiality") or {})
    publication_validation = dict(result.get("publication_validation") or {})
    signals = dict(reflection.get("promotion_signals") or {})
    lines = [
        "# Portfolio Review Gates",
        "",
        f"Status: {result.get('status')}",
        f"Scope: {result.get('scope')}",
        f"Publication Validation: {publication_validation.get('status')}",
        f"  - unit_tests: {publication_validation.get('unit_tests')}",
        (
            "  - runtime_domain_term_audit: "
            f"{publication_validation.get('runtime_domain_term_audit')}"
        ),
        f"  - note: {publication_validation.get('note')}",
        "",
        "Portfolio Demo:",
        f"  - readiness: {portfolio.get('readiness')}",
        f"  - scope: {portfolio.get('scope')}",
        f"  - fixture_evidence: {portfolio.get('fixture_evidence')}",
        (
            "  - contract_checks_passed: "
            f"{portfolio.get('contract_checks_passed')}/"
            f"{portfolio.get('contract_check_count')}"
        ),
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
        "",
        "REFERENCE_NOTE Capability:",
        f"  - status: {reference_note.get('status')}",
        f"  - owner: {reference_note.get('owner')}",
        f"  - graph_relation: {reference_note.get('graph_relation')}",
        f"  - artifact_kind: {reference_note.get('artifact_kind')}",
        f"  - disabled_flags_ok: {str(bool(reference_note.get('disabled_flags_ok'))).lower()}",
        "",
        "Promotion Trace Materiality:",
        f"  - status: {trace_materiality.get('status')}",
        f"  - summary_count: {trace_materiality.get('summary_count')}",
        f"  - source_types: {', '.join(list(trace_materiality.get('source_types') or []))}",
        f"  - reflection_actions: {', '.join(list(trace_materiality.get('reflection_actions') or []))}",
        f"  - materiality_ok: {str(bool(trace_materiality.get('materiality_ok'))).lower()}",
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
    return 0 if result.get("status") == REVIEW_SURFACE_READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
