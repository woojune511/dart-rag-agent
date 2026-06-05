"""Read-only report-scoped cache index diagnostics.

This adapter only loads and validates future local-cache-index entries. It does
not serve runtime hits, write entries, or bypass retrieval.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.config.report_scoped_cache import (
    CACHE_ENTRY_READABLE,
    classify_report_cache_entry,
    report_cache_key_id,
)


def _iter_entry_payloads(payload: Any) -> Iterable[Dict[str, Any]]:
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


class ReportCacheIndex:
    """Read-only validator for a local report-cache index file."""

    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None

    def load_diagnostics(self) -> Dict[str, Any]:
        if self.path is None:
            return {
                "status": "not_configured",
                "enabled": False,
                "serving_enabled": False,
                "path": "",
                "entries": [],
                "readable_count": 0,
                "blocked_count": 0,
                "malformed_count": 0,
            }
        if not self.path.exists():
            return {
                "status": "missing",
                "enabled": False,
                "serving_enabled": False,
                "path": str(self.path),
                "entries": [],
                "readable_count": 0,
                "blocked_count": 0,
                "malformed_count": 0,
            }
        try:
            if self.path.suffix.lower() == ".jsonl":
                payloads: List[Dict[str, Any]] = []
                malformed_count = 0
                for line in self.path.read_text(encoding="utf-8").splitlines():
                    text = line.strip()
                    if not text:
                        continue
                    try:
                        item = json.loads(text)
                    except json.JSONDecodeError:
                        malformed_count += 1
                        continue
                    if isinstance(item, dict):
                        payloads.append(item)
                    else:
                        malformed_count += 1
            else:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                payloads = list(_iter_entry_payloads(payload))
                malformed_count = 0
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "status": "malformed",
                "enabled": False,
                "serving_enabled": False,
                "path": str(self.path),
                "error": str(exc),
                "entries": [],
                "readable_count": 0,
                "blocked_count": 0,
                "malformed_count": 1,
            }

        entries = [classify_report_cache_entry(entry) for entry in payloads]
        readable_count = sum(1 for entry in entries if entry.get("status") == CACHE_ENTRY_READABLE)
        blocked_count = len(entries) - readable_count
        return {
            "status": "loaded",
            "enabled": False,
            "serving_enabled": False,
            "path": str(self.path),
            "entries": entries,
            "readable_count": readable_count,
            "blocked_count": blocked_count,
            "malformed_count": malformed_count,
        }

    def lookup_diagnostics(self, key_parts: Dict[str, Any]) -> Dict[str, Any]:
        key_id = report_cache_key_id(key_parts)
        diagnostics = self.load_diagnostics()
        matches = [
            dict(entry)
            for entry in list(diagnostics.get("entries") or [])
            if str(entry.get("key_id") or "") == key_id
        ]
        return {
            "status": "trace_only",
            "enabled": False,
            "serving_enabled": False,
            "key_id": key_id,
            "match_count": len(matches),
            "readable_match_count": sum(1 for entry in matches if entry.get("status") == CACHE_ENTRY_READABLE),
            "matches": matches,
            "index": {
                "status": diagnostics.get("status"),
                "path": diagnostics.get("path"),
                "readable_count": diagnostics.get("readable_count", 0),
                "blocked_count": diagnostics.get("blocked_count", 0),
                "malformed_count": diagnostics.get("malformed_count", 0),
            },
        }
