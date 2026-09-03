"""Application ingest orchestration outside the query agent."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

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

    def _store_has_documents(self) -> Optional[bool]:
        if list(getattr(self.store, "bm25_docs", []) or []):
            return True
        vector_store = getattr(self.store, "vector_store", None)
        collection = getattr(vector_store, "_collection", None)
        count = getattr(collection, "count", None)
        if callable(count):
            try:
                return int(count() or 0) > 0
            except Exception:
                return None
        return None

    def _assert_manifest_boundary(self) -> None:
        actual = read_store_manifest(self.store.persist_directory)
        if actual is not None and actual != self.manifest:
            raise RuntimeError(
                "store manifest does not match the ingest runtime contract"
            )
        if actual is None:
            store_has_documents = self._store_has_documents()
            if store_has_documents is True:
                raise RuntimeError(
                    "refusing to adopt a non-empty store without an approved manifest"
                )
            if store_has_documents is None:
                raise RuntimeError(
                    "refusing ingest because store emptiness could not be verified"
                )

    def _report_is_fully_indexed(self, report: Any, chunks: Iterable[Any]) -> bool:
        chunk_rows = list(chunks)
        expected_ids = {
            str(getattr(chunk, "metadata", {}).get("chunk_uid") or "").strip()
            for chunk in chunk_rows
        }
        expected_ids.discard("")
        list_indexed = getattr(self.store, "list_indexed_chunk_uids", None)
        if len(expected_ids) == len(chunk_rows) and callable(list_indexed):
            indexed_ids = set(list_indexed(rcept_no=report.rcept_no))
            list_structure = getattr(
                self.store,
                "list_structure_chunk_uids",
                None,
            )
            if callable(list_structure):
                structure_ids = set(
                    list_structure(rcept_no=report.rcept_no)
                )
                return bool(
                    expected_ids.issubset(indexed_ids)
                    and expected_ids.issubset(structure_ids)
                )
            return expected_ids.issubset(indexed_ids)
        return bool(self.store.is_indexed(report.rcept_no))

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
        manifest_recorded = read_store_manifest(self.store.persist_directory) is not None

        def record_manifest_after_mutation(completed: int, _total: int) -> None:
            nonlocal manifest_recorded
            if int(completed or 0) <= 0 or manifest_recorded:
                return
            write_store_manifest(self.store.persist_directory, self.manifest)
            manifest_recorded = True

        total_chunks = 0
        processed = 0
        skipped = 0
        missing_files = 0
        for report in reports:
            if not report.file_path or not Path(report.file_path).is_file():
                missing_files += 1
                logger.warning("Skipping report without a local file: %s", report)
                continue
            chunks = self.parser.process_document(
                report.file_path,
                self._report_metadata(report),
            )
            if not chunks:
                continue
            if self._report_is_fully_indexed(report, chunks):
                skipped += 1
                continue
            ingest_result = self.context_generator.contextual_ingest(
                chunks,
                on_store_progress=record_manifest_after_mutation,
                max_workers=max_workers,
                resume_partial_store=True,
            ) or {}
            processed += 1
            total_chunks += int(ingest_result.get("added_chunks", len(chunks)))
            if not manifest_recorded:
                write_store_manifest(self.store.persist_directory, self.manifest)
                manifest_recorded = True
        return {
            "company": str(company),
            "years": normalized_years,
            "files_fetched": len(reports),
            "chunks_added": total_chunks,
            "reports_processed": processed,
            "reports_skipped": skipped,
            "missing_files": missing_files,
        }


__all__ = ["IngestService"]
