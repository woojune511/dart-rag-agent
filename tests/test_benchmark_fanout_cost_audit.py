import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.ops.audit_benchmark_fanout_cost import build_audit, find_result_files, render_markdown


class BenchmarkFanoutCostAuditTests(unittest.TestCase):
    def test_build_audit_summarizes_trace_usage_cost_and_quality(self) -> None:
        with TemporaryDirectory() as temp_dir:
            result_path = Path(temp_dir) / "results.json"
            result_path.write_text(
                json.dumps(
                    {
                        "company_runs": [
                            {
                                "id": "company_a",
                                "results": [
                                    {
                                        "id": "structural_selective_v2_prefix_2500_320",
                                        "full_eval": {
                                            "aggregate": {
                                                "estimated_runtime_cost_usd": 0.0123,
                                                "estimated_runtime_embedding_cost_usd": 0.0045,
                                            },
                                            "per_question": [
                                                {
                                                    "id": "Q1",
                                                    "faithfulness": 1.0,
                                                    "completeness": 0.8,
                                                    "context_recall": 1.0,
                                                    "retrieval_hit_at_k": 1.0,
                                                    "numeric_final_judgement": "PASS",
                                                    "llm_usage": {
                                                        "api_calls": 3,
                                                        "prompt_tokens": 100,
                                                        "output_tokens": 20,
                                                        "total_tokens": 120,
                                                    },
                                                    "embedding_usage": {
                                                        "query_embedding_api_calls": 2,
                                                        "query_embedding_text_count": 2,
                                                    },
                                                    "retrieval_debug_trace_history": [
                                                        {
                                                            "query_budget": {
                                                                "source": {
                                                                    "active_subtask_id": "task_1",
                                                                    "active_subtask_operation": "lookup",
                                                                },
                                                                "primary": {"selected_count": 2},
                                                                "operand_focus": {
                                                                    "selected_count": 1,
                                                                    "skipped": False,
                                                                },
                                                                "retry": {"selected_count": 1},
                                                            },
                                                            "search_summary": {
                                                                "executed_query_count": 4,
                                                                "cache_hit_count": 1,
                                                                "vector_attempted_count": 3,
                                                                "query_embedding_api_calls": 3,
                                                                "by_source": {
                                                                    "primary": {
                                                                        "executed_query_count": 2,
                                                                        "cache_hit_count": 1,
                                                                        "query_embedding_api_calls": 1,
                                                                    },
                                                                    "operand_focus": {
                                                                        "executed_query_count": 1,
                                                                        "query_embedding_api_calls": 1,
                                                                    },
                                                                    "retry": {
                                                                        "executed_query_count": 1,
                                                                        "query_embedding_api_calls": 1,
                                                                    },
                                                                },
                                                            },
                                                            "executed_queries": [
                                                                {
                                                                    "source": "primary",
                                                                    "executed_query": "Revenue 2023",
                                                                },
                                                                {
                                                                    "source": "primary",
                                                                    "executed_query": "Revenue 2023",
                                                                },
                                                                {
                                                                    "source": "operand_focus",
                                                                    "executed_query": "Cost 2023",
                                                                },
                                                                {
                                                                    "source": "retry",
                                                                    "executed_query": "Cost 2023",
                                                                },
                                                            ],
                                                            "cross_trace_reuse_candidates": {
                                                                "candidate_count": 1,
                                                                "prior_match_count": 1,
                                                                "candidates": [
                                                                    {
                                                                        "source": "primary",
                                                                        "signature": "revenue 2023",
                                                                        "executed_query": "Revenue 2023",
                                                                        "current_trace_index": 2,
                                                                        "current_cache_hit": True,
                                                                        "prior_match_count": 1,
                                                                        "prior_matches": [
                                                                            {
                                                                                "trace_index": 1,
                                                                                "task_id": "task_0",
                                                                                "operation": "lookup",
                                                                            }
                                                                        ],
                                                                    }
                                                                ],
                                                            },
                                                            "query_result_cache": {
                                                                "entry_count": 2,
                                                                "reuse_count": 1,
                                                            },
                                                            "reused_queries": [
                                                                {
                                                                    "source": "primary",
                                                                    "executed_query": "Revenue 2023",
                                                                    "result_cache_hit": True,
                                                                }
                                                            ],
                                                        }
                                                    ],
                                                },
                                                {
                                                    "id": "Q2",
                                                    "faithfulness": 0.5,
                                                    "completeness": 0.7,
                                                    "numeric_final_judgement": None,
                                                    "llm_usage": {"api_calls": 1, "total_tokens": 40},
                                                    "retrieval_debug_trace": {
                                                        "query_budget": {
                                                            "primary": {"selected_count": 1},
                                                            "operand_focus": {
                                                                "selected_count": 0,
                                                                "skipped": True,
                                                            },
                                                        },
                                                        "executed_queries": [
                                                            {
                                                                "source": "primary",
                                                                "executed_query": "Narrative driver",
                                                                "search_telemetry": {
                                                                    "cache_hit": False,
                                                                    "vector_attempted": True,
                                                                    "embedding_usage": {
                                                                        "query_embedding_api_calls": 1,
                                                                        "query_embedding_text_count": 1,
                                                                    },
                                                                },
                                                            }
                                                        ],
                                                    },
                                                },
                                            ],
                                        },
                                    }
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            audit = build_audit([result_path], top_n=1)

        summary = audit["summary"]
        self.assertEqual(summary["result_file_count"], 1)
        self.assertEqual(summary["question_count"], 2)
        self.assertEqual(summary["executed_query_count"], 5)
        self.assertEqual(summary["unique_executed_query_count"], 3)
        self.assertEqual(summary["duplicate_executed_query_count"], 2)
        self.assertEqual(summary["cross_trace_reuse_candidate_count"], 1)
        self.assertEqual(summary["cross_trace_reuse_prior_match_count"], 1)
        self.assertEqual(summary["cross_trace_reuse_cache_hit_count"], 1)
        self.assertEqual(summary["cross_trace_reuse_cache_miss_count"], 0)
        self.assertEqual(summary["query_result_cache_reuse_count"], 1)
        self.assertEqual(summary["query_result_cache_entry_count"], 2)
        self.assertEqual(summary["query_embedding_api_calls"], 4)
        self.assertEqual(summary["primary_selected_count"], 3)
        self.assertEqual(summary["operand_focus_selected_count"], 1)
        self.assertEqual(summary["retry_selected_count"], 1)
        self.assertEqual(summary["operand_focus_skipped_count"], 1)
        self.assertEqual(summary["llm_usage"]["api_calls"], 4)
        self.assertEqual(summary["llm_usage"]["total_tokens"], 160)
        self.assertAlmostEqual(summary["estimated_runtime_cost_usd"], 0.0123)
        self.assertAlmostEqual(summary["estimated_runtime_embedding_cost_usd"], 0.0045)
        self.assertAlmostEqual(summary["avg_faithfulness"], 0.75)
        self.assertEqual(summary["numeric_pass_count"], 1)
        self.assertEqual(summary["by_source"]["primary"]["executed_query_count"], 3)
        self.assertEqual(summary["by_source"]["primary"]["unique_executed_query_count"], 2)
        self.assertEqual(summary["by_source"]["primary"]["duplicate_executed_query_count"], 1)
        self.assertEqual(summary["by_source"]["retry"]["query_embedding_api_calls"], 1)
        self.assertEqual(audit["top_rows_by_executed_queries"][0]["question_id"], "Q1")
        self.assertEqual(audit["top_rows_by_duplicate_queries"][0]["question_id"], "Q1")
        self.assertEqual(audit["top_rows_by_cross_trace_reuse_candidates"][0]["question_id"], "Q1")
        reuse_details = audit["top_rows_by_cross_trace_reuse_candidates"][0]["cross_trace_reuse_details"]
        self.assertEqual(reuse_details[0]["signature"], "revenue 2023")
        self.assertEqual(reuse_details[0]["prior_match_count"], 1)
        self.assertTrue(reuse_details[0]["current_cache_hit"])
        self.assertFalse(reuse_details[0]["current_cache_miss"])
        self.assertEqual(reuse_details[0]["prior_trace_indexes"], [1])
        self.assertEqual(reuse_details[0]["prior_task_contexts"], {"task_0/lookup": 1})
        duplicate_details = audit["top_rows_by_duplicate_queries"][0]["duplicate_query_details"]
        signatures = {row["signature"] for row in duplicate_details}
        self.assertEqual(signatures, {"revenue 2023", "cost 2023"})
        cost_detail = next(row for row in duplicate_details if row["signature"] == "cost 2023")
        self.assertEqual(cost_detail["count"], 2)
        self.assertEqual(cost_detail["duplicate_count"], 1)
        self.assertEqual(cost_detail["sources"], {"operand_focus": 1, "retry": 1})
        self.assertEqual(cost_detail["trace_indexes"], [1])
        self.assertEqual(cost_detail["trace_count"], 1)
        self.assertEqual(cost_detail["within_trace_duplicate_count"], 1)
        self.assertEqual(cost_detail["cross_trace_repeat_count"], 0)
        self.assertTrue(cost_detail["cross_source"])
        self.assertEqual(cost_detail["task_contexts"], {"task_1/lookup": 2})

    def test_find_result_files_recurses_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "company" / "results.json"
            nested.parent.mkdir()
            nested.write_text("{}", encoding="utf-8")

            self.assertEqual(find_result_files([root]), [nested.resolve()])

    def test_render_markdown_includes_summary_and_top_rows(self) -> None:
        markdown = render_markdown(
            {
                "summary": {
                    "result_file_count": 1,
                    "question_count": 1,
                    "trace_count": 1,
                    "executed_query_count": 2,
                    "cross_trace_reuse_candidate_count": 1,
                    "cross_trace_reuse_prior_match_count": 1,
                    "cross_trace_reuse_cache_hit_count": 1,
                    "cross_trace_reuse_cache_miss_count": 0,
                    "query_result_cache_reuse_count": 1,
                    "query_embedding_api_calls": 2,
                    "llm_usage": {"api_calls": 1},
                    "by_source": {"primary": {"executed_query_count": 2}},
                },
                "top_rows_by_executed_queries": [
                    {
                        "question_id": "Q1",
                        "company_id": "company_a",
                        "experiment_id": "exp",
                        "executed_query_count": 2,
                        "unique_executed_query_count": 1,
                        "duplicate_executed_query_count": 1,
                        "primary_selected_count": 2,
                        "query_embedding_api_calls": 2,
                        "faithfulness": 1,
                        "completeness": 1,
                        "numeric_final_judgement": "PASS",
                    }
                ],
                "top_rows_by_cross_trace_reuse_candidates": [
                    {
                        "question_id": "Q1",
                        "company_id": "company_a",
                        "experiment_id": "exp",
                        "executed_query_count": 2,
                        "cross_trace_reuse_candidate_count": 1,
                        "cross_trace_reuse_prior_match_count": 1,
                        "cross_trace_reuse_cache_hit_count": 1,
                        "cross_trace_reuse_cache_miss_count": 0,
                        "cross_trace_reuse_details": [
                            {
                                "signature": "revenue 2023",
                                "source": "primary",
                                "prior_match_count": 1,
                                "current_trace_index": 2,
                                "current_cache_hit": True,
                                "current_cache_miss": False,
                                "prior_trace_indexes": [1],
                                "prior_task_contexts": {"task_0/lookup": 1},
                            }
                        ],
                        "query_embedding_api_calls": 2,
                        "faithfulness": 1,
                        "completeness": 1,
                    }
                ],
                "top_rows_by_duplicate_queries": [
                    {
                        "question_id": "Q1",
                        "company_id": "company_a",
                        "experiment_id": "exp",
                        "executed_query_count": 2,
                        "unique_executed_query_count": 1,
                        "duplicate_executed_query_count": 1,
                        "duplicate_query_details": [
                            {
                                "signature": "revenue 2023",
                                "count": 2,
                                "duplicate_count": 1,
                                "sources": {"primary": 2},
                                "trace_indexes": [1],
                                "within_trace_duplicate_count": 1,
                                "cross_trace_repeat_count": 0,
                                "cross_source": False,
                                "task_contexts": {"task_1/lookup": 2},
                            }
                        ],
                        "query_embedding_api_calls": 2,
                        "faithfulness": 1,
                        "completeness": 1,
                    }
                ],
            }
        )

        self.assertIn("# Benchmark Fan-out Cost Audit", markdown)
        self.assertIn("| primary | 2 |", markdown)
        self.assertIn("Duplicate executed queries", markdown)
        self.assertIn("Cross-trace reuse candidates", markdown)
        self.assertIn("Cross-trace reuse current cache hits", markdown)
        self.assertIn("Current cache misses", markdown)
        self.assertIn("State query-result cache reuses", markdown)
        self.assertIn("Top Rows By Cross-Trace Reuse Candidates", markdown)
        self.assertIn(
            "revenue 2023 (source:primary; prior:1; prior-traces:1; prior-tasks:task_0/lookup:1; current-cache-hit)",
            markdown,
        )
        self.assertIn("revenue 2023 (2x; primary:2; traces:1; same-trace-dup:1; tasks:task_1/lookup:2)", markdown)
        self.assertIn("| Q1 | company_a | exp | 2 |", markdown)


if __name__ == "__main__":
    unittest.main()
