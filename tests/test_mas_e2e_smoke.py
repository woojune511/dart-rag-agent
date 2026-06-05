import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops import mas_e2e_smoke
from src.config.report_scoped_cache import (
    CACHE_ENTRY_SOURCE_LOCAL_INDEX,
    REPORT_CACHE_ENTRY_VERSION,
    report_cache_key_id,
)
from src.storage.report_cache_index import ReportCacheIndex


class MasE2ESmokeTests(unittest.TestCase):
    def test_default_smoke_profile_builds_value_contract(self) -> None:
        contract = mas_e2e_smoke.build_smoke_value_contract(
            report_scope=mas_e2e_smoke.DEFAULT_SCOPE,
            queries=list(reversed(mas_e2e_smoke.DEFAULT_QUERIES)),
        )

        self.assertEqual(contract["source"], "mas_e2e_smoke_default_profile")
        self.assertEqual(contract["scope_match"]["rcept_no"], "20240312000736")
        self.assertEqual(contract["assertions"][0]["case_index"], 1)
        self.assertEqual(contract["assertions"][0]["name"], "samsung_2023_rnd_ratio")
        self.assertIn("10.95%", contract["assertions"][0]["must_include"])
        self.assertEqual(contract["assertions"][1]["case_index"], 2)
        self.assertEqual(contract["assertions"][1]["name"], "samsung_2023_operating_margin")

    def test_run_smoke_embeds_value_contract_for_default_profile(self) -> None:
        noop_node = lambda _state: {}

        def fake_run_mas_graph(_query, **_kwargs):
            return {
                "tasks": {},
                "artifacts": {},
                "critic_reports": [],
                "execution_trace": [],
                "final_report_record": {"status": "ok"},
                "task_artifact_trace": {"integrity_status": "ok"},
            }

        with (
            patch.object(mas_e2e_smoke, "VectorStoreManager", return_value=object()),
            patch.object(mas_e2e_smoke, "build_financial_orchestrator_plan_node", return_value=noop_node),
            patch.object(mas_e2e_smoke, "build_financial_orchestrator_merge_node", return_value=noop_node),
            patch.object(mas_e2e_smoke, "build_financial_analyst_node", return_value=noop_node),
            patch.object(mas_e2e_smoke, "build_financial_researcher_node", return_value=noop_node),
            patch.object(mas_e2e_smoke, "run_mas_graph", side_effect=fake_run_mas_graph),
        ):
            payload = mas_e2e_smoke.run_smoke(
                store_dir=Path("store"),
                collection_name="collection",
                queries=list(mas_e2e_smoke.DEFAULT_QUERIES),
                report_scope=dict(mas_e2e_smoke.DEFAULT_SCOPE),
            )

        self.assertEqual(payload["value_contract"]["source"], "mas_e2e_smoke_default_profile")
        self.assertEqual(len(payload["value_contract"]["assertions"]), 2)

    def test_run_smoke_surfaces_replan_and_integrity_contract(self) -> None:
        graph_calls = []
        noop_node = lambda _state: {}

        def fake_run_mas_graph(query, **kwargs):
            graph_calls.append({"query": query, **kwargs})
            return {
                "tasks": {
                    "task_1": {"status": "failed"},
                    "task_2": {"status": "completed"},
                },
                "artifacts": {
                    "task_2": {
                        "content": {"answer": "repaired answer"},
                    },
                    "task_1": {
                        "content": {
                            "resolved_calculation_trace": {
                                "report_cache_candidate": {
                                    "status": "requires_evidence_verification",
                                    "reasons": ["derived_result"],
                                    "key_id": "abc123",
                                    "key": {
                                        "company": "ACME",
                                        "year": "2023",
                                    },
                                    "retrieval_bypass": {
                                        "status": "blocked",
                                        "eligible": False,
                                        "enabled": False,
                                        "mode": "trace_only",
                                        "reasons": ["candidate_not_reusable"],
                                    },
                                }
                            }
                        },
                        "payload": {
                            "resolved_calculation_trace": {
                                "report_cache_candidate": {
                                    "status": "requires_evidence_verification",
                                    "reasons": ["derived_result"],
                                    "key_id": "abc123",
                                    "key": {
                                        "company": "ACME",
                                        "year": "2023",
                                    },
                                    "retrieval_bypass": {
                                        "status": "blocked",
                                        "eligible": False,
                                        "enabled": False,
                                        "mode": "trace_only",
                                        "reasons": ["candidate_not_reusable"],
                                    },
                                }
                            }
                        },
                    }
                },
                "critic_reports": [{"target_task_id": "task_2", "passed": True}],
                "critic_feedback": "Critic passed all artifacts (Deterministic)",
                "planner_feedback": None,
                "replan_budget": 1,
                "replan_count": 1,
                "execution_trace": [
                    "Orchestrator requested replan on integrity errors",
                    "Orchestrator replanned 1 tasks",
                    "Orchestrator synthesized final report",
                ],
                "final_report": "merged repaired answer",
                "final_report_record": {
                    "status": "ok",
                    "source_artifact_ids": ["task_2"],
                },
                "task_artifact_trace": {
                    "integrity_status": "ok",
                    "integrity_issue_count": 0,
                },
            }

        with (
            patch.object(mas_e2e_smoke, "VectorStoreManager", return_value=object()),
            patch.object(mas_e2e_smoke, "build_financial_orchestrator_plan_node", return_value=noop_node),
            patch.object(mas_e2e_smoke, "build_financial_orchestrator_merge_node", return_value=noop_node),
            patch.object(mas_e2e_smoke, "build_financial_analyst_node", return_value=noop_node),
            patch.object(mas_e2e_smoke, "build_financial_researcher_node", return_value=noop_node),
            patch.object(mas_e2e_smoke, "run_mas_graph", side_effect=fake_run_mas_graph),
        ):
            payload = mas_e2e_smoke.run_smoke(
                store_dir=Path("store"),
                collection_name="collection",
                queries=["question"],
                replan_budget=1,
                report_scope=mas_e2e_smoke._report_scope(year="2023", rcept_no="20240312000736"),
            )

        self.assertEqual(graph_calls[0]["replan_budget"], 1)
        self.assertEqual(graph_calls[0]["report_scope"]["year"], "2023")
        self.assertEqual(graph_calls[0]["report_scope"]["rcept_no"], "20240312000736")
        self.assertTrue(callable(graph_calls[0]["orchestrator_plan_node"]))
        self.assertTrue(callable(graph_calls[0]["orchestrator_merge_node"]))
        self.assertEqual(payload["replan_budget"], 1)
        self.assertEqual(payload["embedding_compatibility"]["status"], "unknown")
        self.assertEqual(payload["report_scope"]["year"], "2023")
        self.assertEqual(payload["summary"]["replan_routed_count"], 1)
        self.assertEqual(payload["summary"]["blocked_count"], 0)
        self.assertEqual(payload["summary"]["integrity_error_count"], 0)
        case = payload["cases"][0]
        self.assertEqual(case["replan_count"], 1)
        self.assertFalse(case["replan_requested"])
        self.assertTrue(case["replan_routed"])
        self.assertEqual(case["task_artifact_integrity_status"], "ok")
        self.assertEqual(case["task_artifact_integrity_issue_count"], 0)
        self.assertEqual(case["artifact_answers"]["task_2"], "repaired answer")
        self.assertEqual(payload["summary"]["report_cache_candidate_count"], 1)
        self.assertEqual(
            payload["summary"]["report_cache_candidate_status_counts"],
            {"requires_evidence_verification": 1},
        )
        self.assertEqual(
            payload["summary"]["report_cache_candidate_reason_counts"],
            {"derived_result": 1},
        )
        self.assertEqual(case["report_cache_candidates"]["count"], 1)
        self.assertEqual(
            case["report_cache_candidates"]["items"][0]["artifact_id"],
            "task_1",
        )
        self.assertEqual(
            case["report_cache_candidates"]["items"][0]["path"],
            "artifacts.task_1.content.resolved_calculation_trace",
        )
        self.assertEqual(
            case["report_cache_candidates"]["items"][0]["retrieval_bypass"]["status"],
            "blocked",
        )
        self.assertFalse(
            case["report_cache_candidates"]["items"][0]["retrieval_bypass"]["enabled"]
        )
        self.assertNotIn("value_contract", payload)

    def test_run_smoke_counts_blocked_integrity_error(self) -> None:
        noop_node = lambda _state: {}

        def fake_run_mas_graph(_query, **_kwargs):
            return {
                "tasks": {},
                "artifacts": {},
                "critic_reports": [],
                "execution_trace": ["Orchestrator blocked final report on integrity errors"],
                "final_report_record": {"status": "blocked"},
                "task_artifact_trace": {
                    "integrity_status": "error",
                    "integrity_issue_count": 1,
                },
            }

        with (
            patch.object(mas_e2e_smoke, "VectorStoreManager", return_value=object()),
            patch.object(mas_e2e_smoke, "build_financial_orchestrator_plan_node", return_value=noop_node),
            patch.object(mas_e2e_smoke, "build_financial_orchestrator_merge_node", return_value=noop_node),
            patch.object(mas_e2e_smoke, "build_financial_analyst_node", return_value=noop_node),
            patch.object(mas_e2e_smoke, "build_financial_researcher_node", return_value=noop_node),
            patch.object(mas_e2e_smoke, "run_mas_graph", side_effect=fake_run_mas_graph),
        ):
            payload = mas_e2e_smoke.run_smoke(
                store_dir=Path("store"),
                collection_name="collection",
                queries=["question"],
                replan_budget=0,
            )

        self.assertEqual(payload["summary"]["replan_routed_count"], 0)
        self.assertEqual(payload["summary"]["blocked_count"], 1)
        self.assertEqual(payload["summary"]["integrity_error_count"], 1)

    def test_run_smoke_surfaces_trace_only_cache_index_diagnostics(self) -> None:
        noop_node = lambda _state: {}
        analyst_routing_configs = []
        key = {
            "company": "ACME",
            "report_type": "annual",
            "rcept_no": "r1",
            "year": "2023",
            "metric_label": "metric",
            "period": "2023",
            "consolidation_scope": "consolidated",
            "statement_type": "statement",
            "source_section": "section",
            "source_table_id": "section::table:1",
        }
        entry = {
            "entry_version": REPORT_CACHE_ENTRY_VERSION,
            "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
            "key": key,
            "key_id": report_cache_key_id(key),
            "value": {
                "kind": "calculation_result",
                "rendered_value": "123",
                "answer_slots": {"primary_value": {"display": "123", "raw_value": "123"}},
                "calculation_trace": {
                    "calculation_result": {"status": "ok", "rendered_value": "123"},
                    "calculation_operands": [{"label": "metric", "raw_value": "123"}],
                },
                "citations": ["[ACME | 2023 | section]"],
                "evidence_items": [{"source_anchor": "section", "claim": "metric was 123"}],
            },
            "provenance": {"source_row_ids": ["row-1"], "evidence_refs": ["ev-1"], "source_anchor": "section"},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "report-cache-index.json"
            index_path.write_text(json.dumps([entry], ensure_ascii=False), encoding="utf-8")
            lookup_diagnostics = ReportCacheIndex(index_path).lookup_diagnostics(key)
            retrieval_debug_trace = {
                "report_cache_index_diagnostics": {
                    **lookup_diagnostics,
                    "lookup_attempted": True,
                    "normal_retrieval_executed": True,
                    "executed_query_count": 1,
                }
            }

            def fake_build_financial_analyst_node(_vsm, **kwargs):
                analyst_routing_configs.append(dict(kwargs.get("routing_config") or {}))
                return noop_node

            def fake_run_mas_graph(_query, **_kwargs):
                return {
                    "tasks": {},
                    "artifacts": {
                        "task_1": {
                            "content": {"retrieval_debug_trace": retrieval_debug_trace},
                            "payload": {"retrieval_debug_trace": retrieval_debug_trace},
                        }
                    },
                    "critic_reports": [],
                    "execution_trace": [],
                    "final_report_record": {"status": "ok"},
                    "task_artifact_trace": {"integrity_status": "ok"},
                }

            with (
                patch.object(mas_e2e_smoke, "VectorStoreManager", return_value=object()),
                patch.object(mas_e2e_smoke, "build_financial_orchestrator_plan_node", return_value=noop_node),
                patch.object(mas_e2e_smoke, "build_financial_orchestrator_merge_node", return_value=noop_node),
                patch.object(mas_e2e_smoke, "build_financial_analyst_node", side_effect=fake_build_financial_analyst_node),
                patch.object(mas_e2e_smoke, "build_financial_researcher_node", return_value=noop_node),
                patch.object(mas_e2e_smoke, "run_mas_graph", side_effect=fake_run_mas_graph),
            ):
                payload = mas_e2e_smoke.run_smoke(
                    store_dir=Path("store"),
                    collection_name="collection",
                    queries=["question"],
                    report_cache_index_path=index_path,
                )

        self.assertEqual(analyst_routing_configs[0]["report_cache_index_path"], str(index_path))
        self.assertEqual(payload["report_cache_index_path"], str(index_path))
        self.assertEqual(payload["summary"]["report_cache_index_diagnostic_count"], 1)
        self.assertEqual(payload["summary"]["report_cache_index_status_counts"], {"trace_only": 1})
        self.assertEqual(payload["summary"]["report_cache_index_lookup_attempted_count"], 1)
        self.assertEqual(payload["summary"]["report_cache_index_match_count"], 1)
        self.assertEqual(payload["summary"]["report_cache_index_readable_match_count"], 1)
        self.assertEqual(payload["summary"]["report_cache_index_rehydration_ready_match_count"], 1)
        self.assertEqual(payload["summary"]["report_cache_index_rehydration_blocked_match_count"], 0)
        self.assertEqual(payload["summary"]["report_cache_index_rehydration_reason_counts"], {})
        self.assertEqual(payload["summary"]["report_cache_index_normal_retrieval_count"], 1)
        diagnostics = payload["cases"][0]["report_cache_index_diagnostics"]
        self.assertEqual(diagnostics["count"], 1)
        self.assertEqual(diagnostics["items"][0]["status"], "trace_only")
        self.assertFalse(diagnostics["items"][0]["enabled"])
        self.assertFalse(diagnostics["items"][0]["serving_enabled"])
        self.assertTrue(diagnostics["items"][0]["normal_retrieval_executed"])
        self.assertEqual(diagnostics["items"][0]["match_count"], 1)
        self.assertEqual(diagnostics["items"][0]["readable_match_count"], 1)
        self.assertEqual(diagnostics["items"][0]["rehydration_ready_match_count"], 1)
        self.assertEqual(diagnostics["items"][0]["rehydration_blocked_match_count"], 0)

    def test_run_smoke_records_compatible_store_embedding_signature(self) -> None:
        noop_node = lambda _state: {}
        runtime_spec = {
            "provider": "openai",
            "model_name": "text-embedding-3-large",
            "dimension": 3072,
        }

        def fake_run_mas_graph(_query, **_kwargs):
            return {
                "tasks": {},
                "artifacts": {},
                "critic_reports": [],
                "execution_trace": [],
                "final_report_record": {"status": "ok"},
                "task_artifact_trace": {"integrity_status": "ok"},
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            store_dir = Path(temp_dir)
            (store_dir / "benchmark_cache_meta.json").write_text(
                json.dumps(
                    {
                        "store_signature": {
                            "collection_name": "collection",
                            "embedding": runtime_spec,
                        }
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(mas_e2e_smoke, "get_embedding_runtime_spec", return_value=runtime_spec),
                patch.object(mas_e2e_smoke, "VectorStoreManager", return_value=object()),
                patch.object(mas_e2e_smoke, "build_financial_orchestrator_plan_node", return_value=noop_node),
                patch.object(mas_e2e_smoke, "build_financial_orchestrator_merge_node", return_value=noop_node),
                patch.object(mas_e2e_smoke, "build_financial_analyst_node", return_value=noop_node),
                patch.object(mas_e2e_smoke, "build_financial_researcher_node", return_value=noop_node),
                patch.object(mas_e2e_smoke, "run_mas_graph", side_effect=fake_run_mas_graph),
            ):
                payload = mas_e2e_smoke.run_smoke(
                    store_dir=store_dir,
                    collection_name="collection",
                    queries=["question"],
                )

        self.assertEqual(payload["embedding_compatibility"]["status"], "ok")
        self.assertEqual(payload["embedding_compatibility"]["store_embedding"], runtime_spec)
        self.assertEqual(payload["embedding_compatibility"]["runtime_embedding"], runtime_spec)

    def test_run_smoke_fails_before_graph_on_embedding_signature_mismatch(self) -> None:
        runtime_spec = {
            "provider": "openai",
            "model_name": "text-embedding-3-large",
            "dimension": 3072,
        }
        store_spec = {
            "provider": "huggingface",
            "model_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "dimension": 384,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            store_dir = Path(temp_dir)
            (store_dir / "benchmark_cache_meta.json").write_text(
                json.dumps(
                    {
                        "store_signature": {
                            "collection_name": "collection",
                            "embedding": store_spec,
                        }
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(mas_e2e_smoke, "get_embedding_runtime_spec", return_value=runtime_spec),
                patch.object(mas_e2e_smoke, "VectorStoreManager") as vector_store_manager,
                patch.object(mas_e2e_smoke, "run_mas_graph") as run_mas_graph,
            ):
                with self.assertRaisesRegex(ValueError, "Store embedding signature mismatch.*dimension"):
                    mas_e2e_smoke.run_smoke(
                        store_dir=store_dir,
                        collection_name="collection",
                        queries=["question"],
                    )

        vector_store_manager.assert_not_called()
        run_mas_graph.assert_not_called()

    def test_run_smoke_fails_before_graph_on_chroma_dimension_mismatch(self) -> None:
        runtime_spec = {
            "provider": "openai",
            "model_name": "text-embedding-3-large",
            "dimension": 3072,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            store_dir = Path(temp_dir)
            conn = sqlite3.connect(store_dir / "chroma.sqlite3")
            try:
                conn.execute("CREATE TABLE collections (name TEXT NOT NULL, dimension INTEGER)")
                conn.execute(
                    "INSERT INTO collections (name, dimension) VALUES (?, ?)",
                    ("collection", 384),
                )
                conn.commit()
            finally:
                conn.close()

            with (
                patch.object(mas_e2e_smoke, "get_embedding_runtime_spec", return_value=runtime_spec),
                patch.object(mas_e2e_smoke, "VectorStoreManager") as vector_store_manager,
                patch.object(mas_e2e_smoke, "run_mas_graph") as run_mas_graph,
            ):
                with self.assertRaisesRegex(ValueError, "Store embedding signature mismatch.*dimension"):
                    mas_e2e_smoke.run_smoke(
                        store_dir=store_dir,
                        collection_name="collection",
                        queries=["question"],
                    )

        vector_store_manager.assert_not_called()
        run_mas_graph.assert_not_called()


if __name__ == "__main__":
    unittest.main()
