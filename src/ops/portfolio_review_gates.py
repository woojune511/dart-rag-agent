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

REVIEW_SURFACE_READY_STATUS = "review_surface_ready"


def run_review_gates() -> Dict[str, Any]:
    """Review the preserved fixture; no retired experimental capability gates."""
    portfolio_demo = build_demo()
    portfolio_readiness = dict(portfolio_demo.get("readiness") or {})
    portfolio_checks = dict(portfolio_readiness.get("checks") or {})
    ready = portfolio_readiness.get("status") == "fixture_contract_ready"
    return {
        "status": REVIEW_SURFACE_READY_STATUS if ready else "needs_review",
        "scope": "review_surface_only",
        "publication_validation": {
            "status": "not_run", "unit_tests": "not_run",
            "runtime_domain_term_audit": "not_run", "publication_ready": None,
            "note": "Fixture consistency does not establish current runtime or model quality.",
        },
        "checks": {"portfolio_demo_fixture_contract_ready": ready},
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
    }


def render_text(result: Dict[str, Any]) -> str:
    lines = ["# Portfolio Review Gates", f"Status: {result.get('status')}",
             f"Scope: {result.get('scope')}",
             f"Publication Validation: {result.get('publication_validation', {}).get('status')}"]
    for key, value in result.get("publication_validation", {}).items():
        lines.append(f"  - {key}: {value}")
    lines.extend(["", "Portfolio Demo:"])
    for key, value in result.get("portfolio_demo", {}).items():
        lines.append(f"  - {key}: {value}")
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
