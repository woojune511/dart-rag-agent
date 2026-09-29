"""The ledger records final answer completeness, not merely assembly success."""

from copy import deepcopy
import unittest

from src.agent.financial_task_artifacts import aggregate_answer_artifact_update


class AggregateAnswerStatusTests(unittest.TestCase):
    def _project(self, structured_result, *, feedback=""):
        inputs = {
            "tasks": [], "artifacts": [], "final_answer": "Available answer.",
            "payload": {
                "final_answer": "Available answer.",
                "structured_result": structured_result,
                "resolved_calculation_trace": {},
            },
            "evidence_refs": ["source_a"], "planner_feedback": feedback,
            "query": "Return both requested outputs.",
        }
        before = deepcopy(inputs)
        projection = aggregate_answer_artifact_update(**inputs)
        self.assertEqual(inputs, before)
        self.assertEqual(projection["artifacts"][-1]["payload"], inputs["payload"])
        return projection["tasks"][-1], projection["artifacts"][-1]

    def test_final_completeness_applies_to_numeric_and_narrative_answers(self):
        for kind in ("direct_value", "narrative"):
            for status in ("partial", "incomplete", "invalid"):
                with self.subTest(kind=kind, status=status):
                    task, artifact = self._project({
                        "status": status,
                        "answer_obligations": [{"obligation_id": "first", "kind": kind},
                                               {"obligation_id": "second", "kind": kind}],
                        "missing_obligation_ids": ["second"],
                    })
                    self.assertEqual(artifact["status"], status)
                    self.assertEqual(task["status"], "partial")

    def test_complete_final_result_without_feedback_is_completed(self):
        task, artifact = self._project({"status": "ok", "missing_obligation_ids": []})
        self.assertEqual((task["status"], artifact["status"]), ("completed", "ok"))

    def test_planner_feedback_keeps_both_task_and_artifact_partial(self):
        task, artifact = self._project({"status": "ok"}, feedback="One planning constraint remains unresolved.")
        self.assertEqual((task["status"], artifact["status"]), ("partial", "partial"))

    def test_feedback_does_not_hide_more_specific_incomplete_final_status(self):
        task, artifact = self._project({"status": "incomplete"}, feedback="Required evidence is unavailable.")
        self.assertEqual((task["status"], artifact["status"]), ("partial", "incomplete"))

    def test_legacy_unstructured_payload_keeps_existing_feedback_fallback(self):
        for feedback, expected in (("", ("completed", "ok")), ("Unresolved", ("partial", "partial"))):
            with self.subTest(feedback=feedback):
                task, artifact = self._project({}, feedback=feedback)
                self.assertEqual((task["status"], artifact["status"]), expected)


if __name__ == "__main__":
    unittest.main()
