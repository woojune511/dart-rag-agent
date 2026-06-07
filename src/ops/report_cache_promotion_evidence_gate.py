"""Run the report-cache promotion evidence gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from src.config.report_scoped_cache import build_report_cache_promotion_evidence_case


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_CACHE_INDEX_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "report_cache_index" / "rehydration_diagnostics.json"
)
DEFAULT_TRACE_SUMMARY_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "promotion_trace_summary"
    / "store_fixed_candidate_summary.json"
)
DEFAULT_TRACE_SUMMARY_PATHS = (DEFAULT_TRACE_SUMMARY_PATH,)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _iter_entries(payload: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(payload, Mapping):
        entries = payload.get("entries")
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, Mapping):
                    yield dict(entry)
            return
        yield dict(payload)
    elif isinstance(payload, list):
        for entry in payload:
            if isinstance(entry, Mapping):
                yield dict(entry)


def _scenario(name: str, entry: Mapping[str, Any], *, selected_match_count: int) -> Dict[str, Any]:
    case = build_report_cache_promotion_evidence_case(
        entry,
        selected_match_count=selected_match_count,
        task_id=f"report_cache_promotion::{name}",
    )
    return {
        "name": name,
        "status": case.get("status"),
        "ready": bool(case.get("ready")),
        "fallback_required": bool(case.get("fallback_required")),
        "selected_match_count": case.get("selected_match_count"),
        "reasons": list(case.get("reasons") or []),
        "consumer_admissibility_status": case.get("consumer_admissibility_status"),
        "producer_policy_status": case.get("producer_policy_status"),
        "producer_policy_ready": bool(case.get("producer_policy_ready")),
        "serving_enabled": bool(case.get("serving_enabled")),
        "ledger_insertion_enabled": bool(case.get("ledger_insertion_enabled")),
        "retrieval_bypass_enabled": bool(case.get("retrieval_bypass_enabled")),
        "final_acceptance_enabled": bool(case.get("final_acceptance_enabled")),
        "acceptance_authority": case.get("acceptance_authority"),
    }


def _trace_summary_scenarios(path: Path) -> List[Dict[str, Any]]:
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        raise ValueError(f"promotion trace summary must be a JSON object: {path}")
    scenarios: List[Dict[str, Any]] = []
    for item in list(payload.get("report_cache_promotion_cases") or []):
        if not isinstance(item, Mapping):
            continue
        scenario = dict(item)
        scenario["name"] = str(scenario.get("name") or "trace_summary_case")
        scenario["status"] = str(scenario.get("status") or "")
        scenario["ready"] = bool(scenario.get("ready"))
        scenario["fallback_required"] = bool(scenario.get("fallback_required"))
        scenario["serving_enabled"] = bool(scenario.get("serving_enabled"))
        scenario["ledger_insertion_enabled"] = bool(scenario.get("ledger_insertion_enabled"))
        scenario["retrieval_bypass_enabled"] = bool(scenario.get("retrieval_bypass_enabled"))
        scenario["final_acceptance_enabled"] = bool(scenario.get("final_acceptance_enabled"))
        scenario["reasons"] = [
            str(reason)
            for reason in list(scenario.get("reasons") or [])
            if str(reason).strip()
        ]
        scenarios.append(scenario)
    return scenarios


def run_gate(
    *,
    report_cache_index_path: str | Path = DEFAULT_REPORT_CACHE_INDEX_PATH,
    trace_summary_paths: List[str | Path] | None = None,
) -> Dict[str, Any]:
    entries = list(_iter_entries(_read_json(Path(report_cache_index_path))))
    if len(entries) < 2:
        return {
            "status": "needs_evidence",
            "reason": "expected at least one incomplete and one ready fixture entry",
            "scenario_count": len(entries),
            "scenarios": [],
        }

    scenarios = [
        _scenario("incomplete_entry_fallback", entries[0], selected_match_count=1),
        _scenario("ready_entry_candidate_only", entries[1], selected_match_count=1),
        _scenario("ambiguous_match_fallback", entries[1], selected_match_count=2),
    ]
    trace_paths = [
        Path(path)
        for path in (
            trace_summary_paths
            if trace_summary_paths is not None
            else list(DEFAULT_TRACE_SUMMARY_PATHS)
        )
    ]
    for path in trace_paths:
        scenarios.extend(_trace_summary_scenarios(path))
    disabled_flag_values = [
        bool(item.get("serving_enabled"))
        or bool(item.get("ledger_insertion_enabled"))
        or bool(item.get("retrieval_bypass_enabled"))
        or bool(item.get("final_acceptance_enabled"))
        for item in scenarios
    ]
    ready_count = sum(1 for item in scenarios if bool(item.get("ready")))
    fallback_count = sum(1 for item in scenarios if bool(item.get("fallback_required")))
    status = (
        "ready"
        if ready_count >= 1 and fallback_count >= 2 and not any(disabled_flag_values)
        else "needs_evidence"
    )
    return {
        "status": status,
        "report_cache_index_path": str(Path(report_cache_index_path)),
        "scenario_count": len(scenarios),
        "ready_count": ready_count,
        "fallback_count": fallback_count,
        "disabled_flags_ok": not any(disabled_flag_values),
        "trace_summary_count": len(trace_paths),
        "trace_summary_paths": [str(path) for path in trace_paths],
        "scenarios": scenarios,
    }


def render_text(result: Dict[str, Any]) -> str:
    lines = [
        "# Report Cache Promotion Evidence Gate",
        "",
        f"Status: {result.get('status')}",
        f"Ready cases: {result.get('ready_count', 0)}",
        f"Fallback cases: {result.get('fallback_count', 0)}",
        f"Disabled flags ok: {str(bool(result.get('disabled_flags_ok'))).lower()}",
        f"Trace summaries: {result.get('trace_summary_count', 0)}",
        "",
        "Scenarios:",
    ]
    for scenario in list(result.get("scenarios") or []):
        item = dict(scenario or {})
        lines.append(
            "  - "
            f"{item.get('name')}: status={item.get('status')} "
            f"ready={str(bool(item.get('ready'))).lower()} "
            f"fallback={str(bool(item.get('fallback_required'))).lower()}"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixture-backed report-cache promotion evidence gate.",
    )
    parser.add_argument(
        "--report-cache-index-path",
        type=Path,
        default=DEFAULT_REPORT_CACHE_INDEX_PATH,
        help="Path to a local_cache_index JSON or JSONL fixture.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--trace-summary",
        type=Path,
        action="append",
        default=None,
        help=(
            "Path to a promotion trace summary JSON. May be repeated. "
            "Defaults to the reviewed store-fixed trace summary fixture."
        ),
    )
    parser.add_argument("--output", type=Path, help="Optional output file path.")
    return parser.parse_args(argv)


def _write_output(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_gate(
        report_cache_index_path=args.report_cache_index_path,
        trace_summary_paths=args.trace_summary,
    )
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
