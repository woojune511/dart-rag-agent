"""Audit reviewed domain-language string literals in runtime agent code."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCAN_ROOTS = ("src/agent", "src/routing")
DEFAULT_BASELINE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "runtime_domain_terms_baseline.json"
BASELINE_SCHEMA_VERSION = 1

_HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")
_WHITESPACE_RE = re.compile(r"\s+")
_REGEX_HINTS_RE = re.compile(r"(\\[dDsSwWbBAZ]|\[\^?|\(\?:|\?P<|\{[0-9,]+\})")


def normalise_literal(value: str) -> str:
    """Collapse whitespace so the audit is stable across formatting edits."""

    return _WHITESPACE_RE.sub(" ", value).strip()


def has_reviewed_domain_language(value: str) -> bool:
    return bool(_HANGUL_RE.search(value))


def classify_literal(value: str) -> str:
    if "\n" in value or len(value) > 120:
        return "prompt_or_template"
    if _REGEX_HINTS_RE.search(value):
        return "regex_or_pattern"
    return "runtime_literal"


def _relative_path(path: Path, project_root: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def _iter_python_files(project_root: Path, scan_roots: Sequence[str]) -> Iterable[Path]:
    for root_value in scan_roots:
        root = (project_root / root_value).resolve()
        if root.is_file() and root.suffix == ".py":
            yield root
        elif root.is_dir():
            yield from sorted(root.rglob("*.py"))


class _StringLiteralVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.literals: List[Tuple[int, str]] = []

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802 - ast visitor API
        if isinstance(node.value, str):
            self.literals.append((int(getattr(node, "lineno", 0) or 0), node.value))
        self.generic_visit(node)


def collect_runtime_domain_terms(
    project_root: Path | str = PROJECT_ROOT,
    scan_roots: Sequence[str] = DEFAULT_SCAN_ROOTS,
) -> List[Dict[str, Any]]:
    project_path = Path(project_root).resolve()
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    lines_by_key: Dict[Tuple[str, str], List[int]] = defaultdict(list)

    for source_path in _iter_python_files(project_path, scan_roots):
        relative = _relative_path(source_path, project_path)
        source = source_path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(source_path))
        visitor = _StringLiteralVisitor()
        visitor.visit(tree)
        for line_number, raw_value in visitor.literals:
            text = normalise_literal(raw_value)
            if not text or not has_reviewed_domain_language(text):
                continue
            key = (relative, text)
            if key not in grouped:
                fingerprint = hashlib.sha256(f"{relative}\0{text}".encode("utf-8")).hexdigest()[:16]
                grouped[key] = {
                    "path": relative,
                    "text": text,
                    "category": classify_literal(raw_value),
                    "fingerprint": fingerprint,
                    "count": 0,
                }
            grouped[key]["count"] = int(grouped[key]["count"]) + 1
            if line_number:
                lines_by_key[key].append(line_number)

    records: List[Dict[str, Any]] = []
    for key, record in grouped.items():
        lines = sorted(set(lines_by_key[key]))
        records.append({**record, "first_lines": lines[:5]})
    return sorted(records, key=lambda item: (str(item["path"]), str(item["text"])))


def load_runtime_domain_term_baseline(path: Path | str = DEFAULT_BASELINE_PATH) -> List[Dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return list(payload.get("records", []))
    return list(payload)


def _comparison_key(item: Mapping[str, Any]) -> Tuple[str, str]:
    return (str(item["path"]), str(item["text"]))


def compare_runtime_domain_terms(
    current: Sequence[Mapping[str, Any]],
    baseline: Sequence[Mapping[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    current_map = {_comparison_key(item): item for item in current}
    baseline_map = {_comparison_key(item): item for item in baseline}

    unexpected = [dict(current_map[key]) for key in sorted(current_map.keys() - baseline_map.keys())]
    missing = [dict(baseline_map[key]) for key in sorted(baseline_map.keys() - current_map.keys())]

    count_mismatches: List[Dict[str, Any]] = []
    for key in sorted(current_map.keys() & baseline_map.keys()):
        current_count = int(current_map[key].get("count", 0) or 0)
        baseline_count = int(baseline_map[key].get("count", 0) or 0)
        if current_count != baseline_count:
            count_mismatches.append(
                {
                    "path": key[0],
                    "text": key[1],
                    "current_count": current_count,
                    "baseline_count": baseline_count,
                }
            )

    return {
        "unexpected": unexpected,
        "missing": missing,
        "count_mismatches": count_mismatches,
    }


def _write_json(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "scan_roots": list(DEFAULT_SCAN_ROOTS),
        "review_note": (
            "Reviewed snapshot of existing Korean string literals in high-risk runtime paths. "
            "New domain vocabulary should move to ontology/policy/config before this baseline is updated."
        ),
        "records": list(records),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _format_diff(diff: Mapping[str, Sequence[Mapping[str, Any]]]) -> str:
    lines = [
        "Runtime domain-language audit failed.",
        "Move new domain vocabulary to ontology/policy/config, or update the reviewed baseline with rationale.",
    ]
    for section in ("unexpected", "missing", "count_mismatches"):
        items = list(diff.get(section, ()))
        if not items:
            continue
        lines.append(f"{section}: {len(items)}")
        for item in items[:20]:
            path = item.get("path", "")
            text = str(item.get("text", ""))
            preview = text[:117] + "..." if len(text) > 120 else text
            if section == "count_mismatches":
                lines.append(
                    f"- {path}: {preview} "
                    f"(baseline={item.get('baseline_count')}, current={item.get('current_count')})"
                )
            else:
                lines.append(f"- {path}: {preview}")
        if len(items) > 20:
            lines.append(f"- ... {len(items) - 20} more")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit reviewed domain-language string literals in runtime agent code."
    )
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))
    parser.add_argument("--scan-root", action="append", dest="scan_roots")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)

    scan_roots = tuple(args.scan_roots or DEFAULT_SCAN_ROOTS)
    baseline_path = Path(args.baseline)
    if not baseline_path.is_absolute():
        baseline_path = (PROJECT_ROOT / baseline_path).resolve()

    current = collect_runtime_domain_terms(PROJECT_ROOT, scan_roots)
    if args.write_baseline:
        _write_json(baseline_path, current)
        if args.json_output:
            print(json.dumps({"baseline": str(baseline_path), "record_count": len(current)}, ensure_ascii=False))
        else:
            print(f"Wrote {len(current)} reviewed runtime domain-language literals to {baseline_path}")
        return 0

    baseline = load_runtime_domain_term_baseline(baseline_path)
    diff = compare_runtime_domain_terms(current, baseline)
    failed = any(diff[section] for section in ("unexpected", "missing", "count_mismatches"))
    if args.json_output:
        print(json.dumps({"failed": failed, "diff": diff}, ensure_ascii=False, indent=2))
    elif failed:
        print(_format_diff(diff))
    else:
        print(f"Runtime domain-language audit passed ({len(current)} reviewed literals).")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
