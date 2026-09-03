"""FastAPI-owned service container and strict startup readiness."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.storage.store_manifest import (
    StoreManifestV1,
    StoreReadiness,
    assess_store_readiness,
    canonical_store_manifest,
    is_empty_chroma_store,
)


_APP_SETTING_NAMES = (
    "CONTEXTUAL_INGEST_MAX_WORKERS",
    "DART_ALLOW_DEGRADED_BM25_ONLY",
    "DART_CORS_ALLOW_ORIGINS",
    "DART_REPORTS_PATH",
    "DART_STORE_PATH",
)


def _enabled(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_app_settings(project_root: Path) -> Dict[str, str]:
    """Resolve API settings without mutating the process environment."""

    from dotenv import dotenv_values

    dotenv_settings = dotenv_values(Path(project_root) / ".env")
    return {
        name: str(
            os.environ[name]
            if name in os.environ
            else dotenv_settings.get(name) or ""
        )
        for name in _APP_SETTING_NAMES
    }


def _store_may_initialize(
    persist_directory: Path,
    *,
    readiness: StoreReadiness,
    allow_degraded: bool,
) -> bool:
    existing_entries = (
        any(persist_directory.iterdir())
        if persist_directory.is_dir()
        else False
    )
    return bool(
        readiness.status == "compatible"
        or not existing_entries
        or allow_degraded
        or (
            readiness.status == "missing"
            and is_empty_chroma_store(persist_directory)
        )
    )


@dataclass(slots=True)
class AppServices:
    expected_manifest: StoreManifestV1
    readiness: StoreReadiness
    contextual_ingest_max_workers: int = 8
    store: Optional[Any] = None
    agent: Optional[Any] = None
    ingest_service: Optional[Any] = None
    operation_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        repr=False,
    )

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
    from dotenv import load_dotenv

    root = project_root or Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")
    settings: Mapping[str, str] = resolve_app_settings(root)

    from src.agent.financial_graph import FinancialAgent
    from src.ingestion.context_generator import ContextGenerator
    from src.ingestion.dart_fetcher import DARTFetcher
    from src.ingestion.ingest_service import IngestService
    from src.processing.financial_parser import FinancialParser
    from src.storage.vector_store import DEFAULT_COLLECTION_NAME, VectorStoreManager

    persist_directory = Path(
        settings.get("DART_STORE_PATH") or root / "data" / "chroma_dart"
    )
    reports_directory = Path(
        settings.get("DART_REPORTS_PATH") or root / "data" / "reports"
    )
    allow_degraded = _enabled(
        settings.get("DART_ALLOW_DEGRADED_BM25_ONLY", "")
    )
    expected = canonical_store_manifest(
        collection_name=DEFAULT_COLLECTION_NAME
    )
    initial = assess_store_readiness(
        persist_directory,
        expected=expected,
    )
    may_initialize = _store_may_initialize(
        persist_directory,
        readiness=initial,
        allow_degraded=allow_degraded,
    )
    services = AppServices(
        expected_manifest=expected,
        readiness=initial,
        contextual_ingest_max_workers=int(
            settings.get("CONTEXTUAL_INGEST_MAX_WORKERS") or 8
        ),
    )
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


__all__ = ["AppServices", "build_app_services", "resolve_app_settings"]
