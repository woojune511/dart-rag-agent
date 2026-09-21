"""Application profile wiring with real OpenAI serialization and no network."""

import json
import os
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import httpx
from openai import APIStatusError

from src.agent.financial_graph import FinancialAgent
from src.api.services import build_app_services, resolve_app_settings
from src.config.llm_profiles import app_llm_routing_config
from src.storage.store_manifest import (
    StoreReadiness, assess_store_readiness, canonical_store_manifest, write_store_manifest,
)
from tests.test_openai_compiler_transport import Payload, ROUTE, response_body


class AppLLMProfileTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, {
            "GOOGLE_API_KEY": "offline-google-key",
            "OPENAI_API_KEY": "offline-openai-key",
            "LANGSMITH_TRACING": "false",
            "LANGCHAIN_TRACING_V2": "false",
            "GOOGLE_GENAI_USE_VERTEXAI": "false",
            "ANONYMIZED_TELEMETRY": "false",
        }, clear=True))
        # Windows/ASGI clients need the local asyncio self-pipe, never external IO.
        connect = socket.socket.connect

        def local_only(sock, address):
            if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
                return connect(sock, address)
            raise AssertionError("External network forbidden")

        self.enterContext(patch.object(socket.socket, "connect", local_only))
        self.enterContext(patch.object(socket.socket, "connect_ex", side_effect=AssertionError("Network forbidden")))
        self.enterContext(patch.object(socket, "create_connection", side_effect=AssertionError("Network forbidden")))
        self.enterContext(patch("src.agent.financial_graph._load_env_once"))

    def prepare_services(self, *, ready=True):
        expected = canonical_store_manifest(collection_name="app-profile-test")
        self.readiness = StoreReadiness(
            status="compatible" if ready else "incomplete", ready=ready,
            reason="" if ready else "stored source is incomplete", expected=expected,
        )
        self.enterContext(patch("src.api.services.assess_store_readiness", return_value=self.readiness))
        self.enterContext(patch("src.api.services._store_may_initialize", return_value=ready))
        store = SimpleNamespace(
            persist_directory=str(self.root / "store"), embeddings=object(),
            embedding_spec={}, validate_source_integrity=lambda: {"ready": True},
        )
        self.store_factory = self.enterContext(patch("src.storage.vector_store.VectorStoreManager", return_value=store))
        self.google = SimpleNamespace(model="gemini-2.5-flash")
        self.google_factory = self.enterContext(patch("langchain_google_genai.ChatGoogleGenerativeAI", return_value=self.google))
        self.router_factory = self.enterContext(patch("src.routing.QueryRouter"))
        self.enterContext(patch.object(FinancialAgent, "_build_graph", return_value=object()))
        self.context_factory = self.enterContext(patch("src.ingestion.context_generator.ContextGenerator"))
        self.enterContext(patch("src.ingestion.dart_fetcher.DARTFetcher"))
        self.enterContext(patch("src.processing.financial_parser.FinancialParser"))
        self.enterContext(patch("src.ingestion.ingest_service.IngestService"))

    def test_missing_or_google_selection_preserves_defaults(self):
        self.prepare_services()
        for profile in ("", "google", "  google  "):
            with self.subTest(profile=profile):
                os.environ["DART_LLM_PROFILE"] = profile
                services = build_app_services(project_root=self.root)
                self.assertEqual(services.agent.routing_config, {})
                self.assertEqual(set(services.agent.llm_routes), {"default"})
                self.assertIs(services.agent._llm_for_phase("program_compilation"), self.google)

    def test_profile_preserves_reviewed_compiler_options_and_owns_its_data(self):
        config = app_llm_routing_config("openai_compiler")
        self.assertEqual(config, {"llm_routes": {"program_compilation": {k: v for k, v in ROUTE.items() if k != "api_key"}}})
        config["llm_routes"]["program_compilation"]["model"] = "caller-change"
        self.assertEqual(app_llm_routing_config("openai_compiler")["llm_routes"]["program_compilation"]["model"], ROUTE["model"])

    def test_dotenv_selection_and_process_override_without_resolver_mutation(self):
        (self.root / ".env").write_text("DART_LLM_PROFILE=openai_compiler\n", encoding="utf-8")
        before = dict(os.environ)
        self.assertEqual(resolve_app_settings(self.root)["DART_LLM_PROFILE"], "openai_compiler")
        self.assertEqual(dict(os.environ), before)
        for override in ("google", ""):
            with patch.dict(os.environ, DART_LLM_PROFILE=override):
                self.assertEqual(resolve_app_settings(self.root)["DART_LLM_PROFILE"], override)

    def test_invalid_selection_fails_before_store_startup_without_echoing_value(self):
        self.prepare_services()
        os.environ["DART_LLM_PROFILE"] = "private-invalid-setting"
        with self.assertRaisesRegex(ValueError, "DART_LLM_PROFILE") as raised:
            build_app_services(project_root=self.root)
        self.assertNotIn("private-invalid-setting", str(raised.exception))
        self.store_factory.assert_not_called()
        self.router_factory.assert_not_called()

    def test_missing_openai_key_fails_before_store_or_canonical_embeddings(self):
        self.prepare_services()
        os.environ["DART_LLM_PROFILE"] = "openai_compiler"
        for value in (None, "", "   "):
            with self.subTest(value=value), patch.dict(os.environ):
                if value is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = value
                with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                    build_app_services(project_root=self.root)
        self.store_factory.assert_not_called()
        self.router_factory.assert_not_called()

    def test_openai_selection_does_not_bypass_store_readiness(self):
        self.prepare_services(ready=False)
        os.environ["DART_LLM_PROFILE"] = "openai_compiler"
        services = build_app_services(project_root=self.root)
        self.assertFalse(services.readiness.ready)
        self.assertIsNone(services.agent)
        self.store_factory.assert_not_called()

    def test_collection_setting_obeys_dotenv_and_process_precedence(self):
        (self.root / ".env").write_text("DART_COLLECTION_NAME=stored-reports\n", encoding="utf-8")
        before = dict(os.environ)
        self.assertEqual(resolve_app_settings(self.root)["DART_COLLECTION_NAME"], "stored-reports")
        self.assertEqual(dict(os.environ), before)
        with patch.dict(os.environ, DART_COLLECTION_NAME="process-reports"):
            self.assertEqual(resolve_app_settings(self.root)["DART_COLLECTION_NAME"], "process-reports")

    def test_explicit_collection_reaches_store_and_readiness_without_adoption(self):
        self.prepare_services()
        store_path = self.root / "store"
        manifest = canonical_store_manifest(collection_name="stored-reports")
        manifest_path = write_store_manifest(store_path, manifest)
        original = manifest_path.read_bytes()
        with patch.dict(os.environ, DART_STORE_PATH=str(store_path), DART_COLLECTION_NAME=" stored-reports "), \
                patch("src.api.services.assess_store_readiness", wraps=assess_store_readiness):
            services = build_app_services(project_root=self.root)
        self.assertTrue(services.readiness.ready)
        self.assertEqual(services.expected_manifest, manifest)
        self.assertEqual(self.store_factory.call_args.kwargs["collection_name"], "stored-reports")
        self.assertEqual(manifest_path.read_bytes(), original)

    def test_collection_selection_keeps_default_and_strict_identity_checks(self):
        from src.api.services import _store_may_initialize
        from src.storage.vector_store import DEFAULT_COLLECTION_NAME

        self.prepare_services()
        store_path = self.root / "store"
        for collection, provider in (("stored-reports", "openai"), (DEFAULT_COLLECTION_NAME, "google")):
            with self.subTest(collection=collection, provider=provider):
                path = write_store_manifest(store_path, canonical_store_manifest(
                    collection_name=collection, embedding_provider=provider,
                ))
                original = path.read_bytes()
                with patch.dict(os.environ, DART_STORE_PATH=str(store_path), DART_COLLECTION_NAME=" "), \
                        patch("src.api.services.assess_store_readiness", wraps=assess_store_readiness), \
                        patch("src.api.services._store_may_initialize", wraps=_store_may_initialize):
                    services = build_app_services(project_root=self.root)
                self.assertEqual(services.expected_manifest.collection_name, DEFAULT_COLLECTION_NAME)
                self.assertEqual(services.readiness.status, "mismatch")
                self.assertFalse(services.readiness.ready)
                self.assertIsNone(services.agent)
                self.assertEqual(path.read_bytes(), original)
        self.store_factory.assert_not_called()

    def test_services_route_only_compiler_through_actual_responses_adapter(self):
        self.prepare_services()
        (self.root / ".env").write_text("DART_LLM_PROFILE=openai_compiler\n", encoding="utf-8")
        services = build_app_services(project_root=self.root)
        agent = services.agent
        self.assertEqual(set(agent.llm_routes), {"default", "program_compilation"})
        for phase in ("routing", "requirement_planning", "evidence_extraction"):
            self.assertIs(agent._llm_for_phase(phase), self.google)
        self.assertIs(self.router_factory.call_args.kwargs["llm"], self.google)
        self.context_factory.assert_called_once_with(self.google, services.store)
        calls = []

        def send(request, **kwargs):
            self.assertEqual(str(request.url), "https://api.openai.com/v1/responses")
            calls.append(json.loads(request.content))
            return httpx.Response(200, request=request, json=response_body(dict(value=2, comment=None, flags=[])))

        with patch.object(httpx.Client, "send", side_effect=send):
            result = agent._llm_for_phase("program_compilation").with_structured_output(Payload, include_raw=True).invoke("Anonymous configuration check")
        self.assertIsNone(result["parsing_error"])
        self.assertEqual(result["parsed"].value, 2)
        self.assertEqual(len(calls), 1)
        body = calls[0]
        self.assertEqual(body["model"], "gpt-6-astra")
        self.assertEqual(body["max_output_tokens"], 5120)
        self.assertEqual(body["reasoning"], {"effort": "medium"})
        self.assertEqual(body["service_tier"], "default")
        self.assertFalse(body["store"])
        self.assertNotIn("temperature", body)
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertNotIn("DART_LLM_PROFILE", json.dumps(body))

    def test_configured_compiler_has_no_transport_retry_or_google_fallback(self):
        self.prepare_services()
        os.environ["DART_LLM_PROFILE"] = "openai_compiler"
        agent = build_app_services(project_root=self.root).agent
        calls = []

        def send(request, **kwargs):
            calls.append(request.url.host)
            return httpx.Response(503, request=request, json={"error": {"message": "offline unavailable", "type": "server_error"}})

        with patch.object(httpx.Client, "send", side_effect=send), self.assertRaises(APIStatusError):
            agent._llm_for_phase("program_compilation").with_structured_output(Payload).invoke("Anonymous failure check")
        self.assertEqual(calls, ["api.openai.com"])
        self.google_factory.assert_called_once()

    def test_fastapi_lifespan_uses_project_profile_from_shared_services(self):
        from main import create_app

        self.prepare_services()
        (self.root / ".env").write_text("DART_LLM_PROFILE=openai_compiler\n", encoding="utf-8")
        app = create_app(project_root=self.root)
        with patch("main._configure_logging"), TestClient(app) as client:
            self.assertEqual(client.get("/api/health/ready").status_code, 200)
            self.assertIn("program_compilation", app.state.services.agent.llm_routes)
            self.assertEqual(app.state.services.agent.routing_config, app_llm_routing_config("openai_compiler"))

    def test_full_openai_profile_starts_without_google_and_separates_ingest(self):
        from main import create_app

        self.prepare_services()
        os.environ.pop("GOOGLE_API_KEY")
        (self.root / ".env").write_text("DART_LLM_PROFILE=openai\n", encoding="utf-8")
        app = create_app(project_root=self.root)
        with patch("main._configure_logging"), TestClient(app) as client:
            self.assertEqual(client.get("/api/health/ready").status_code, 200)
            agent = app.state.services.agent
            self.assertEqual(agent.llm.model_name, "gpt-5.6-terra")
            self.assertIs(self.router_factory.call_args.kwargs["llm"], agent.llm)
            for phase in ("routing", "requirement_planning", "evidence_extraction"):
                self.assertIs(agent._llm_for_phase(phase), agent.llm)
            context = agent.llm_routes["context_generation"]
            self.assertEqual(context.model_name, "gpt-5.6-luna")
            self.context_factory.assert_called_once_with(context, app.state.services.store)
        self.google_factory.assert_not_called()
        routes = app_llm_routing_config("openai")["llm_routes"]
        self.assertEqual(routes["program_compilation"], app_llm_routing_config("openai_compiler")["llm_routes"]["program_compilation"])
        routes["program_compilation"]["model"] = "caller-change"
        self.assertEqual(app_llm_routing_config("openai")["llm_routes"]["program_compilation"]["model"], "gpt-6-astra")

    def test_full_openai_checks_key_and_readiness_before_initialization(self):
        self.prepare_services()
        os.environ["DART_LLM_PROFILE"] = "openai"
        os.environ.pop("GOOGLE_API_KEY")
        os.environ.pop("OPENAI_API_KEY")
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            build_app_services(project_root=self.root)
        self.store_factory.assert_not_called()
        self.google_factory.assert_not_called()
        self.router_factory.assert_not_called()
        with patch("src.api.services._store_may_initialize", return_value=False):
            self.assertIsNone(build_app_services(project_root=self.root).agent)

    def test_real_router_and_nested_planner_schemas_use_strict_responses(self):
        from jsonschema import Draft202012Validator
        from src.agent.financial_graph_models import RequirementPlannerOutput
        from src.routing.types import QueryRoutingDecision
        from tests.planner_period_wire_test_support import unspecified_period_payload

        self.prepare_services()
        os.environ["DART_LLM_PROFILE"] = "openai"
        agent = build_app_services(project_root=self.root).agent
        values = [
            QueryRoutingDecision(intent="qa", format_preference="paragraph"),
            RequirementPlannerOutput(obligations=[
                dict(kind="narrative", label="anonymous activity", request_unit_ids=["q1"],
                     display_unit="", display_format="paragraph",
                     scope=dict(measurement_period=dict(kind="unspecified")),
                     evidence_requirements=[dict(label="anonymous source", scope=dict(measurement_period=dict(kind="unspecified")))]),
                dict(kind="direct_value", label="anonymous quantity", request_unit_ids=["q1"],
                     display_unit="COUNT", scope=dict(measurement_period=dict(kind="unspecified"))),
                dict(kind="derived_value", label="anonymous rate", request_unit_ids=["q1"],
                     display_unit="%", scope=dict(measurement_period=dict(kind="unspecified"))),
            ]),
        ]
        calls = []
        for value in values:
            def send(request, **kwargs):
                self.assertEqual(str(request.url), "https://api.openai.com/v1/responses")
                calls.append(json.loads(request.content))
                body = response_body(unspecified_period_payload(value))
                body["model"] = "gpt-5.6-terra"
                return httpx.Response(200, request=request, json=body)

            with self.subTest(schema=type(value).__name__), patch.object(httpx.Client, "send", side_effect=send):
                parsed = agent.llm.with_structured_output(type(value)).invoke("Anonymous schema check")
            self.assertEqual(parsed, value)
        self.assertEqual(len(calls), 2)
        for body in calls:
            self.assertEqual(body["model"], "gpt-5.6-terra")
            self.assertEqual(body["reasoning"], {"effort": "low"})
            self.assertEqual(body["max_output_tokens"], 8192)
            self.assertFalse(body["store"])
            self.assertNotIn("temperature", body)
            self.assertTrue(body["text"]["format"]["strict"])
        schema = calls[1]["text"]["format"]["schema"]
        self.assertEqual(schema["type"], "object")
        self.assertNotIn("anyOf", schema)
        branches = schema["properties"]["obligations"]["items"]["anyOf"]
        self.assertEqual(len(branches), 3)
        for branch in branches:
            nested = schema["$defs"][branch["$ref"].rsplit("/", 1)[1]]
            self.assertEqual(set(nested["required"]), set(nested["properties"]))
            self.assertFalse(nested["additionalProperties"])
        validator = Draft202012Validator(schema)
        payload = unspecified_period_payload(values[1])
        validator.validate(payload)
        payload["obligations"][0]["display_unit"] = "text"
        self.assertFalse(validator.is_valid(payload))
        payload = unspecified_period_payload(values[1])
        payload["obligations"][1]["evidence_requirements"] = payload["obligations"][0]["evidence_requirements"]
        self.assertFalse(validator.is_valid(payload))
        direct_branch = next(schema["$defs"][branch["$ref"].rsplit("/", 1)[1]] for branch in branches
            if schema["$defs"][branch["$ref"].rsplit("/", 1)[1]]["properties"]["kind"].get("const") == "direct_value")
        self.assertEqual(direct_branch["properties"]["evidence_requirements"]["maxItems"], 0)
        self.google_factory.assert_not_called()

    def test_full_openai_failure_does_not_retry_or_create_google_client(self):
        self.prepare_services()
        os.environ["DART_LLM_PROFILE"] = "openai"
        agent = build_app_services(project_root=self.root).agent
        for phase in ("routing", "requirement_planning", "context_generation"):
            calls = []
            def send(request, **kwargs):
                calls.append(request.url.host)
                return httpx.Response(503, request=request, json={"error": {"message": "offline unavailable", "type": "server_error"}})

            with self.subTest(phase=phase), patch.object(httpx.Client, "send", side_effect=send), self.assertRaises(APIStatusError):
                agent._llm_for_phase(phase).invoke("Anonymous failure check")
            self.assertEqual(calls, ["api.openai.com"])
        self.google_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
