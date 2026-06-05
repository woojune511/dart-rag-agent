"""Compare report-cache index smoke outputs on stable handoff fields."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _as_int(value: Any) -> int:
    return int(value or 0)


def _candidate_artifact_contract(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    artifact = item.get("artifact")
    artifact_payload = dict(artifact.get("payload_summary") or {}) if isinstance(artifact, dict) else {}
    return {
        "index": index,
        "status": str(item.get("status") or ""),
        "ready": bool(item.get("ready")),
        "serving_enabled": bool(item.get("serving_enabled")),
        "has_artifact": isinstance(artifact, dict),
        "artifact_status": str(artifact.get("status") or "") if isinstance(artifact, dict) else "",
        "artifact_kind": str(artifact.get("kind") or "") if isinstance(artifact, dict) else "",
        "answer_present": bool(str(artifact_payload.get("answer") or "").strip()),
        "citation_count": _as_int(artifact_payload.get("citation_count")),
        "evidence_item_count": _as_int(artifact_payload.get("evidence_item_count")),
        "has_structured_result": bool(artifact_payload.get("has_structured_result")),
        "has_resolved_calculation_trace": bool(artifact_payload.get("has_resolved_calculation_trace")),
        "calculation_operand_count": _as_int(artifact_payload.get("calculation_operand_count")),
        "artifact_serving_enabled": bool(artifact_payload.get("serving_enabled")),
    }


def extract_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return stable fields from a report_cache_index_smoke payload."""
    summary = dict(payload.get("summary") or {})
    candidate_artifacts = dict(payload.get("rehydrated_candidate_artifacts") or {})
    candidate_items = [
        _candidate_artifact_contract(dict(item or {}), index)
        for index, item in enumerate(list(candidate_artifacts.get("items") or []), start=1)
        if isinstance(item, dict)
    ]
    return {
        "status": str(summary.get("status") or ""),
        "enabled": bool(summary.get("enabled")),
        "serving_enabled": bool(summary.get("serving_enabled")),
        "match_count": _as_int(summary.get("match_count")),
        "readable_match_count": _as_int(summary.get("readable_match_count")),
        "rehydration_ready_match_count": _as_int(summary.get("rehydration_ready_match_count")),
        "rehydration_blocked_match_count": _as_int(summary.get("rehydration_blocked_match_count")),
        "rehydration_reason_counts": dict(sorted(dict(summary.get("rehydration_reason_counts") or {}).items())),
        "index_status": str(summary.get("index_status") or ""),
        "index_readable_count": _as_int(summary.get("index_readable_count")),
        "index_rehydration_ready_count": _as_int(summary.get("index_rehydration_ready_count")),
        "index_blocked_count": _as_int(summary.get("index_blocked_count")),
        "index_malformed_count": _as_int(summary.get("index_malformed_count")),
        "rehydrated_candidate_artifact_count": _as_int(summary.get("rehydrated_candidate_artifact_count")),
        "rehydrated_candidate_artifact_blocked_count": _as_int(
            summary.get("rehydrated_candidate_artifact_blocked_count")
        ),
        "candidate_artifacts": candidate_items,
    }


def _as_contract(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "contract" in payload and isinstance(payload["contract"], dict):
        return dict(payload["contract"])
    if "summary" in payload or "rehydrated_candidate_artifacts" in payload:
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
    parser = argparse.ArgumentParser(description="Compare report-cache index smoke contract fields.")
    parser.add_argument("--current", type=Path, required=True, help="Current report_cache_index_smoke JSON output.")
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
