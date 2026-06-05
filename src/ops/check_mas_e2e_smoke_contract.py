"""Compare MAS E2E smoke outputs on their stable contract fields."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalise_status(value: Any) -> str:
    text = str(value or "").strip()
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text.lower()


def _status_counts(task_statuses: Dict[str, Any]) -> Dict[str, int]:
    counts = Counter(_normalise_status(status) for status in dict(task_statuses or {}).values())
    counts.pop("", None)
    return dict(sorted(counts.items()))


def extract_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return the stable smoke-regression surface from a full smoke payload."""
    summary = dict(payload.get("summary") or {})
    cases = []
    for index, case in enumerate(list(payload.get("cases") or []), start=1):
        final_report_record = dict(case.get("final_report_record") or {})
        cases.append(
            {
                "index": index,
                "query": str(case.get("query") or ""),
                "final_report_status": _normalise_status(final_report_record.get("status")),
                "task_artifact_integrity_status": _normalise_status(
                    case.get("task_artifact_integrity_status")
                ),
                "task_count": int(case.get("task_count", 0) or 0),
                "task_status_counts": _status_counts(dict(case.get("task_statuses") or {})),
                "replan_count": int(case.get("replan_count", 0) or 0),
                "replan_routed": bool(case.get("replan_routed")),
            }
        )

    return {
        "embedding_compatibility_status": _normalise_status(
            dict(payload.get("embedding_compatibility") or {}).get("status")
        ),
        "case_count": int(payload.get("case_count", 0) or 0),
        "blocked_count": int(summary.get("blocked_count", 0) or 0),
        "integrity_error_count": int(summary.get("integrity_error_count", 0) or 0),
        "replan_routed_count": int(summary.get("replan_routed_count", 0) or 0),
        "cases": cases,
    }


def _as_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "contract" in payload and isinstance(payload["contract"], dict):
        return dict(payload["contract"])
    if "embedding_compatibility" in payload or "summary" in payload:
        return extract_contract(payload)
    return dict(payload)


def compare_contracts(current: Dict[str, Any], baseline: Dict[str, Any]) -> List[Dict[str, Any]]:
    differences: List[Dict[str, Any]] = []

    def walk(path: str, actual: Any, expected: Any) -> None:
        if isinstance(actual, dict) and isinstance(expected, dict):
            keys = sorted(set(actual) | set(expected))
            for key in keys:
                walk(f"{path}.{key}" if path else str(key), actual.get(key), expected.get(key))
            return
        if isinstance(actual, list) and isinstance(expected, list):
            max_len = max(len(actual), len(expected))
            for index in range(max_len):
                actual_item = actual[index] if index < len(actual) else None
                expected_item = expected[index] if index < len(expected) else None
                walk(f"{path}[{index}]", actual_item, expected_item)
            return
        if actual != expected:
            differences.append({"path": path, "baseline": expected, "current": actual})

    walk("", current, baseline)
    return differences


def check_contract(current_payload: Dict[str, Any], baseline_payload: Dict[str, Any]) -> Dict[str, Any]:
    current = _as_contract(current_payload)
    baseline = _as_contract(baseline_payload)
    differences = compare_contracts(current=current, baseline=baseline)
    return {
        "status": "ok" if not differences else "mismatch",
        "difference_count": len(differences),
        "differences": differences,
        "current_contract": current,
        "baseline_contract": baseline,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare MAS E2E smoke contract fields.")
    parser.add_argument("--current", type=Path, required=True, help="Current mas_e2e_smoke JSON output.")
    parser.add_argument("--baseline", type=Path, required=True, help="Baseline full output or compact contract JSON.")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write the current compact contract to --baseline instead of comparing.",
    )
    parser.add_argument("--output", type=Path, help="Optional path for the comparison/check JSON.")
    args = parser.parse_args()

    current_payload = _read_json(args.current)
    if args.write_baseline:
        contract = extract_contract(current_payload)
        _write_json(args.baseline, contract)
        result = {
            "status": "baseline_written",
            "baseline": str(args.baseline),
            "current": str(args.current),
            "contract": contract,
        }
        if args.output:
            _write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    result = check_contract(current_payload=current_payload, baseline_payload=_read_json(args.baseline))
    if args.output:
        _write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
