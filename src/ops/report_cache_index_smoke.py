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
    }


def build_smoke_payload(
    *,
    report_cache_index_path: str | Path,
    key: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    index_path = Path(report_cache_index_path)
    key_parts = dict(key or _first_entry_key(index_path))
    diagnostics = ReportCacheIndex(index_path).lookup_diagnostics(key_parts)
    return {
        "report_cache_index_path": str(index_path),
        "key": key_parts,
        "key_id": str(diagnostics.get("key_id") or ""),
        "summary": _summary_from_diagnostics(diagnostics),
        "diagnostics": diagnostics,
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
