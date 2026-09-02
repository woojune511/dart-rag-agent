"""Application ingest orchestration outside the query agent."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, Iterable

from src.storage.store_manifest import (
    StoreManifestV1,
    read_store_manifest,
    write_store_manifest,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestService:
    fetcher: Any
    parser: Any
    context_generator: Any
    store: Any
    manifest: StoreManifestV1

    def _store_has_documents(self) -> bool:
        if list(getattr(self.store, "bm25_docs", []) or []):
            return True
        vector_store = getattr(self.store, "vector_store", None)
        collection = getattr(vector_store, "_collection", None)
        count = getattr(collection, "count", None)
        if callable(count):
            try:
                return int(count() or 0) > 0
            except Exception:
                return False
        return False

    def _assert_manifest_boundary(self) -> None:
        actual = read_store_manifest(self.store.persist_directory)
        if actual is not None and actual != self.manifest:
            raise RuntimeError(
                "store manifest does not match the ingest runtime contract"
            )
        if actual is None and self._store_has_documents():
            raise RuntimeError(
                "refusing to adopt a non-empty store without an approved manifest"
            )

    @staticmethod
    def _report_metadata(report: Any) -> Dict[str, Any]:
        return {
            "company": report.corp_name,
            "stock_code": report.stock_code or "unknown",
            "year": report.year,
            "report_type": report.report_type,
            "rcept_no": report.rcept_no,
        }

    def ingest_company(
        self,
        company: str,
        years: Iterable[int],
        *,
        max_workers: int,
    ) -> Dict[str, Any]:
        self._assert_manifest_boundary()
        normalized_years = [int(year) for year in years]
        reports = list(
            self.fetcher.fetch_company_reports(company, normalized_years) or []
        )
        total_chunks = 0
        skipped = 0
        missing_files = 0
        for report in reports:
            if not report.file_path or not Path(report.file_path).is_file():
                missing_files += 1
                logger.warning("Skipping report without a local file: %s", report)
                continue
            if self.store.is_indexed(report.rcept_no):
                skipped += 1
                continue
            chunks = self.parser.process_document(
                report.file_path,
                self._report_metadata(report),
            )
            if not chunks:
                continue
            self.context_generator.contextual_ingest(
                chunks,
                max_workers=max_workers,
            )
            total_chunks += len(chunks)
        if total_chunks:
            write_store_manifest(self.store.persist_directory, self.manifest)
        return {
            "company": str(company),
            "years": normalized_years,
            "files_fetched": len(reports),
            "chunks_added": total_chunks,
            "reports_skipped": skipped,
            "missing_files": missing_files,
        }


__all__ = ["IngestService"]
