import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.mas_graph import build_initial_state, run_mas_graph
from src.agent.mas_types import Artifact, MultiAgentState, TaskStatus
from src.agent.nodes.orchestrator_node import (
    make_run_orchestrator_merge,
    make_run_orchestrator_plan,
)


class FakePlannerCore:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def run(self, query: str, *, report_scope=None):
        self.calls.append({"query": query, "report_scope": dict(report_scope or {})})
        return self.payload


class FakeMergeCore:
    def __init__(self, final_report: str):
        self.final_report = final_report
        self.calls = []

    def run(self, query: str, *, report_scope=None, artifacts=None, critic_feedback=None):
        self.calls.append(
            {
                "query": query,
                "report_scope": dict(report_scope or {}),
                "artifacts": dict(artifacts or {}),
                "critic_feedback": critic_feedback,
            }
        )
        return {"final_report": self.final_report}


class OrchestratorNodeTests(unittest.TestCase):
    def test_orchestrator_plan_registers_tasks(self) -> None:
        planner = FakePlannerCore(
            {
                "tasks": [
                    {
                        "task_id": "task_1",
                        "assignee": "Analyst",
                        "instruction": "2024년 영업이익률을 계산해줘.",
                    },
                    {
                        "task_id": "task_2",
                        "assignee": "Researcher",
                        "instruction": "영업이익률 변화의 맥락을 짧게 요약해줘.",
                    },
                ]
            }
        )
        node = make_run_orchestrator_plan(planner)
        state = build_initial_state(
            "삼성전자 2024년 영업이익률을 계산하고 배경을 설명해줘",
            report_scope={
                "company": "삼성전자",
                "report_type": "사업보고서",
                "rcept_no": "20250311001085",
                "year": "2024",
                "consolidation": "연결",
            },
        )

        updates = node(state)

        self.assertEqual(len(planner.calls), 1)
        self.assertEqual(planner.calls[0]["report_scope"]["company"], "삼성전자")
        self.assertEqual(set(updates["tasks"].keys()), {"task_1", "task_2"})
        self.assertEqual(updates["tasks"]["task_1"]["status"], TaskStatus.PENDING)
        self.assertEqual(updates["tasks"]["task_1"]["context_keys"], ["numeric_values"])
        self.assertEqual(updates["tasks"]["task_2"]["context_keys"], ["narrative_evidence"])
        self.assertEqual(updates["execution_trace"], ["Orchestrator planned 2 tasks"])

    def test_orchestrator_merge_synthesizes_final_report(self) -> None:
        merge = FakeMergeCore("최종 보고서")
        node = make_run_orchestrator_merge(merge)
        state: MultiAgentState = build_initial_state("질문")
        state["artifacts"] = {
            "task_1": Artifact(
                task_id="task_1",
                creator="Analyst",
                content={"answer": "영업이익률은 10.9%입니다."},
                evidence_links=["chunk-a"],
            ),
            "task_2": Artifact(
                task_id="task_2",
                creator="Researcher",
                content={"answer": "반도체 수요 회복이 배경입니다."},
                evidence_links=["chunk-b"],
            ),
        }
        state["critic_feedback"] = "all good"

        updates = node(state)

        self.assertEqual(len(merge.calls), 1)
        self.assertEqual(updates["final_report"], "최종 보고서")
        self.assertEqual(updates["execution_trace"], ["Orchestrator synthesized final report"])

    def test_full_graph_can_use_injected_orchestrators(self) -> None:
        planner = FakePlannerCore(
            {
                "tasks": [
                    {
                        "task_id": "task_1",
                        "assignee": "Analyst",
                        "instruction": "계산해줘.",
                    },
                    {
                        "task_id": "task_2",
                        "assignee": "Researcher",
                        "instruction": "설명해줘.",
                    },
                ]
            }
        )
        merge = FakeMergeCore("병합 완료")

        final = run_mas_graph(
            "삼성전자 24년 분석해줘",
            orchestrator_plan_node=make_run_orchestrator_plan(planner),
            orchestrator_merge_node=make_run_orchestrator_merge(merge),
        )

        self.assertEqual(final["final_report"], "병합 완료")
        self.assertEqual(final["execution_trace"][0], "Orchestrator planned 2 tasks")
        self.assertEqual(final["execution_trace"][-1], "Orchestrator synthesized final report")


if __name__ == "__main__":
    unittest.main()
