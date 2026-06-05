"""Print trace-only diagnostics for a local report-cache index file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.storage.report_cache_index import ReportCacheIndex  # noqa: E402
from src.config.report_scoped_cache import (  # noqa: E402
    build_report_cache_rehydrated_candidate_artifact,
    validate_report_cache_calculation_contract_projection,
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _iter_payload_entries(payload: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(payload, dict):
        entries = payload.get("entries")
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    yield dict(entry)
            return
        yield dict(payload)
    elif isinstance(payload, list):
        for entry in payload:
            if isinstance(entry, dict):
                yield dict(entry)


def _first_entry_key(index_path: Path) -> Dict[str, Any]:
    payload = _read_json(index_path)
    for entry in _iter_payload_entries(payload):
        key = entry.get("key")
        if isinstance(key, dict):
            return dict(key)
    raise ValueError(f"No entry key found in report cache index: {index_path}")


def _summary_from_diagnostics(diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    index = dict(diagnostics.get("index") or {})
    candidate_artifacts = _rehydrated_candidate_artifacts_from_diagnostics(diagnostics)
    calculation_projection_valid_count = sum(
        1
        for item in list(candidate_artifacts.get("items") or [])
        if bool((item.get("calculation_contract_validation") or {}).get("valid_for_contract"))
    )
    calculation_projection_fallback_count = sum(
        1
        for item in list(candidate_artifacts.get("items") or [])
        if bool((item.get("calculation_contract_validation") or {}).get("fallback_required"))
    )
    return {
        "status": str(diagnostics.get("status") or ""),
        "enabled": bool(diagnostics.get("enabled")),
        "serving_enabled": bool(diagnostics.get("serving_enabled")),
        "match_count": int(diagnostics.get("match_count") or 0),
        "readable_match_count": int(diagnostics.get("readable_match_count") or 0),
        "rehydration_ready_match_count": int(diagnostics.get("rehydration_ready_match_count") or 0),
        "rehydration_blocked_match_count": int(diagnostics.get("rehydration_blocked_match_count") or 0),
        "rehydration_reason_counts": dict(diagnostics.get("rehydration_reason_counts") or {}),
        "index_status": str(index.get("status") or ""),
        "index_readable_count": int(index.get("readable_count") or 0),
        "index_rehydration_ready_count": int(index.get("rehydration_ready_count") or 0),
        "index_blocked_count": int(index.get("blocked_count") or 0),
        "index_malformed_count": int(index.get("malformed_count") or 0),
        "rehydrated_candidate_artifact_count": int(candidate_artifacts.get("count") or 0),
        "rehydrated_candidate_artifact_blocked_count": int(candidate_artifacts.get("blocked_count") or 0),
        "calculation_projection_valid_count": calculation_projection_valid_count,
        "calculation_projection_fallback_count": calculation_projection_fallback_count,
    }


def _projection_validation_preview(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": str(result.get("status") or ""),
        "valid_for_contract": bool(result.get("valid_for_contract")),
        "fallback_required": bool(result.get("fallback_required")),
        "enabled": bool(result.get("enabled")),
        "serving_enabled": bool(result.get("serving_enabled")),
        "ledger_insertion_enabled": bool(result.get("ledger_insertion_enabled")),
        "reasons": [str(reason) for reason in list(result.get("reasons") or [])],
        "required_artifact_kinds": [
            str(kind)
            for kind in list(result.get("required_artifact_kinds") or [])
            if str(kind).strip()
        ],
    }


def _candidate_artifact_preview(
    result: Dict[str, Any],
    *,
    calculation_contract_validation: Dict[str, Any],
) -> Dict[str, Any]:
    artifact = result.get("artifact")
    item = {
        "status": str(result.get("status") or ""),
        "ready": bool(result.get("ready")),
        "enabled": bool(result.get("enabled")),
        "serving_enabled": bool(result.get("serving_enabled")),
        "reasons": [str(reason) for reason in list(result.get("reasons") or [])],
        "key_id": str(result.get("key_id") or ""),
        "calculation_contract_validation": _projection_validation_preview(calculation_contract_validation),
        "artifact": None,
    }
    if not isinstance(artifact, dict):
        return item
    payload = dict(artifact.get("payload") or {})
    resolved_trace = dict(payload.get("resolved_calculation_trace") or {})
    item["artifact"] = {
        "artifact_id": str(artifact.get("artifact_id") or ""),
        "status": str(artifact.get("status") or ""),
        "kind": str(artifact.get("kind") or ""),
        "summary": str(artifact.get("summary") or ""),
        "payload_summary": {
            "answer": str(payload.get("answer") or ""),
            "citation_count": len(list(payload.get("citations") or [])),
            "evidence_item_count": len(list(payload.get("evidence_items") or [])),
            "has_structured_result": isinstance(payload.get("structured_result"), dict)
            and bool(payload.get("structured_result")),
            "has_resolved_calculation_trace": bool(resolved_trace),
            "calculation_operand_count": len(list(resolved_trace.get("calculation_operands") or [])),
            "serving_enabled": bool(dict(payload.get("report_cache_rehydration") or {}).get("serving_enabled")),
        },
    }
    return item


def _rehydrated_candidate_artifacts_from_diagnostics(diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for index, match in enumerate(list(diagnostics.get("matches") or []), start=1):
        if not isinstance(match, dict):
            continue
        entry = dict(match.get("entry") or match)
        result = build_report_cache_rehydrated_candidate_artifact(
            entry,
            task_id="report_cache_index_smoke",
            artifact_id=f"report_cache_index_smoke::candidate::{index}",
        )
        validation = validate_report_cache_calculation_contract_projection(
            entry,
            task_id="report_cache_index_smoke",
        )
        items.append(
            _candidate_artifact_preview(
                result,
                calculation_contract_validation=validation,
            )
        )
    return {
        "count": sum(1 for item in items if isinstance(item.get("artifact"), dict)),
        "blocked_count": sum(1 for item in items if not isinstance(item.get("artifact"), dict)),
        "items": items,
    }


def build_smoke_payload(
    *,
    report_cache_index_path: str | Path,
    key: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    index_path = Path(report_cache_index_path)
    key_parts = dict(key or _first_entry_key(index_path))
    diagnostics = ReportCacheIndex(index_path).lookup_diagnostics(key_parts)
    candidate_artifacts = _rehydrated_candidate_artifacts_from_diagnostics(diagnostics)
    return {
        "report_cache_index_path": str(index_path),
        "key": key_parts,
        "key_id": str(diagnostics.get("key_id") or ""),
        "summary": _summary_from_diagnostics(diagnostics),
        "diagnostics": diagnostics,
        "rehydrated_candidate_artifacts": candidate_artifacts,
    }


def _parse_key_json(value: str) -> Dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"invalid JSON key: {exc}") from exc
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("key JSON must be an object")
    return dict(payload)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print trace-only report-cache index diagnostics for reviewer handoff.",
    )
    parser.add_argument(
        "--report-cache-index-path",
        required=True,
        help="Path to a local_cache_index JSON or JSONL file.",
    )
    parser.add_argument(
        "--key-json",
        type=_parse_key_json,
        default=None,
        help="Optional report-cache key object. Defaults to the first entry key in the index.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional JSON output path. Stdout is always written.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_smoke_payload(
        report_cache_index_path=args.report_cache_index_path,
        key=args.key_json,
    )
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{text}\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
