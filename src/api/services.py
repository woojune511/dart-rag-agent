"""FastAPI-owned service container and strict startup readiness."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Optional

from src.storage.store_manifest import (
    StoreManifestV1,
    StoreReadiness,
    assess_store_readiness,
    canonical_store_manifest,
)


def _enabled(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class AppServices:
    expected_manifest: StoreManifestV1
    readiness: StoreReadiness
    store: Optional[Any] = None
    agent: Optional[Any] = None
    ingest_service: Optional[Any] = None

    def refresh_readiness(self) -> StoreReadiness:
        allow_degraded = bool(
            self.store is not None
            and getattr(self.store, "force_bm25_only", False)
        )
        self.readiness = assess_store_readiness(
            self.store.persist_directory if self.store is not None else "",
            expected=self.expected_manifest,
            allow_degraded_bm25_only=allow_degraded,
            bm25_available=bool(
                self.store is not None
                and list(getattr(self.store, "bm25_docs", []) or [])
            ),
        )
        if self.agent is not None:
            self.agent.retrieval_degraded_reason = (
                self.readiness.reason if self.readiness.degraded else ""
            )
            self.agent.retrieval_mode = (
                "bm25_only" if self.readiness.degraded else "hybrid"
            )
        return self.readiness


def build_app_services(
    *,
    project_root: Optional[Path] = None,
) -> AppServices:
    from src.agent.financial_graph import FinancialAgent
    from src.ingestion.context_generator import ContextGenerator
    from src.ingestion.dart_fetcher import DARTFetcher
    from src.ingestion.ingest_service import IngestService
    from src.processing.financial_parser import FinancialParser
    from src.storage.vector_store import DEFAULT_COLLECTION_NAME, VectorStoreManager

    root = project_root or Path(__file__).resolve().parents[2]
    persist_directory = Path(
        os.environ.get("DART_STORE_PATH") or root / "data" / "chroma_dart"
    )
    reports_directory = Path(
        os.environ.get("DART_REPORTS_PATH") or root / "data" / "reports"
    )
    allow_degraded = _enabled(
        os.environ.get("DART_ALLOW_DEGRADED_BM25_ONLY", "")
    )
    expected = canonical_store_manifest(
        collection_name=DEFAULT_COLLECTION_NAME
    )
    initial = assess_store_readiness(
        persist_directory,
        expected=expected,
    )
    existing_entries = (
        [entry for entry in persist_directory.iterdir()]
        if persist_directory.is_dir()
        else []
    )
    may_initialize = (
        initial.status == "compatible"
        or not existing_entries
        or allow_degraded
    )
    services = AppServices(expected_manifest=expected, readiness=initial)
    if not may_initialize:
        return services

    store = VectorStoreManager(
        persist_directory=str(persist_directory),
        collection_name=expected.collection_name,
        embedding_provider=expected.embedding.provider,
        embedding_model_name=expected.embedding.model_name,
        allow_query_embedding_fallback=allow_degraded,
        force_bm25_only=allow_degraded and initial.status != "compatible",
    )
    agent = FinancialAgent(store, k=8)
    context_generator = ContextGenerator(agent.llm, store)
    parser = FinancialParser(
        chunk_size=expected.ingest.chunk_size,
        chunk_overlap=expected.ingest.chunk_overlap,
    )
    ingest_service = IngestService(
        fetcher=DARTFetcher(download_dir=str(reports_directory)),
        parser=parser,
        context_generator=context_generator,
        store=store,
        manifest=expected,
    )
    services.store = store
    services.agent = agent
    services.ingest_service = ingest_service
    services.refresh_readiness()
    return services


__all__ = ["AppServices", "build_app_services"]
