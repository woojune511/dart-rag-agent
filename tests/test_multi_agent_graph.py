import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.mas_graph import run_mas_graph
from src.agent.mas_types import TaskStatus


class MultiAgentSkeletonTests(unittest.TestCase):
    def test_parallel_workers_join_before_merge(self) -> None:
        final = run_mas_graph("삼성전자 24년 분석해줘")

        trace = final["execution_trace"]
        self.assertEqual(trace[0], "Orchestrator planned 2 tasks")
        self.assertIn("Analyst completed task_1", trace)
        self.assertIn("Researcher completed task_2", trace)
        self.assertIn("Critic passed all artifacts (Deterministic)", trace)
        self.assertEqual(trace[-1], "Orchestrator merged final report")

        critic_index = trace.index("Critic passed all artifacts (Deterministic)")
        self.assertLess(trace.index("Analyst completed task_1"), critic_index)
        self.assertLess(trace.index("Researcher completed task_2"), critic_index)

        self.assertEqual(set(final["tasks"].keys()), {"task_1", "task_2"})
        self.assertEqual(final["tasks"]["task_1"]["status"], TaskStatus.COMPLETED)
        self.assertEqual(final["tasks"]["task_2"]["status"], TaskStatus.COMPLETED)
        self.assertIn("task_1", final["artifacts"])
        self.assertIn("task_2", final["artifacts"])
        self.assertEqual(len(final["critic_reports"]), 2)
        self.assertTrue(all(report["passed"] for report in final["critic_reports"]))
        self.assertEqual(
            final["final_report"],
            "매출은 1000억이고, 이유는 AI 수요 증가와 제품 믹스 개선이 실적에 영향을 미쳤습니다.입니다.",
        )

    def test_critic_can_retry_analyst_then_merge(self) -> None:
        final = run_mas_graph(
            "삼성전자 24년 분석해줘",
            debug_force_retry_assignee="Analyst",
        )

        trace = final["execution_trace"]
        self.assertEqual(trace.count("Critic rejected some artifacts (Deterministic)"), 1)
        self.assertEqual(trace.count("Critic passed all artifacts (Deterministic)"), 1)
        self.assertEqual(trace.count("Analyst completed task_1"), 1)
        self.assertEqual(trace.count("Analyst completed task_1 after critic retry"), 1)
        self.assertEqual(trace.count("Researcher completed task_2"), 1)
        self.assertEqual(trace[-1], "Orchestrator merged final report")

        self.assertEqual(final["tasks"]["task_1"]["status"], TaskStatus.COMPLETED)
        self.assertEqual(final["tasks"]["task_1"]["retry_count"], 1)
        self.assertEqual(final["tasks"]["task_2"]["status"], TaskStatus.COMPLETED)
        self.assertEqual(len(final["critic_reports"]), 4)
        first_critic_pass = {
            report["target_task_id"]: report["passed"]
            for report in final["critic_reports"][:2]
        }
        self.assertFalse(first_critic_pass["task_1"])
        self.assertTrue(first_critic_pass["task_2"])
        final_critic_pass = {
            report["target_task_id"]: report["passed"]
            for report in final["critic_reports"][-2:]
        }
        self.assertTrue(final_critic_pass["task_1"])
        self.assertTrue(final_critic_pass["task_2"])


if __name__ == "__main__":
    unittest.main()
