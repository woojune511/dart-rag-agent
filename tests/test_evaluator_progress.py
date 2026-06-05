import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.evaluator import EvalExample, EvalResult, RAGEvaluator


class _FakeRun:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class _FakeMlflow:
    def set_experiment(self, name):
        self.experiment_name = name

    def start_run(self, run_name=None):
        self.run_name = run_name
        return _FakeRun()

    def log_params(self, params):
        self.params = dict(params)

    def log_param(self, key, value):
        setattr(self, key, value)

    def log_metrics(self, metrics, step=None):
        pass

    def log_artifact(self, path, artifact_path=None):
        pass


def _example(example_id: str) -> EvalExample:
    return EvalExample(
        id=example_id,
        question=f"question {example_id}",
        ground_truth="answer",
        company="TEST",
        year=2023,
        section="section",
    )


def _result(example: EvalExample, task_artifact_trace=None) -> EvalResult:
    return EvalResult(
        id=example.id,
        question=example.question,
        answer="answer",
        ground_truth=example.ground_truth,
        answer_key=example.canonical_answer_key,
        expected_sections=[],
        evidence=[],
        raw_faithfulness=None,
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
        missing_info_compliance=None,
        refusal_accuracy=None,
        retrieved_count=1,
        query_type="numeric",
        intent="comparison",
        format_preference="",
        routing_source="test",
        routing_confidence=None,
        latency_sec=0.1,
        numeric_final_judgement="PASS",
        task_artifact_trace=dict(task_artifact_trace or {"integrity_status": "ok", "integrity_issue_count": 0}),
    )


class EvaluatorProgressTests(unittest.TestCase):
    def test_run_emits_per_question_progress(self) -> None:
        evaluator = RAGEvaluator.__new__(RAGEvaluator)
        evaluator.experiment_name = "test"
        evaluator.load_dataset = lambda: []
        evaluator.evaluate_one = lambda example: _result(example)
        events = []

        with patch("src.ops.evaluator.mlflow", _FakeMlflow()):
            output = evaluator.run(
                examples=[_example("Q1"), _example("Q2")],
                run_name="progress-test",
                max_workers=1,
                on_progress=events.append,
            )

        self.assertEqual([event["event"] for event in events], ["started", "completed", "started", "completed"])
        self.assertEqual([event["question_id"] for event in events], ["Q1", "Q1", "Q2", "Q2"])
        self.assertEqual([event["completed"] for event in events], [0, 1, 1, 2])
        self.assertEqual(events[-1]["numeric_final_judgement"], "PASS")
        self.assertEqual(len(output["per_question"]), 2)

    def test_run_aggregates_task_artifact_integrity_counts(self) -> None:
        evaluator = RAGEvaluator.__new__(RAGEvaluator)
        evaluator.experiment_name = "test"
        evaluator.load_dataset = lambda: []

        traces = {
            "Q1": {
                "integrity_status": "error",
                "integrity_issue_count": 2,
                "integrity_issues": [
                    {"type": "missing_artifact_reference", "severity": "error"},
                    {"type": "orphan_artifact", "severity": "warning"},
                ],
            },
            "Q2": {
                "integrity_status": "warning",
                "integrity_issue_count": 1,
                "integrity_issues": [
                    {"type": "task_without_artifacts", "severity": "warning"},
                ],
            },
        }
        evaluator.evaluate_one = lambda example: _result(example, traces[example.id])

        with patch("src.ops.evaluator.mlflow", _FakeMlflow()):
            output = evaluator.run(
                examples=[_example("Q1"), _example("Q2")],
                run_name="integrity-test",
                max_workers=1,
            )

        aggregate = output["aggregate"]
        self.assertEqual(aggregate["task_artifact_integrity_error_count"], 1)
        self.assertEqual(aggregate["task_artifact_integrity_warning_count"], 1)
        self.assertEqual(aggregate["task_artifact_integrity_ok_count"], 0)
        self.assertEqual(aggregate["task_artifact_integrity_issue_count"], 3)


if __name__ == "__main__":
    unittest.main()
