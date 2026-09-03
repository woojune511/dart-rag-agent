import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.financial_router import get_router
from src.agent.financial_run_result import (
    FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
    FinancialRunResultV1,
)
from src.storage.store_manifest import StoreReadiness, canonical_store_manifest


class _Agent:
    def __init__(self) -> None:
        self.calls = []

    def run(
        self,
        question,
        *,
        report_scope=None,
        include_review_trace=False,
        include_debug_bundle=False,
    ):
        self.calls.append(
            {
                "question": question,
                "report_scope": report_scope,
                "thread": threading.current_thread().name,
            }
        )
        return FinancialRunResultV1(
            schema_version=FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
            agent_answer={
                "answer": "answer",
                "query_type": "qa",
                "companies": ["A"],
                "years": [2024],
                "citations": ["source"],
                "structured_result": {"ok": True},
                "resolved_calculation_trace": {},
            },
            review_trace={"review": True} if include_review_trace else None,
            debug_bundle={"debug": True} if include_debug_bundle else None,
        )


class _ConcurrentAgent(_Agent):
    def __init__(self) -> None:
        super().__init__()
        self._guard = threading.Lock()
        self.active_calls = 0
        self.max_active_calls = 0

    def run(self, question, **kwargs):
        with self._guard:
            self.active_calls += 1
            self.max_active_calls = max(
                self.max_active_calls,
                self.active_calls,
            )
        try:
            time.sleep(0.05)
            return super().run(question, **kwargs)
        finally:
            with self._guard:
                self.active_calls -= 1


class _IngestService:
    def __init__(self) -> None:
        self.calls = []

    def ingest_company(self, company, years, *, max_workers):
        self.calls.append(
            {
                "company": company,
                "years": list(years),
                "max_workers": max_workers,
                "thread": threading.current_thread().name,
            }
        )
        return {
            "files_fetched": 1,
            "chunks_added": 2,
            "reports_skipped": 0,
        }


class _FailingIngestService:
    def ingest_company(self, _company, _years, *, max_workers):
        raise RuntimeError("synthetic partial ingest failure")


class _RepairOnlyIngestService:
    def ingest_company(self, _company, _years, *, max_workers):
        return {
            "files_fetched": 1,
            "chunks_added": 0,
            "reports_processed": 1,
            "reports_skipped": 0,
        }


def _services(*, status="compatible", ready=True, degraded=False, agent=None):
    manifest = canonical_store_manifest(collection_name="runtime")
    readiness = StoreReadiness(
        status=status,
        ready=ready,
        reason=status,
        expected=manifest,
        actual=manifest if status == "compatible" else None,
        degraded=degraded,
    )
    agent = agent or _Agent()
    ingest = _IngestService()
    services = SimpleNamespace(
        expected_manifest=manifest,
        readiness=readiness,
        store=SimpleNamespace(
            bm25_docs=[],
            persist_directory="unused",
            force_bm25_only=False,
        ),
        agent=agent,
        ingest_service=ingest,
        operation_lock=asyncio.Lock(),
        contextual_ingest_max_workers=8,
    )
    # The API contract test does not touch a real store after ingest.
    services.refresh_readiness = lambda: readiness
    return services, agent, ingest


def _client(services):
    app = FastAPI()
    app.state.services = services
    app.include_router(get_router())
    return TestClient(app)


class FinancialAPIContractTests(unittest.TestCase):
    def test_synchronous_optional_clients_share_one_service_lock(self) -> None:
        from src.api.services import AppServices

        manifest = canonical_store_manifest(collection_name="runtime")
        services = AppServices(
            expected_manifest=manifest,
            readiness=StoreReadiness(
                status="compatible",
                ready=True,
                reason="compatible",
                expected=manifest,
                actual=manifest,
            ),
        )
        guard = threading.Lock()
        active = 0
        max_active = 0

        def use_shared_services():
            nonlocal active, max_active
            with services.serialized_sync_operation():
                with guard:
                    active += 1
                    max_active = max(max_active, active)
                try:
                    time.sleep(0.05)
                finally:
                    with guard:
                        active -= 1

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(lambda _index: use_shared_services(), range(2)))

        self.assertEqual(max_active, 1)

    def test_forced_bm25_startup_requires_persisted_search_data(self) -> None:
        from src.api.services import _has_persisted_bm25_source

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.assertFalse(_has_persisted_bm25_source(root))

            (root / "document_structure_graph.json").write_text(
                '{"nodes":{"chunk-1":{"text":"evidence"}}}',
                encoding="utf-8",
            )
            self.assertTrue(_has_persisted_bm25_source(root))

    def test_empty_unmanifested_chroma_restart_is_initializable(self) -> None:
        from src.api.services import (
            _has_persisted_bm25_source,
            _store_may_initialize,
        )

        manifest = canonical_store_manifest(collection_name="runtime")
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "chroma.sqlite3"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute("CREATE TABLE embeddings (id INTEGER)")
                connection.execute("CREATE TABLE embeddings_queue (seq_id INTEGER)")
                connection.commit()
            finally:
                connection.close()
            self.assertFalse(_has_persisted_bm25_source(root))
            readiness = StoreReadiness(
                status="missing",
                ready=False,
                reason="store manifest is missing",
                expected=manifest,
            )

            self.assertTrue(
                _store_may_initialize(
                    root,
                    readiness=readiness,
                    allow_degraded=False,
                )
            )

            connection = sqlite3.connect(database_path)
            try:
                connection.execute("INSERT INTO embeddings VALUES (1)")
                connection.commit()
            finally:
                connection.close()
            self.assertFalse(
                _store_may_initialize(
                    root,
                    readiness=readiness,
                    allow_degraded=False,
                )
            )

    def test_app_factory_reads_cors_from_project_dotenv_without_env_mutation(
        self,
    ) -> None:
        from fastapi.middleware.cors import CORSMiddleware
        from main import create_app

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / ".env").write_text(
                "DART_CORS_ALLOW_ORIGINS=https://one.example,https://two.example\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                before = dict(os.environ)
                app = create_app(project_root=root)
                self.assertEqual(dict(os.environ), before)

        middleware = next(
            item
            for item in app.user_middleware
            if item.cls is CORSMiddleware
        )
        self.assertEqual(
            middleware.kwargs["allow_origins"],
            ["https://one.example", "https://two.example"],
        )

    def test_app_settings_read_dotenv_before_service_configuration(self) -> None:
        from src.api.services import resolve_app_settings

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / ".env").write_text(
                "DART_STORE_PATH=dotenv-store\n"
                "DART_REPORTS_PATH=dotenv-reports\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"DART_STORE_PATH": "process-store"},
                clear=True,
            ):
                settings = resolve_app_settings(root)

        self.assertEqual(settings["DART_STORE_PATH"], "process-store")
        self.assertEqual(settings["DART_REPORTS_PATH"], "dotenv-reports")

    def test_openapi_declares_ingest_and_query_requests_as_json_bodies(self) -> None:
        services, _, _ = _services()
        app = FastAPI()
        app.state.services = services
        app.include_router(get_router())

        schema = app.openapi()
        for path in ("/api/ingest", "/api/query"):
            operation = schema["paths"][path]["post"]
            self.assertIn("application/json", operation["requestBody"]["content"])
            self.assertNotIn(
                "req",
                {
                    parameter.get("name")
                    for parameter in operation.get("parameters", [])
                },
            )

    def test_liveness_is_independent_but_readiness_is_strict(self) -> None:
        services, agent, _ = _services(status="missing", ready=False)
        with _client(services) as client:
            self.assertEqual(client.get("/api/health/live").status_code, 200)
            self.assertEqual(client.get("/api/health/ready").status_code, 503)
            self.assertEqual(client.get("/api/health").status_code, 503)
            response = client.post("/api/query", json={"question": "q"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(agent.calls, [])

    def test_query_runs_off_event_loop_and_preserves_report_scope(self) -> None:
        services, agent, _ = _services()
        report_scope = {
            "company": "A",
            "year": 2024,
            "source_receipts": ["r1"],
        }
        with _client(services) as client:
            response = client.post(
                "/api/query",
                json={"question": "q", "report_scope": report_scope},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(agent.calls[0]["report_scope"], report_scope)
        self.assertIn("worker", agent.calls[0]["thread"].lower())
        payload = response.json()
        self.assertNotIn("review_trace", payload)
        self.assertNotIn("debug_bundle", payload)

    def test_shared_agent_queries_are_serialized_before_threadpool_dispatch(
        self,
    ) -> None:
        agent = _ConcurrentAgent()
        services, _, _ = _services(agent=agent)
        with _client(services) as client:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        client.post,
                        "/api/query",
                        json={"question": f"q-{index}"},
                    )
                    for index in range(2)
                ]
                responses = [future.result() for future in futures]

        self.assertEqual([response.status_code for response in responses], [200, 200])
        self.assertEqual(agent.max_active_calls, 1)

    def test_review_and_debug_are_opt_in(self) -> None:
        services, _, _ = _services()
        with _client(services) as client:
            response = client.post(
                "/api/query",
                json={
                    "question": "q",
                    "include_review_trace": True,
                    "include_debug_bundle": True,
                },
            )
        payload = response.json()
        self.assertEqual(payload["review_trace"], {"review": True})
        self.assertEqual(payload["debug_bundle"], {"debug": True})

    def test_degraded_mode_is_explicit_in_query_response(self) -> None:
        services, _, _ = _services(
            status="degraded",
            ready=True,
            degraded=True,
        )
        with _client(services) as client:
            response = client.post("/api/query", json={"question": "q"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["retrieval_readiness"]["degraded"])

    def test_ingest_runs_in_threadpool(self) -> None:
        services, _, ingest = _services()
        with _client(services) as client:
            response = client.post(
                "/api/ingest",
                json={"company": "A", "years": [2024]},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("worker", ingest.calls[0]["thread"].lower())

    def test_sidecar_only_repair_is_a_successful_ingest(self) -> None:
        services, _, _ = _services()
        services.ingest_service = _RepairOnlyIngestService()
        with _client(services) as client:
            response = client.post(
                "/api/ingest",
                json={"company": "A", "years": [2024]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["chunks_added"], 0)

    def test_failed_ingest_refreshes_readiness(self) -> None:
        services, _, _ = _services(status="missing", ready=False)
        services.ingest_service = _FailingIngestService()
        compatible = StoreReadiness(
            status="compatible",
            ready=True,
            reason="compatible",
            expected=services.expected_manifest,
            actual=services.expected_manifest,
        )

        def refresh_readiness():
            services.readiness = compatible
            return compatible

        services.refresh_readiness = refresh_readiness
        with _client(services) as client:
            failed = client.post(
                "/api/ingest",
                json={"company": "A", "years": [2024]},
            )
            ready = client.get("/api/health/ready")

        self.assertEqual(failed.status_code, 502)
        self.assertEqual(ready.status_code, 200)
        self.assertTrue(ready.json()["ready"])


if __name__ == "__main__":
    unittest.main()
