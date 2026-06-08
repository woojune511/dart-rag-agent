"""Run the promotion trace summary materiality gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Set


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRACE_SUMMARY_PATHS = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "promotion_trace_summary"
    / "store_fixed_candidate_summary.json",
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "promotion_trace_summary"
    / "live_default_mas_handoff_summary.json",
)
REQUIRED_SOURCE_TYPES = {
    "store_fixed_eval_only_trace_summary",
    "live_default_mas_trace_summary",
}
REQUIRED_REFLECTION_ACTIONS = {"none", "retry_retrieval", "stop_insufficient"}
MIN_CACHE_FALLBACK_REASON_COUNT = 2
CACHE_DISABLED_FLAGS = (
    "serving_enabled",
    "ledger_insertion_enabled",
    "retrieval_bypass_enabled",
    "final_acceptance_enabled",
)


def _read_json_object(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"promotion trace summary must be a JSON object: {path}")
    return dict(payload)


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _reflection_action(case: Mapping[str, Any]) -> str:
    report = case.get("reflection_report")
    report_action = ""
    if isinstance(report, Mapping):
        report_action = str(report.get("action_taken") or "").strip()
    return report_action or str(case.get("expected_action") or "none").strip() or "none"


def _reflection_material_signature(case: Mapping[str, Any]) -> str:
    trace = case.get("task_artifact_trace")
    integrity = ""
    if isinstance(trace, Mapping):
        integrity = str(trace.get("integrity_status") or "").strip()
    parts = [
        _reflection_action(case),
        str(bool(case.get("eligible"))).lower(),
        str(bool(case.get("reflection_triggered"))).lower(),
        str(case.get("initial_status") or "").strip(),
        str(case.get("final_status") or "").strip(),
        integrity,
        str(case.get("calculation_trace_status") or "").strip(),
        str(bool(case.get("evidence_supported"))).lower(),
    ]
    return "|".join(parts)


def _cache_material_signature(case: Mapping[str, Any]) -> str:
    parts = [
        str(case.get("status") or "").strip(),
        str(bool(case.get("ready"))).lower(),
        str(bool(case.get("fallback_required"))).lower(),
        ",".join(sorted(_string_list(case.get("reasons")))),
        str(case.get("producer_policy_status") or "").strip(),
        str(bool(case.get("calculation_contract_valid"))).lower(),
    ]
    return "|".join(parts)


def _summary_review(path: Path) -> Dict[str, Any]:
    payload = _read_json_object(path)
    source_type = str(payload.get("source_type") or "").strip()
    summary_id = str(payload.get("summary_id") or path.stem).strip()
    reflection_cases = [
        dict(case)
        for case in list(payload.get("reflection_promotion_cases") or [])
        if isinstance(case, Mapping)
    ]
    cache_cases = [
        dict(case)
        for case in list(payload.get("report_cache_promotion_cases") or [])
        if isinstance(case, Mapping)
    ]
    reflection_actions = sorted({_reflection_action(case) for case in reflection_cases})
    cache_fallback_reasons = sorted(
        {
            reason
            for case in cache_cases
            if bool(case.get("fallback_required"))
            for reason in _string_list(case.get("reasons"))
        }
    )
    return {
        "path": str(path),
        "summary_id": summary_id,
        "source_type": source_type,
        "reflection_case_count": len(reflection_cases),
        "report_cache_case_count": len(cache_cases),
        "reflection_actions": reflection_actions,
        "cache_fallback_reasons": cache_fallback_reasons,
        "reflection_material_signatures": sorted(
            {_reflection_material_signature(case) for case in reflection_cases}
        ),
        "cache_material_signatures": sorted(
            {_cache_material_signature(case) for case in cache_cases}
        ),
        "cache_disabled_flags_ok": not any(
            bool(case.get(flag))
            for case in cache_cases
            for flag in CACHE_DISABLED_FLAGS
        ),
    }


def run_gate(trace_summary_paths: List[str | Path] | None = None) -> Dict[str, Any]:
    paths = [Path(path) for path in (trace_summary_paths or DEFAULT_TRACE_SUMMARY_PATHS)]
    summaries = [_summary_review(path) for path in paths]
    source_types: Set[str] = {str(item.get("source_type") or "") for item in summaries}
    summary_ids = [str(item.get("summary_id") or "") for item in summaries]
    reflection_actions: Set[str] = {
        action
        for summary in summaries
        for action in list(summary.get("reflection_actions") or [])
    }
    cache_fallback_reasons: Set[str] = {
        reason
        for summary in summaries
        for reason in list(summary.get("cache_fallback_reasons") or [])
    }
    reflection_signatures: Set[str] = {
        signature
        for summary in summaries
        for signature in list(summary.get("reflection_material_signatures") or [])
    }
    cache_signatures: Set[str] = {
        signature
        for summary in summaries
        for signature in list(summary.get("cache_material_signatures") or [])
    }

    issue_ids: List[str] = []
    for source_type in sorted(REQUIRED_SOURCE_TYPES):
        if source_type not in source_types:
            issue_ids.append(f"missing_source_type:{source_type}")
    for action in sorted(REQUIRED_REFLECTION_ACTIONS):
        if action not in reflection_actions:
            issue_ids.append(f"missing_reflection_action:{action}")
    if len(cache_fallback_reasons) < MIN_CACHE_FALLBACK_REASON_COUNT:
        issue_ids.append("insufficient_distinct_cache_fallback_reasons")
    if len(reflection_signatures) < len(REQUIRED_REFLECTION_ACTIONS):
        issue_ids.append("insufficient_reflection_material_signatures")
    if len(cache_signatures) < MIN_CACHE_FALLBACK_REASON_COUNT + 1:
        issue_ids.append("insufficient_cache_material_signatures")
    if len(set(summary_ids)) != len(summary_ids):
        issue_ids.append("duplicate_summary_id")
    for summary in summaries:
        summary_id = str(summary.get("summary_id") or "unknown")
        if not str(summary.get("source_type") or ""):
            issue_ids.append(f"{summary_id}:missing_source_type")
        if int(summary.get("reflection_case_count") or 0) <= 0:
            issue_ids.append(f"{summary_id}:missing_reflection_cases")
        if int(summary.get("report_cache_case_count") or 0) <= 0:
            issue_ids.append(f"{summary_id}:missing_report_cache_cases")
        if not bool(summary.get("cache_disabled_flags_ok")):
            issue_ids.append(f"{summary_id}:cache_disabled_flags")

    materiality_ok = not issue_ids
    return {
        "status": "ready" if materiality_ok else "needs_review",
        "summary_count": len(summaries),
        "source_types": sorted(source_types),
        "required_source_types": sorted(REQUIRED_SOURCE_TYPES),
        "reflection_actions": sorted(reflection_actions),
        "required_reflection_actions": sorted(REQUIRED_REFLECTION_ACTIONS),
        "cache_fallback_reasons": sorted(cache_fallback_reasons),
        "reflection_material_signature_count": len(reflection_signatures),
        "cache_material_signature_count": len(cache_signatures),
        "materiality_ok": materiality_ok,
        "issue_ids": issue_ids,
        "summaries": summaries,
    }


def render_text(result: Dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Promotion Trace Materiality Gate",
            "",
            f"Status: {result.get('status')}",
            f"Summary count: {result.get('summary_count')}",
            f"Source types: {', '.join(list(result.get('source_types') or []))}",
            f"Reflection actions: {', '.join(list(result.get('reflection_actions') or []))}",
            f"Cache fallback reasons: {', '.join(list(result.get('cache_fallback_reasons') or []))}",
            f"Reflection material signatures: {result.get('reflection_material_signature_count')}",
            f"Cache material signatures: {result.get('cache_material_signature_count')}",
            f"Materiality ok: {str(bool(result.get('materiality_ok'))).lower()}",
            "",
        ]
    )


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the promotion trace summary materiality gate.",
    )
    parser.add_argument(
        "--trace-summary",
        action="append",
        dest="trace_summaries",
        help="Promotion trace summary JSON path. Repeat to pass multiple summaries.",
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
    result = run_gate(trace_summary_paths=args.trace_summaries)
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
