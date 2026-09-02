import threading
import unittest
from types import SimpleNamespace

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


def _services(*, status="compatible", ready=True, degraded=False):
    manifest = canonical_store_manifest(collection_name="runtime")
    readiness = StoreReadiness(
        status=status,
        ready=ready,
        reason=status,
        expected=manifest,
        actual=manifest if status == "compatible" else None,
        degraded=degraded,
    )
    agent = _Agent()
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


if __name__ == "__main__":
    unittest.main()
