"""Public API errors must not disclose arbitrary provider exception contents."""

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.financial_router import get_router
from src.storage.store_manifest import StoreReadiness, canonical_store_manifest


class APIErrorBoundaryTests(unittest.TestCase):
    def test_query_ingest_and_companies_do_not_publish_raw_exception_or_log_it(self):
        secret_marker = "SYNTHETIC_SECRET_MUST_NOT_LEAK"
        error = RuntimeError(f"https://provider.invalid/api?crtfc_key={secret_marker}")
        for path, payload, status in (
            ("/api/query", {"question": "synthetic question"}, 500),
            ("/api/ingest", {"company": "Example", "years": [2031]}, 502),
            ("/api/companies", None, 500),
        ):
            with self.subTest(path=path):
                manifest = canonical_store_manifest(collection_name="synthetic")
                services = SimpleNamespace(
                    readiness=StoreReadiness("compatible", True, "ready", manifest, manifest),
                    agent=Mock(), ingest_service=Mock(),
                    store=SimpleNamespace(vector_store=Mock()),
                    operation_lock=asyncio.Lock(), contextual_ingest_max_workers=1,
                    refresh_readiness=Mock(),
                )
                services.agent.run.side_effect = error
                services.ingest_service.ingest_company.side_effect = error
                services.store.vector_store.get.side_effect = error
                app = FastAPI()
                app.state.services = services
                app.include_router(get_router())
                with TestClient(app) as client:
                    with self.assertLogs("src.api.financial_router", level="ERROR") as captured:
                        response = client.get(path) if payload is None else client.post(path, json=payload)
                self.assertEqual(response.status_code, status)
                self.assertNotIn(secret_marker, response.text)
                self.assertNotIn("provider.invalid", response.text)
                self.assertNotIn(secret_marker, " ".join(captured.output))
                self.assertIn("RuntimeError", " ".join(captured.output))
                if path == "/api/ingest":
                    services.refresh_readiness.assert_called_once()


if __name__ == "__main__":
    unittest.main()
