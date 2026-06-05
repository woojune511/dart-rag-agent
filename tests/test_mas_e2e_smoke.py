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
