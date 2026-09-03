from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.ingestion.ingest_service import IngestService
from src.storage.store_manifest import (
    canonical_store_manifest,
    read_store_manifest,
)


class _Fetcher:
    def __init__(self, reports):
        self.reports = reports

    def fetch_company_reports(self, _company, _years):
        return list(self.reports)


class _Parser:
    def process_document(self, _path, metadata):
        return [SimpleNamespace(content="text", metadata=metadata)]


class _ContextGenerator:
    def __init__(self):
        self.calls = []

    def contextual_ingest(
        self,
        chunks,
        *,
        on_store_progress=None,
        max_workers,
    ):
        self.calls.append((list(chunks), max_workers))
        if on_store_progress:
            on_store_progress(len(chunks), len(chunks))


class _FailAfterFirstContextGenerator(_ContextGenerator):
    def contextual_ingest(
        self,
        chunks,
        *,
        on_store_progress=None,
        max_workers,
    ):
        super().contextual_ingest(
            chunks,
            on_store_progress=on_store_progress,
            max_workers=max_workers,
        )
        if len(self.calls) > 1:
            raise RuntimeError("synthetic later-report failure")


class _FailAfterFirstBatchContextGenerator(_ContextGenerator):
    def contextual_ingest(
        self,
        chunks,
        *,
        on_store_progress=None,
        max_workers,
    ):
        self.calls.append((list(chunks), max_workers))
        if on_store_progress:
            on_store_progress(1, len(chunks))
        raise RuntimeError("synthetic later-batch failure")


class _Store:
    def __init__(self, root, *, indexed=False, existing_docs=False):
        self.persist_directory = str(root)
        self.indexed = indexed
        self.bm25_docs = ["existing"] if existing_docs else []

    def is_indexed(self, _receipt):
        return self.indexed


class IngestServiceTests(unittest.TestCase):
    def test_fresh_ingest_records_manifest_only_after_indexing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report_path = root / "report.xml"
            report_path.write_text("report", encoding="utf-8")
            report = SimpleNamespace(
                file_path=str(report_path),
                corp_name="sample",
                stock_code="000000",
                year=2024,
                report_type="annual",
                rcept_no="receipt-1",
            )
            context_generator = _ContextGenerator()
            manifest = canonical_store_manifest(collection_name="runtime")
            service = IngestService(
                _Fetcher([report]),
                _Parser(),
                context_generator,
                _Store(root),
                manifest,
            )

            result = service.ingest_company("sample", [2024], max_workers=2)

            self.assertEqual(result["chunks_added"], 1)
            self.assertEqual(len(context_generator.calls), 1)
            self.assertEqual(read_store_manifest(root), manifest)

    def test_partial_success_records_manifest_before_later_report_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reports = []
            for index in range(2):
                report_path = root / f"report-{index}.xml"
                report_path.write_text("report", encoding="utf-8")
                reports.append(
                    SimpleNamespace(
                        file_path=str(report_path),
                        corp_name="sample",
                        stock_code="000000",
                        year=2024,
                        report_type="annual",
                        rcept_no=f"receipt-{index}",
                    )
                )
            manifest = canonical_store_manifest(collection_name="runtime")
            service = IngestService(
                _Fetcher(reports),
                _Parser(),
                _FailAfterFirstContextGenerator(),
                _Store(root),
                manifest,
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "synthetic later-report failure",
            ):
                service.ingest_company("sample", [2024], max_workers=2)

            self.assertEqual(read_store_manifest(root), manifest)
            service._assert_manifest_boundary()

    def test_partial_batch_records_manifest_before_indexing_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report_path = root / "report.xml"
            report_path.write_text("report", encoding="utf-8")
            report = SimpleNamespace(
                file_path=str(report_path),
                corp_name="sample",
                stock_code="000000",
                year=2024,
                report_type="annual",
                rcept_no="receipt-1",
            )
            manifest = canonical_store_manifest(collection_name="runtime")
            service = IngestService(
                _Fetcher([report]),
                _Parser(),
                _FailAfterFirstBatchContextGenerator(),
                _Store(root),
                manifest,
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "synthetic later-batch failure",
            ):
                service.ingest_company("sample", [2024], max_workers=2)

            self.assertEqual(read_store_manifest(root), manifest)

    def test_nonempty_unmanifested_store_is_not_auto_adopted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            service = IngestService(
                _Fetcher([]),
                _Parser(),
                _ContextGenerator(),
                _Store(temporary_directory, existing_docs=True),
                canonical_store_manifest(collection_name="runtime"),
            )

            with self.assertRaisesRegex(RuntimeError, "non-empty store"):
                service.ingest_company("sample", [2024], max_workers=1)


if __name__ == "__main__":
    unittest.main()
