"""Versioned vector-store identity and strict readiness checks."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, Mapping, Optional

from src.config.runtime_contract import (
    CANONICAL_CHUNK_OVERLAP,
    CANONICAL_CHUNK_SIZE,
    CANONICAL_EMBEDDING_DIMENSION,
    CANONICAL_EMBEDDING_MODEL,
    CANONICAL_EMBEDDING_PROVIDER,
    CANONICAL_INGEST_PROFILE_ID,
    CANONICAL_PARSER_SCHEMA_VERSION,
)


STORE_MANIFEST_FILENAME = "store_manifest.json"
STORE_MANIFEST_SCHEMA_VERSION = "store_manifest_v1"


@dataclass(frozen=True, slots=True)
class StoreEmbeddingV1:
    provider: str
    model_name: str
    dimension: int

    def to_projection(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "dimension": self.dimension,
        }


@dataclass(frozen=True, slots=True)
class StoreIngestV1:
    profile_id: str
    parser_schema_version: str
    chunk_size: int
    chunk_overlap: int

    def to_projection(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "parser_schema_version": self.parser_schema_version,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }


@dataclass(frozen=True, slots=True)
class StoreManifestV1:
    collection_name: str
    embedding: StoreEmbeddingV1
    ingest: StoreIngestV1
    schema_version: str = STORE_MANIFEST_SCHEMA_VERSION

    @classmethod
    def from_projection(cls, value: Mapping[str, Any]) -> "StoreManifestV1":
        schema_version = str(value.get("schema_version") or "")
        if schema_version != STORE_MANIFEST_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported store manifest schema: {schema_version or 'missing'}"
            )
        embedding = dict(value.get("embedding") or {})
        ingest = dict(value.get("ingest") or {})
        return cls(
            schema_version=schema_version,
            collection_name=str(value.get("collection_name") or ""),
            embedding=StoreEmbeddingV1(
                provider=str(embedding.get("provider") or ""),
                model_name=str(embedding.get("model_name") or ""),
                dimension=int(embedding.get("dimension") or 0),
            ),
            ingest=StoreIngestV1(
                profile_id=str(ingest.get("profile_id") or ""),
                parser_schema_version=str(
                    ingest.get("parser_schema_version") or ""
                ),
                chunk_size=int(ingest.get("chunk_size") or 0),
                chunk_overlap=int(ingest.get("chunk_overlap") or 0),
            ),
        )

    def to_projection(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "collection_name": self.collection_name,
            "embedding": self.embedding.to_projection(),
            "ingest": self.ingest.to_projection(),
        }


@dataclass(frozen=True, slots=True)
class StoreReadiness:
    status: str
    ready: bool
    reason: str
    expected: StoreManifestV1
    actual: Optional[StoreManifestV1] = None
    degraded: bool = False

    def to_projection(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "ready": self.ready,
            "reason": self.reason,
            "degraded": self.degraded,
            "expected": self.expected.to_projection(),
            "actual": (
                self.actual.to_projection() if self.actual is not None else None
            ),
        }


def canonical_store_manifest(
    *,
    collection_name: str,
    embedding_provider: str = CANONICAL_EMBEDDING_PROVIDER,
    embedding_model_name: str = CANONICAL_EMBEDDING_MODEL,
    embedding_dimension: int = CANONICAL_EMBEDDING_DIMENSION,
    profile_id: str = CANONICAL_INGEST_PROFILE_ID,
    parser_schema_version: str = CANONICAL_PARSER_SCHEMA_VERSION,
    chunk_size: int = CANONICAL_CHUNK_SIZE,
    chunk_overlap: int = CANONICAL_CHUNK_OVERLAP,
) -> StoreManifestV1:
    return StoreManifestV1(
        collection_name=str(collection_name),
        embedding=StoreEmbeddingV1(
            provider=str(embedding_provider).strip().lower(),
            model_name=str(embedding_model_name).strip(),
            dimension=int(embedding_dimension),
        ),
        ingest=StoreIngestV1(
            profile_id=str(profile_id),
            parser_schema_version=str(parser_schema_version),
            chunk_size=int(chunk_size),
            chunk_overlap=int(chunk_overlap),
        ),
    )


def store_manifest_path(persist_directory: str | Path) -> Path:
    return Path(persist_directory) / STORE_MANIFEST_FILENAME


def is_empty_chroma_store(persist_directory: str | Path) -> bool:
    """Return true only for a readable initialized Chroma store with no data."""

    database_path = Path(persist_directory) / "chroma.sqlite3"
    if not database_path.is_file():
        return False
    if any(
        database_path.with_name(f"{database_path.name}{suffix}").exists()
        for suffix in ("-wal", "-shm")
    ):
        return False

    database_uri = f"{database_path.resolve().as_uri()}?mode=ro&immutable=1"
    try:
        connection = sqlite3.connect(database_uri, uri=True)
        try:
            for table in ("embeddings", "embeddings_queue"):
                row = connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()
                if row is None or int(row[0] or 0) > 0:
                    return False
        finally:
            connection.close()
    except sqlite3.Error:
        return False
    return True


def read_store_manifest(
    persist_directory: str | Path,
) -> Optional[StoreManifestV1]:
    path = store_manifest_path(persist_directory)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("store manifest root must be an object")
    return StoreManifestV1.from_projection(payload)


def write_store_manifest(
    persist_directory: str | Path,
    manifest: StoreManifestV1,
) -> Path:
    path = store_manifest_path(persist_directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(
            manifest.to_projection(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)
    return path


def assess_store_readiness(
    persist_directory: str | Path,
    *,
    expected: StoreManifestV1,
    allow_degraded_bm25_only: bool = False,
    bm25_available: bool = False,
) -> StoreReadiness:
    try:
        actual = read_store_manifest(persist_directory)
    except Exception as exc:
        return StoreReadiness(
            status="invalid",
            ready=False,
            reason=str(exc),
            expected=expected,
        )
    if actual is None:
        if allow_degraded_bm25_only and bm25_available:
            return StoreReadiness(
                status="degraded",
                ready=True,
                reason="manifest missing; explicit BM25-only mode enabled",
                expected=expected,
                degraded=True,
            )
        return StoreReadiness(
            status="missing",
            ready=False,
            reason="store manifest is missing",
            expected=expected,
        )
    if actual != expected:
        if allow_degraded_bm25_only and bm25_available:
            return StoreReadiness(
                status="degraded",
                ready=True,
                reason="manifest mismatch; explicit BM25-only mode enabled",
                expected=expected,
                actual=actual,
                degraded=True,
            )
        return StoreReadiness(
            status="mismatch",
            ready=False,
            reason="store manifest does not match runtime contract",
            expected=expected,
            actual=actual,
        )
    return StoreReadiness(
        status="compatible",
        ready=True,
        reason="store manifest matches runtime contract",
        expected=expected,
        actual=actual,
    )


__all__ = [
    "STORE_MANIFEST_FILENAME",
    "STORE_MANIFEST_SCHEMA_VERSION",
    "StoreEmbeddingV1",
    "StoreIngestV1",
    "StoreManifestV1",
    "StoreReadiness",
    "assess_store_readiness",
    "canonical_store_manifest",
    "is_empty_chroma_store",
    "read_store_manifest",
    "store_manifest_path",
    "write_store_manifest",
]
