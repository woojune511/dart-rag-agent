"""Dry-run validation and explicitly approved manifest adoption for legacy stores."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from src.config.runtime_contract import CANONICAL_INGEST_PROFILE_ID
from src.storage.store_manifest import (
    StoreManifestV1,
    canonical_store_manifest,
    write_store_manifest,
)
from src.storage.vector_store import DEFAULT_COLLECTION_NAME


def validate_manifest_adoption(
    *,
    expected: StoreManifestV1,
    observed_collection_name: str,
    observed_dimension: Optional[int],
    declared_profile_id: str,
) -> Dict[str, Any]:
    errors = []
    if str(observed_collection_name) != expected.collection_name:
        errors.append("collection_name_mismatch")
    if observed_dimension is None:
        errors.append("embedding_dimension_unavailable")
    elif int(observed_dimension) != expected.embedding.dimension:
        errors.append("embedding_dimension_mismatch")
    if str(declared_profile_id) != expected.ingest.profile_id:
        errors.append("ingest_profile_mismatch")
    return {
        "status": "compatible" if not errors else "rejected",
        "write_allowed": not errors,
        "errors": errors,
        "expected": expected.to_projection(),
        "observed": {
            "collection_name": str(observed_collection_name),
            "embedding_dimension": observed_dimension,
            "declared_profile_id": str(declared_profile_id),
        },
    }


def _inspect_chroma(
    persist_directory: Path,
    collection_name: str,
) -> tuple[str, Optional[int]]:
    import chromadb

    client = chromadb.PersistentClient(path=str(persist_directory))
    collection = client.get_collection(name=collection_name)
    payload = collection.peek(limit=1)
    embeddings = list(payload.get("embeddings") or [])
    dimension = len(embeddings[0]) if embeddings else None
    return str(collection.name), dimension


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("persist_directory", type=Path)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument(
        "--expected-profile",
        default=CANONICAL_INGEST_PROFILE_ID,
    )
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="Write only after reviewing a successful dry-run.",
    )
    args = parser.parse_args()
    expected = canonical_store_manifest(collection_name=args.collection_name)
    observed_collection, observed_dimension = _inspect_chroma(
        args.persist_directory,
        args.collection_name,
    )
    result = validate_manifest_adoption(
        expected=expected,
        observed_collection_name=observed_collection,
        observed_dimension=observed_dimension,
        declared_profile_id=args.expected_profile,
    )
    result["mode"] = "write" if args.write_manifest else "dry_run"
    if args.write_manifest:
        if not result["write_allowed"]:
            raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
        result["manifest_path"] = str(
            write_store_manifest(args.persist_directory, expected)
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
