"""Run the REFERENCE_NOTE capability boundary gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from src.config.reference_note_capability import (
    REFERENCE_NOTE_ARTIFACT_KIND,
    REFERENCE_NOTE_CAPABILITY_STATUS,
    REFERENCE_NOTE_GRAPH_RELATION,
    REFERENCE_NOTE_OWNER,
    reference_note_capability_status,
)


EXPECTED_DISABLED_FLAGS = (
    "cache_read_source",
    "cache_serving_enabled",
    "retrieval_bypass_enabled",
    "ledger_insertion_enabled",
    "final_acceptance_enabled",
)


def run_gate() -> Dict[str, Any]:
    capability = reference_note_capability_status()
    issue_ids: List[str] = []
    if str(capability.get("status") or "") != REFERENCE_NOTE_CAPABILITY_STATUS:
        issue_ids.append("status")
    if str(capability.get("owner") or "") != REFERENCE_NOTE_OWNER:
        issue_ids.append("owner")
    if str(capability.get("graph_relation") or "") != REFERENCE_NOTE_GRAPH_RELATION:
        issue_ids.append("graph_relation")
    if str(capability.get("artifact_kind") or "") != REFERENCE_NOTE_ARTIFACT_KIND:
        issue_ids.append("artifact_kind")
    if not bool(capability.get("retrieval_context_enabled")):
        issue_ids.append("retrieval_context_enabled")
    if str(capability.get("report_cache_origin") or ""):
        issue_ids.append("report_cache_origin")
    for flag in EXPECTED_DISABLED_FLAGS:
        if bool(capability.get(flag)):
            issue_ids.append(flag)
    allowed_surfaces = set(str(item) for item in list(capability.get("allowed_surfaces") or []))
    blocked_surfaces = set(str(item) for item in list(capability.get("blocked_surfaces") or []))
    if "researcher.retrieval_bundle" not in allowed_surfaces:
        issue_ids.append("missing_researcher_surface")
    if "report_cache_entry.source" not in blocked_surfaces:
        issue_ids.append("missing_cache_entry_block")
    if "final_answer.acceptance_authority" not in blocked_surfaces:
        issue_ids.append("missing_acceptance_block")
    return {
        "status": "ready" if not issue_ids else "needs_review",
        "capability": capability,
        "disabled_flags_ok": not any(bool(capability.get(flag)) for flag in EXPECTED_DISABLED_FLAGS),
        "issue_ids": issue_ids,
    }


def render_text(result: Dict[str, Any]) -> str:
    capability = dict(result.get("capability") or {})
    return "\n".join(
        [
            "# REFERENCE_NOTE Capability Gate",
            "",
            f"Status: {result.get('status')}",
            f"Owner: {capability.get('owner')}",
            f"Graph relation: {capability.get('graph_relation')}",
            f"Artifact kind: {capability.get('artifact_kind')}",
            f"Disabled flags ok: {str(bool(result.get('disabled_flags_ok'))).lower()}",
            f"Cache serving enabled: {str(bool(capability.get('cache_serving_enabled'))).lower()}",
            f"Retrieval bypass enabled: {str(bool(capability.get('retrieval_bypass_enabled'))).lower()}",
            f"Final acceptance enabled: {str(bool(capability.get('final_acceptance_enabled'))).lower()}",
            "",
        ]
    )


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the REFERENCE_NOTE capability boundary gate.",
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
    result = run_gate()
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
