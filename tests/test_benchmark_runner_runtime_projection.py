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
    _build_cross_company_rows,
    _build_winner_ranking,
    _flatten_review_rows,
    _progress_watch_path_summary,
    _render_cross_company_summary_markdown,
    _serialise_eval_results,
)


class BenchmarkRunnerRuntimeProjectionTests(unittest.TestCase):
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
                                            {"label": "fresh", "value": "123"}
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

        self.assertEqual(rows[0]["resolved_operand_count"], 1)
        self.assertEqual(structured_result["rendered_value"], "123")
        self.assertEqual(
            resolved_trace["calculation_result"]["answer_slots"]["operation_family"],
            "lookup",
        )
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
        self.assertEqual(rows[0]["resolved_operand_count"], 1)
        self.assertEqual(rows[0]["raw_numeric_grounding"], 0.5)
        self.assertEqual(rows[0]["numeric_grounding"], 1.0)
        self.assertEqual(rows[0]["raw_numeric_final_judgement"], "UNCERTAIN")
        self.assertEqual(rows[0]["numeric_final_judgement"], "PASS")
        self.assertEqual(rows[0]["raw_operand_selection_correctness"], 0.5)
        self.assertEqual(rows[0]["operand_selection_correctness"], 1.0)
        self.assertEqual(rows[0]["retrieval_debug_trace"]["selected_count"], 1)
        self.assertEqual(rows[0]["retrieval_debug_trace"]["candidate_count"], 3)
        self.assertNotIn("calculation_operands", rows[0])
        self.assertNotIn("calculation_plan", rows[0])
        self.assertNotIn("calculation_result", rows[0])


if __name__ == "__main__":
    unittest.main()
