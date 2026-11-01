"""Check the published historical artifact manifest; no providers or store access."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads(
        (Path(__file__).parent / "rag_experiments_202610_manifest.json").read_text(encoding="utf-8")
    )
    seen: set[str] = set()
    failures = []
    total_bytes = 0
    for entry in manifest["files"]:
        name = entry["path"]
        path = (root / name).resolve()
        if name in seen or not path.is_relative_to(root / "benchmarks" / "results"):
            failures.append(f"invalid or duplicate path: {name}")
            continue
        seen.add(name)
        if not path.is_file():
            failures.append(f"missing: {name}")
            continue
        data = path.read_bytes()
        total_bytes += len(data)
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry["published_sha256"] or len(data) != entry["published_bytes"]:
            failures.append(f"changed: {name}")
        if entry["kind"] == "source_snapshot" and digest != entry["original_sha256"]:
            failures.append(f"source differs from original: {name}")
    if not seen:
        failures.append("empty manifest")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"PASS: {len(seen)} published files, {total_bytes} bytes; source snapshots match originals")


if __name__ == "__main__":
    main()
