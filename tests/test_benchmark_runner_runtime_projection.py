import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.benchmark_runner import _flatten_review_rows, _serialise_eval_results


class BenchmarkRunnerRuntimeProjectionTests(unittest.TestCase):
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
        calculation_operands = json.loads(rows[0]["calculation_operands"])
        calculation_plan = json.loads(rows[0]["calculation_plan"])
        calculation_result = json.loads(rows[0]["calculation_result"])
        structured_result = json.loads(rows[0]["structured_result"])
        resolved_trace = json.loads(rows[0]["resolved_calculation_trace"])

        self.assertEqual(calculation_operands, [{"label": "fresh", "value": "123"}])
        self.assertEqual(calculation_plan["operation"], "lookup")
        self.assertEqual(calculation_result["rendered_value"], "123")
        self.assertEqual(structured_result["rendered_value"], "123")
        self.assertEqual(
            resolved_trace["calculation_result"]["answer_slots"]["operation_family"],
            "lookup",
        )

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
            numeric_grounding=1.0,
            numeric_retrieval_support=1.0,
            numeric_final_judgement="PASS",
            numeric_confidence=1.0,
            numeric_debug={},
            absolute_error_rate=0.0,
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
            calculation_operands=[{"label": "fresh", "value": "123"}],
            calculation_plan={"operation": "lookup"},
            calculation_result={"status": "ok", "rendered_value": "123"},
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


if __name__ == "__main__":
    unittest.main()
