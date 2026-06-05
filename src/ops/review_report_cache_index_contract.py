"""Run the report-cache index reviewer contract check with repo defaults."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from src.ops.check_report_cache_index_smoke_contract import check_contract
from src.ops.report_cache_index_smoke import build_smoke_payload


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_CACHE_INDEX_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "report_cache_index" / "rehydration_diagnostics.json"
)
DEFAULT_BASELINE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "report_cache_index" / "rehydration_contract_baseline.json"
)


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n", encoding="utf-8")


def _parse_key_json(value: str) -> Dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"invalid JSON key: {exc}") from exc
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("key JSON must be an object")
    return dict(payload)


def _reviewer_handoff_summary(contract: Dict[str, Any], *, status: str) -> Dict[str, Any]:
    candidate_artifacts = [
        dict(item)
        for item in list(contract.get("candidate_artifacts") or [])
        if isinstance(item, dict)
    ]
    serving_flags = [
        bool(contract.get("serving_enabled")),
        *[bool(item.get("serving_enabled")) for item in candidate_artifacts],
        *[bool(item.get("artifact_serving_enabled")) for item in candidate_artifacts],
        *[bool(item.get("calculation_projection_serving_enabled")) for item in candidate_artifacts],
    ]
    ledger_insertion_flags = [
        bool(item.get("calculation_projection_ledger_insertion_enabled"))
        for item in candidate_artifacts
    ]
    projection_ready_count = sum(
        1
        for item in candidate_artifacts
        if bool(item.get("calculation_projection_valid_for_contract"))
    )
    fallback_count = sum(
        1
        for item in candidate_artifacts
        if bool(item.get("calculation_projection_fallback_required"))
    )
    candidate_only_ready = (
        status == "ok"
        and not any(serving_flags)
        and not any(ledger_insertion_flags)
        and projection_ready_count > 0
        and fallback_count > 0
    )
    return {
        "status": "ready" if candidate_only_ready else "needs_review",
        "mode": "candidate_only",
        "serving_enabled": any(serving_flags),
        "ledger_insertion_enabled": any(ledger_insertion_flags),
        "projection_ready_count": projection_ready_count,
        "fallback_count": fallback_count,
        "review_note": (
            "Candidate-only reviewer contract is ready; cache serving, ledger insertion, "
            "and retrieval bypass remain disabled."
            if candidate_only_ready
            else "Review the contract diff or disabled-flag/projection counts before handoff."
        ),
    }


def run_review(
    *,
    report_cache_index_path: str | Path = DEFAULT_REPORT_CACHE_INDEX_PATH,
    baseline_path: str | Path = DEFAULT_BASELINE_PATH,
    key: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    index_path = Path(report_cache_index_path)
    baseline = Path(baseline_path)
    current_payload = build_smoke_payload(report_cache_index_path=index_path, key=key)
    result = check_contract(current_payload=current_payload, baseline_payload=_read_json(baseline))
    reviewer_handoff = _reviewer_handoff_summary(
        result["current_contract"],
        status=str(result["status"] or ""),
    )
    return {
        "status": result["status"],
        "difference_count": result["difference_count"],
        "reviewer_handoff": reviewer_handoff,
        "report_cache_index_path": str(index_path),
        "baseline": str(baseline),
        "differences": result["differences"],
        "current_contract": result["current_contract"],
        "baseline_contract": result["baseline_contract"],
    }


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixture-backed report-cache index contract review check.",
    )
    parser.add_argument(
        "--report-cache-index-path",
        type=Path,
        default=DEFAULT_REPORT_CACHE_INDEX_PATH,
        help="Path to a local_cache_index JSON or JSONL file.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help="Baseline full output or compact contract JSON.",
    )
    parser.add_argument(
        "--key-json",
        type=_parse_key_json,
        default=None,
        help="Optional report-cache key object. Defaults to the first entry key in the index.",
    )
    parser.add_argument("--output", type=Path, help="Optional path for the review JSON.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_review(
        report_cache_index_path=args.report_cache_index_path,
        baseline_path=args.baseline,
        key=args.key_json,
    )
    if args.output:
        _write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
