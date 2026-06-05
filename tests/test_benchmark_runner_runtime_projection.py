import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.benchmark_runner import (
    _BenchmarkProgressReporter,
    _apply_llm_route_overrides,
    _build_agent_routing_config,
    _build_cross_company_rows,
    _build_winner_ranking,
    _estimate_embedding_cost_usd,
    _estimate_cost_usd,
    _flatten_review_rows,
    _progress_watch_path_summary,
    _render_cross_company_summary_markdown,
    _render_summary_markdown,
    _serialise_eval_results,
)


class BenchmarkRunnerRuntimeProjectionTests(unittest.TestCase):
    def test_estimate_cost_usd_includes_cached_and_thinking_tokens(self) -> None:
        cost = _estimate_cost_usd(
            {
                "prompt_tokens": 1_200_000,
                "cached_tokens": 200_000,
                "output_tokens": 300_000,
                "thoughts_tokens": 100_000,
                "tool_use_prompt_tokens": 50_000,
            },
            {
                "input_per_million_tokens_usd": 1.0,
                "cached_input_per_million_tokens_usd": 0.25,
                "output_per_million_tokens_usd": 3.0,
                "thinking_per_million_tokens_usd": 2.0,
                "tool_input_per_million_tokens_usd": 0.5,
            },
        )

        self.assertAlmostEqual(cost or 0.0, 2.175)

    def test_estimate_embedding_cost_usd_requires_embedding_rate(self) -> None:
        usage = {"embedding_estimated_input_tokens": 1_500_000}

        self.assertIsNone(_estimate_embedding_cost_usd(usage, {"input_per_million_tokens_usd": 0.3}))
        self.assertAlmostEqual(
            _estimate_embedding_cost_usd(usage, {"embedding_input_per_million_tokens_usd": 0.2}) or 0.0,
            0.3,
        )

    def test_routing_config_carries_retrieval_query_budgets(self) -> None:
        config = _build_agent_routing_config(
            {
                "retrieval_query_budget": 12,
                "focused_retrieval_query_budget": 4,
                "retry_retrieval_query_budget": 1,
                "report_cache_index_path": "tmp/report-cache-index.json",
                "llm_routes": {
                    "evidence_extraction": {
                        "provider": "openrouter",
                        "model": "openai/gpt-4.1-mini",
                    }
                },
            }
        )

        self.assertEqual(config["retrieval_query_budget"], 12)
        self.assertEqual(config["focused_retrieval_query_budget"], 4)
        self.assertEqual(config["retry_retrieval_query_budget"], 1)
        self.assertEqual(config["report_cache_index_path"], "tmp/report-cache-index.json")
        self.assertEqual(
            config["llm_routes"]["evidence_extraction"]["model"],
            "openai/gpt-4.1-mini",
        )

    def test_llm_route_overrides_merge_with_profile_routes(self) -> None:
        full_eval_config = _apply_llm_route_overrides(
            {
                "llm_routes": {
                    "default": {"provider": "google", "model": "gemini-2.5-flash", "temperature": 0},
                    "evidence_extraction": {"provider": "google", "model": "gemini-2.5-pro", "temperature": 0},
                }
            },
            [
                "evidence_extraction=google:gemini-2.5-flash",
                "compression=openrouter:openai/gpt-4.1-mini",
            ],
        )

        routes = full_eval_config["llm_routes"]
        self.assertEqual(routes["evidence_extraction"]["provider"], "google")
        self.assertEqual(routes["evidence_extraction"]["model"], "gemini-2.5-flash")
        self.assertEqual(routes["evidence_extraction"]["temperature"], 0)
        self.assertEqual(routes["compression"]["provider"], "openrouter")
        self.assertEqual(routes["compression"]["model"], "openai/gpt-4.1-mini")

    def test_serialise_eval_results_preserves_retrieval_trace_history(self) -> None:
        result = SimpleNamespace(
            id="Q1",
            question="질문",
            answer="답변",
            ground_truth="정답",
            answer_key={},
            expected_sections=[],
            evidence=[],
            raw_faithfulness=1.0,
            faithfulness=1.0,
            faithfulness_override_reason=None,
            answer_relevancy=1.0,
            context_recall=1.0,
            retrieval_hit_at_k=1.0,
            ndcg_at_3=None,
            ndcg_at_5=None,
            context_precision_at_3=None,
            context_precision_at_5=None,
            section_match_rate=1.0,
            citation_coverage=1.0,
            entity_coverage=None,
            completeness=1.0,
            completeness_reason=None,
            refusal_accuracy=None,
            numeric_equivalence=None,
            numeric_grounding=None,
            numeric_retrieval_support=None,
            numeric_final_judgement=None,
            numeric_confidence=None,
            numeric_debug={},
            absolute_error_rate=None,
            operand_selection_correctness=None,
            unit_consistency_pass=None,
            numeric_result_correctness=None,
            trend_interpretation_correctness=None,
            grounded_rendering_correctness=None,
            calculation_correctness=None,
            missing_info_compliance=None,
            retrieved_count=0,
            query_type="numeric_fact",
            intent="numeric_fact",
            format_preference="table",
            routing_source="test",
            routing_confidence=1.0,
            routing_scores={},
            latency_sec=0.1,
            citations=[],
            retrieved_metadata=[],
            retrieved_previews=[],
            retrieval_debug_trace={"query_budget": {"primary": {"selected_count": 1}}},
            retrieval_debug_trace_history=[
                {"query_budget": {"source": {"active_subtask_id": "task_1"}}},
                {"query_budget": {"source": {"active_subtask_id": "task_2"}}},
            ],
            runtime_evidence=[],
            selected_claim_ids=[],
            draft_points=[],
            kept_claim_ids=[],
            dropped_claim_ids=[],
            unsupported_sentences=[],
            sentence_checks=[],
            resolved_calculation_trace={},
            structured_result={},
            calculation_operands=[],
            calculation_plan={},
            calculation_result={},
            agent_llm_usage={},
            judge_llm_usage={},
            llm_usage={},
            agent_embedding_usage={},
            judge_embedding_usage={},
            embedding_usage={},
            missing_info_policy=None,
            error=None,
        )

        row = _serialise_eval_results([result])[0]

        self.assertEqual(len(row["retrieval_debug_trace_history"]), 2)
        self.assertEqual(
            row["retrieval_debug_trace_history"][1]["query_budget"]["source"]["active_subtask_id"],
            "task_2",
        )

    def test_progress_reporter_writes_jsonl_events(self) -> None:
        with TemporaryDirectory() as temp_dir:
            heartbeat_log = Path(temp_dir) / "heartbeat.jsonl"
            reporter = _BenchmarkProgressReporter(
                heartbeat_sec=0,
                heartbeat_log=heartbeat_log,
            )

            reporter.start()
            reporter.update("screening:ingest", 1, 3, experiment_id="exp-1", emit_now=True)
            reporter.stop(status="completed")

            events = [
                json.loads(line)
                for line in heartbeat_log.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(events[0]["event"], "started")
        self.assertEqual(events[1]["phase"], "screening:ingest")
        self.assertEqual(events[1]["current"], 1)
        self.assertEqual(events[1]["total"], 3)
        self.assertEqual(events[-1]["details"]["status"], "completed")

    def test_progress_watch_path_summary_reports_latest_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            older = root / "older.txt"
            newer = root / "nested" / "newer.txt"
            older.write_text("old", encoding="utf-8")
            newer.parent.mkdir()
            newer.write_text("new", encoding="utf-8")
            os.utime(older, (1, 1))
            os.utime(newer, (2, 2))

            summary = _progress_watch_path_summary([root])

        self.assertEqual(summary["existing_count"], 1)
        self.assertTrue(summary["latest_path"].endswith("newer.txt"))

    def test_winner_ranking_prefers_full_eval_pass_over_cheaper_candidate(self) -> None:
        company_bundles = [
            {
                "company_id": "naver_2023_runtime_contract_gate",
                "company_label": "NAVER 2023",
                "results": [
                    {
                        "id": "plain_prefix_8000_400",
                        "screen_pass": True,
                        "screen_failure_reasons": [],
                        "config": {"ingest_mode": "plain", "chunk_size": 8000, "chunk_overlap": 400},
                        "ingest": {"api_calls": 0, "elapsed_sec": 100.0},
                        "comparison_to_baseline": {
                            "api_call_reduction_ratio": 1.0,
                            "ingest_time_reduction_ratio": 0.9,
                            "estimated_cost_reduction_ratio": 1.0,
                        },
                        "full_eval": {
                            "aggregate": {
                                "faithfulness": 1.0,
                                "completeness": 1.0,
                                "numeric_pass_rate": 1.0,
                                "context_recall": 1.0,
                            }
                        },
                    },
                    {
                        "id": "contextual_selective_v2_prefix_2500_320",
                        "screen_pass": True,
                        "screen_failure_reasons": [],
                        "config": {
                            "ingest_mode": "contextual_selective_v2",
                            "chunk_size": 2500,
                            "chunk_overlap": 320,
                        },
                        "ingest": {"api_calls": 300, "elapsed_sec": 1200.0},
                        "comparison_to_baseline": {
                            "api_call_reduction_ratio": 0.0,
                            "ingest_time_reduction_ratio": 0.0,
                            "estimated_cost_reduction_ratio": 0.0,
                        },
                        "full_eval": {
                            "aggregate": {
                                "faithfulness": 1.0,
                                "completeness": 1.0,
                                "numeric_pass_rate": 1.0,
                                "context_recall": 1.0,
                            }
                        },
                    },
                ],
            },
            {
                "company_id": "skh_2023_runtime_contract_gate",
                "company_label": "SK하이닉스 2023",
                "results": [
                    {
                        "id": "plain_prefix_8000_400",
                        "screen_pass": True,
                        "screen_failure_reasons": [],
                        "config": {"ingest_mode": "plain", "chunk_size": 8000, "chunk_overlap": 400},
                        "ingest": {"api_calls": 0, "elapsed_sec": 40.0},
                        "comparison_to_baseline": {
                            "api_call_reduction_ratio": 1.0,
                            "ingest_time_reduction_ratio": 0.95,
                            "estimated_cost_reduction_ratio": 1.0,
                        },
                        "full_eval": {
                            "aggregate": {
                                "faithfulness": 0.3,
                                "completeness": 0.0,
                                "numeric_pass_rate": 0.0,
                                "context_recall": 1.0,
                            }
                        },
                    },
                    {
                        "id": "contextual_selective_v2_prefix_2500_320",
                        "screen_pass": True,
                        "screen_failure_reasons": [],
                        "config": {
                            "ingest_mode": "contextual_selective_v2",
                            "chunk_size": 2500,
                            "chunk_overlap": 320,
                        },
                        "ingest": {"api_calls": 320, "elapsed_sec": 1260.0},
                        "comparison_to_baseline": {
                            "api_call_reduction_ratio": 0.0,
                            "ingest_time_reduction_ratio": 0.0,
                            "estimated_cost_reduction_ratio": 0.0,
                        },
                        "full_eval": {
                            "aggregate": {
                                "faithfulness": 1.0,
                                "completeness": 1.0,
                                "numeric_pass_rate": 1.0,
                                "context_recall": 1.0,
                            }
                        },
                    },
                ],
            },
        ]

        rows = _build_cross_company_rows(company_bundles)
        ranking = _build_winner_ranking(rows)
        markdown = _render_cross_company_summary_markdown(rows, ranking)

        self.assertEqual(ranking[0]["experiment_id"], "contextual_selective_v2_prefix_2500_320")
        self.assertEqual(ranking[0]["full_eval_fail_count"], 0)
        self.assertEqual(ranking[1]["experiment_id"], "plain_prefix_8000_400")
        self.assertEqual(ranking[1]["full_eval_fail_count"], 1)
        self.assertIn("full-evaluation fail count", markdown)
        self.assertIn("Full-Eval Failure Notes for `plain_prefix_8000_400`", markdown)

    def test_full_eval_failure_count_treats_missing_numeric_pass_rate_as_not_applicable(self) -> None:
        rows = [
            {
                "company_id": "naver_2023_runtime_contract_gate",
                "company": "NAVER 2023",
                "experiment_id": "policy_driven_runtime_contract",
                "screen_pass": True,
                "critical_category_miss_count": 0,
                "retrieval_hit_at_k": 1.0,
                "section_match_rate": 1.0,
                "citation_coverage": 1.0,
                "contamination_rate": 0.0,
                "api_calls": 0,
                "estimated_ingest_cost_usd": 0.0,
                "ingest_elapsed_sec": 1.0,
                "api_call_reduction_ratio": None,
                "ingest_time_reduction_ratio": None,
                "estimated_cost_reduction_ratio": None,
                "full_faithfulness": 1.0,
                "full_completeness": 1.0,
                "full_numeric_pass_rate": None,
                "full_context_recall": 1.0,
                "screen_failure_reasons": [],
                "screen_failure_examples": [],
            }
        ]

        ranking = _build_winner_ranking(rows)
        markdown = _render_cross_company_summary_markdown(rows, ranking)

        self.assertEqual(ranking[0]["full_eval_fail_count"], 0)
        self.assertEqual(ranking[0]["full_eval_failures"], [])
        self.assertIn("| NAVER 2023 | policy_driven_runtime_contract | yes | 0 |", markdown)
        self.assertNotIn("Full-Eval Failure Notes", markdown)

    def test_flatten_review_rows_prefers_resolved_runtime_trace(self) -> None:
        results = [
            {
                "id": "exp-1",
                "screening_eval": {"per_question": [{"id": "Q1", "category": "numeric_fact"}]},
                "full_eval": {
                    "per_question": [
                        {
                            "id": "Q1",
                            "question": "질문",
                            "answer": "최종 답변",
                            "answer_key": "정답",
                            "calculation_operands": [{"label": "stale", "value": "999"}],
                            "calculation_plan": {"status": "stale"},
                            "calculation_result": {"status": "stale"},
                            "active_subtask": {"task_id": "task_1"},
                            "tasks": [
                                {
                                    "task_id": "task_1",
                                    "kind": "calculation",
                                    "status": "completed",
                                    "artifact_ids": [
                                        "artifact:operands",
                                        "artifact:plan",
                                        "artifact:result",
                                    ],
                                }
                            ],
                            "artifacts": [
                                {
                                    "artifact_id": "artifact:operands",
                                    "task_id": "task_1",
                                    "kind": "operand_set",
                                    "payload": {
                                        "calculation_operands": [
                                            {"label": "fresh", "value": "123", "row_id": "ev_001"}
                                        ]
                                    },
                                },
                                {
                                    "artifact_id": "artifact:plan",
                                    "task_id": "task_1",
                                    "kind": "calculation_plan",
                                    "payload": {
                                        "calculation_plan": {"status": "ok", "operation": "lookup"}
                                    },
                                },
                                {
                                    "artifact_id": "artifact:result",
                                    "task_id": "task_1",
                                    "kind": "calculation_result",
                                    "payload": {
                                        "calculation_result": {
                                            "status": "ok",
                                            "rendered_value": "123",
                                            "answer_slots": {
                                                "operation_family": "lookup",
                                                "primary_value": {"rendered_value": "123"},
                                            },
                                        }
                                    },
                                },
                            ],
                        }
                    ]
                },
            }
        ]

        rows = _flatten_review_rows(results)

        self.assertEqual(len(rows), 1)
        structured_result = json.loads(rows[0]["structured_result"])
        resolved_trace = json.loads(rows[0]["resolved_calculation_trace"])
        task_artifact_trace = json.loads(rows[0]["task_artifact_trace"])

        self.assertEqual(rows[0]["resolved_operand_count"], 1)
        self.assertEqual(rows[0]["task_artifact_task_count"], 1)
        self.assertEqual(rows[0]["task_artifact_artifact_count"], 3)
        self.assertEqual(rows[0]["task_artifact_integrity_status"], "ok")
        self.assertEqual(rows[0]["task_artifact_integrity_issue_count"], 0)
        self.assertEqual(task_artifact_trace["tasks"][0]["latest_artifact_id"], "artifact:result")
        self.assertEqual(task_artifact_trace["tasks"][0]["artifact_kinds"], ["operand_set", "calculation_plan", "calculation_result"])
        self.assertEqual(structured_result["rendered_value"], "123")
        self.assertEqual(
            resolved_trace["calculation_result"]["answer_slots"]["operation_family"],
            "lookup",
        )
        self.assertEqual(resolved_trace["runtime_projection"]["source"], "task_artifact_ledger")
        self.assertFalse(resolved_trace["runtime_projection"]["legacy_fallback"])
        self.assertEqual(rows[0]["runtime_projection_source"], "task_artifact_ledger")
        self.assertFalse(rows[0]["runtime_projection_legacy_fallback"])
        self.assertEqual(rows[0]["runtime_projection_calculation_result_source"], "")
        self.assertNotIn("calculation_operands", rows[0])
        self.assertNotIn("calculation_plan", rows[0])
        self.assertNotIn("calculation_result", rows[0])

    def test_flatten_review_rows_rejects_legacy_top_level_runtime_projection(self) -> None:
        results = [
            {
                "id": "exp-1",
                "screening_eval": {"per_question": [{"id": "Q1", "category": "numeric_fact"}]},
                "full_eval": {
                    "per_question": [
                        {
                            "id": "Q1",
                            "question": "question",
                            "answer_key": "answer",
                            "answer": "answer",
                            "calculation_operands": [{"label": "legacy", "value": "999"}],
                            "calculation_plan": {"status": "legacy"},
                            "calculation_result": {"status": "ok", "rendered_value": "999"},
                            "resolved_calculation_trace": {},
                            "structured_result": {},
                            "task_artifact_trace": {},
                        }
                    ]
                },
            }
        ]

        rows = _flatten_review_rows(results)

        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0]["resolved_calculation_trace"]), {})
        self.assertEqual(json.loads(rows[0]["structured_result"]), {})
        self.assertEqual(rows[0]["runtime_projection_source"], "")
        self.assertFalse(rows[0]["runtime_projection_legacy_fallback"])
        self.assertEqual(rows[0]["resolved_operand_count"], 0)
        self.assertNotIn("calculation_operands", rows[0])
        self.assertNotIn("calculation_plan", rows[0])
        self.assertNotIn("calculation_result", rows[0])

    def test_serialise_eval_results_keeps_structured_runtime_contract(self) -> None:
        result = SimpleNamespace(
            id="Q1",
            question="질문",
            answer="답변",
            ground_truth="정답",
            answer_key="정답",
            expected_sections=[],
            evidence=[],
            raw_faithfulness=1.0,
            faithfulness=1.0,
            faithfulness_override_reason=None,
            answer_relevancy=1.0,
            context_recall=1.0,
            retrieval_hit_at_k=1.0,
            ndcg_at_3=1.0,
            ndcg_at_5=1.0,
            context_precision_at_3=1.0,
            context_precision_at_5=1.0,
            section_match_rate=1.0,
            citation_coverage=1.0,
            entity_coverage=1.0,
            completeness=1.0,
            completeness_reason="ok",
            refusal_accuracy=1.0,
            numeric_equivalence=1.0,
            raw_numeric_grounding=0.5,
            numeric_grounding=1.0,
            numeric_retrieval_support=1.0,
            raw_numeric_final_judgement="UNCERTAIN",
            numeric_final_judgement="PASS",
            raw_numeric_confidence=0.6,
            numeric_confidence=1.0,
            numeric_debug={},
            absolute_error_rate=0.0,
            raw_operand_selection_correctness=0.5,
            operand_selection_correctness=1.0,
            unit_consistency_pass=1.0,
            numeric_result_correctness=1.0,
            trend_interpretation_correctness=None,
            grounded_rendering_correctness=1.0,
            calculation_correctness=1.0,
            missing_info_compliance=None,
            retrieved_count=1,
            query_type="numeric_fact",
            intent="numeric_fact",
            format_preference="sentence",
            routing_source="router",
            routing_confidence=1.0,
            routing_scores={"numeric_fact": 1.0},
            latency_sec=0.1,
            citations=[],
            retrieved_metadata=[],
            retrieved_previews=[],
            retrieval_debug_trace={
                "query_bundle": ["질문"],
                "candidate_count": 3,
                "selected_count": 1,
            },
            runtime_evidence=[],
            selected_claim_ids=[],
            draft_points=[],
            kept_claim_ids=[],
            dropped_claim_ids=[],
            unsupported_sentences=[],
            sentence_checks=[],
            resolved_calculation_trace={
                "calculation_operands": [{"label": "fresh", "value": "123"}],
                "calculation_plan": {"operation": "lookup"},
                "calculation_result": {"status": "ok", "rendered_value": "123"},
            },
            structured_result={
                "status": "ok",
                "rendered_value": "123",
                "answer_slots": {"operation_family": "lookup"},
            },
            task_artifact_trace={
                "task_count": 1,
                "artifact_count": 1,
                "missing_artifact_ids": ["artifact_missing"],
                "orphan_artifact_ids": [],
                "integrity_status": "error",
                "integrity_issue_count": 1,
                "integrity_issues": [
                    {"type": "missing_artifact_reference", "severity": "error", "artifact_id": "artifact_missing"}
                ],
                "tasks": [{"task_id": "task_1", "latest_artifact_id": "artifact_1"}],
                "artifacts": [{"artifact_id": "artifact_1", "payload_keys": ["calculation_result"]}],
            },
            calculation_operands=[{"label": "stale", "value": "999"}],
            calculation_plan={"status": "stale"},
            calculation_result={"status": "stale", "rendered_value": "999"},
            missing_info_policy=None,
            error=None,
        )

        rows = _serialise_eval_results([result])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["structured_result"]["rendered_value"], "123")
        self.assertEqual(
            rows[0]["resolved_calculation_trace"]["calculation_plan"]["operation"],
            "lookup",
        )
        self.assertEqual(
            rows[0]["resolved_calculation_trace"]["runtime_projection"]["source"],
            "resolved_calculation_trace",
        )
        self.assertFalse(
            rows[0]["resolved_calculation_trace"]["runtime_projection"]["legacy_fallback"]
        )
        self.assertEqual(rows[0]["runtime_projection_source"], "resolved_calculation_trace")
        self.assertFalse(rows[0]["runtime_projection_legacy_fallback"])
        self.assertEqual(rows[0]["runtime_projection_calculation_result_source"], "")
        self.assertEqual(rows[0]["task_artifact_trace"]["task_count"], 1)
        self.assertEqual(rows[0]["task_artifact_missing_ids"], ["artifact_missing"])
        self.assertEqual(rows[0]["task_artifact_integrity_status"], "error")
        self.assertEqual(rows[0]["task_artifact_integrity_issue_count"], 1)
        self.assertEqual(rows[0]["task_artifact_integrity_issues"][0]["type"], "missing_artifact_reference")
        self.assertEqual(rows[0]["resolved_operand_count"], 1)
        self.assertEqual(rows[0]["raw_numeric_grounding"], 0.5)
        self.assertEqual(rows[0]["numeric_grounding"], 1.0)
        self.assertEqual(rows[0]["raw_numeric_final_judgement"], "UNCERTAIN")
        self.assertEqual(rows[0]["numeric_final_judgement"], "PASS")
        self.assertEqual(rows[0]["raw_operand_selection_correctness"], 0.5)
        self.assertEqual(rows[0]["operand_selection_correctness"], 1.0)
        self.assertEqual(rows[0]["retrieval_debug_trace"]["selected_count"], 1)
        self.assertEqual(rows[0]["retrieval_debug_trace"]["candidate_count"], 3)
        self.assertNotIn(
            "stale",
            json.dumps(rows[0]["resolved_calculation_trace"], ensure_ascii=False),
        )
        self.assertNotIn("calculation_operands", rows[0])
        self.assertNotIn("calculation_plan", rows[0])
        self.assertNotIn("calculation_result", rows[0])

    def test_summary_markdown_includes_task_artifact_integrity_counts(self) -> None:
        markdown = _render_summary_markdown(
            [
                {
                    "id": "exp-1",
                    "config": {
                        "chunk_size": 2500,
                        "chunk_overlap": 320,
                        "ingest_mode": "structural_selective_v2",
                    },
                    "parse": {"elapsed_sec": 1.0, "chunk_count": 10},
                    "ingest": {"elapsed_sec": 2.0},
                    "comparison_to_baseline": {},
                    "screen_pass": True,
                    "screening_eval": {
                        "aggregate": {
                            "contamination_rate": 0.0,
                            "retrieval_hit_at_k": 1.0,
                            "section_match_rate": 1.0,
                            "citation_coverage": 1.0,
                        }
                    },
                    "full_eval": {
                        "aggregate": {
                            "faithfulness": 1.0,
                            "answer_relevancy": 1.0,
                            "context_recall": 1.0,
                            "completeness": 1.0,
                            "numeric_pass_rate": 1.0,
                            "task_artifact_integrity_error_count": 1,
                            "task_artifact_integrity_warning_count": 2,
                            "task_artifact_integrity_issue_count": 3,
                        }
                    },
                }
            ]
        )

        self.assertIn("Ledger Errors", markdown)
        self.assertIn("| exp-1 |", markdown)
        self.assertIn("| 1 | 2 | 3 |", markdown)


if __name__ == "__main__":
    unittest.main()
