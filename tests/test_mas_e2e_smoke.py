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

from src.ops import mas_e2e_smoke


class MasE2ESmokeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
