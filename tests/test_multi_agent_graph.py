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
from src.agent.mas_types import AgentTask, Artifact, MultiAgentState, TaskStatus, build_artifact
from src.agent.nodes.orchestrator_node import (
    _planner_feedback_from_integrity_issues,
    make_run_orchestrator_merge,
    make_run_orchestrator_plan,
)
from src.schema import ArtifactKind


class StatefulPlannerCore:
    def __init__(self) -> None:
        self.calls = []

    def run(self, query: str, *, report_scope=None):
        self.calls.append(query)
        task_id = "task_1" if len(self.calls) == 1 else "task_2"
        return {
            "tasks": [
                {
                    "task_id": task_id,
                    "assignee": "Analyst",
                    "instruction": f"Compute {task_id}.",
                }
            ]
        }


class OrchestratorIntegrityFeedbackTests(unittest.TestCase):
    def test_planner_feedback_surfaces_critic_rejection_details(self) -> None:
        feedback = _planner_feedback_from_integrity_issues(
            [
                {
                    "type": "critic_report_rejected",
                    "severity": "error",
                    "task_id": "task_critic",
                    "artifact_kind": "critic_report",
                    "runtime_acceptance_status": "blocked",
                    "reasons": ["critic_rejected"],
                    "target_refs": ["task_synthesis", "artifact_synthesis"],
                }
            ]
        )

        self.assertIn("critic_report_rejected", feedback)
        self.assertIn("task_critic", feedback)
        self.assertIn("status=blocked", feedback)
        self.assertIn("reasons=critic_rejected", feedback)
        self.assertIn("targets=task_synthesis,artifact_synthesis", feedback)


def make_replan_test_analyst_node():
    def run_analyst(state: MultiAgentState):
        task_updates: dict[str, AgentTask] = {}
        artifact_updates: dict[str, Artifact] = {}
        trace: list[str] = []
        for task_id, task in dict(state.get("tasks") or {}).items():
            if task.get("assignee") != "Analyst" or task.get("status") != TaskStatus.PENDING:
                continue
            if task_id == "task_1":
                task_updates[task_id] = {
                    **task,
                    "status": TaskStatus.COMPLETED,
                    "artifact_ids": ["task_1"],
                }
                artifact_updates["task_1"] = build_artifact(
                    task_id="task_1",
                    creator="Analyst",
                    artifact_id="task_1",
                    kind=ArtifactKind.CALCULATION_RESULT.value,
                    status="ok",
                    summary="incomplete",
                    content={"answer": "incomplete"},
                    payload={"answer": "incomplete", "calculation_result": {"status": "ok", "formatted_result": "incomplete"}},
                    evidence_links=["chunk://old"],
                )
                trace.append("Analyst completed incomplete task_1")
                continue

            evidence_refs = ["chunk://new"]
            task_updates[task_id] = {
                **task,
                "status": TaskStatus.COMPLETED,
                "artifact_ids": [f"{task_id}::operand_set", f"{task_id}::calculation_plan", task_id],
            }
            artifact_updates[f"{task_id}::operand_set"] = build_artifact(
                task_id=task_id,
                creator="Analyst",
                artifact_id=f"{task_id}::operand_set",
                kind=ArtifactKind.OPERAND_SET.value,
                status="ok",
                summary="1 operands",
                content={"calculation_operands": [{"label": "value", "row_id": evidence_refs[0]}]},
                payload={"calculation_operands": [{"label": "value", "row_id": evidence_refs[0]}]},
                evidence_links=evidence_refs,
            )
            artifact_updates[f"{task_id}::calculation_plan"] = build_artifact(
                task_id=task_id,
                creator="Analyst",
                artifact_id=f"{task_id}::calculation_plan",
                kind=ArtifactKind.CALCULATION_PLAN.value,
                status="ok",
                summary="lookup",
                content={"calculation_plan": {"mode": "lookup"}},
                payload={"calculation_plan": {"mode": "lookup"}},
                evidence_links=evidence_refs,
            )
            artifact_updates[task_id] = build_artifact(
                task_id=task_id,
                creator="Analyst",
                artifact_id=task_id,
                kind=ArtifactKind.CALCULATION_RESULT.value,
                status="ok",
                summary="complete",
                content={"answer": "complete"},
                payload={"answer": "complete", "calculation_result": {"status": "ok", "formatted_result": "complete"}},
                evidence_links=evidence_refs,
            )
            trace.append(f"Analyst completed repaired {task_id}")
        return {
            "tasks": task_updates,
            "artifacts": artifact_updates,
            "execution_trace": trace,
        }

    return run_analyst


def no_op_researcher_node(_state: MultiAgentState):
    return {"execution_trace": []}


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

        self.assertEqual(
            set(final["tasks"].keys()),
            {"task_1", "task_2", "critic::task_1", "critic::task_2", "synthesis::final"},
        )
        self.assertEqual(final["tasks"]["task_1"]["status"], TaskStatus.COMPLETED)
        self.assertEqual(final["tasks"]["task_2"]["status"], TaskStatus.COMPLETED)
        self.assertEqual(final["tasks"]["task_1"]["kind"], "calculation")
        self.assertEqual(final["tasks"]["task_2"]["kind"], "retrieval")
        self.assertEqual(
            final["tasks"]["task_1"]["artifact_ids"],
            ["task_1::operand_set", "task_1::calculation_plan", "task_1"],
        )
        self.assertEqual(final["tasks"]["critic::task_1"]["kind"], "critic")
        self.assertEqual(final["tasks"]["synthesis::final"]["kind"], "synthesis")
        self.assertIn("task_1::operand_set", final["artifacts"])
        self.assertIn("task_1::calculation_plan", final["artifacts"])
        self.assertIn("task_1", final["artifacts"])
        self.assertIn("task_2", final["artifacts"])
        self.assertIn("critic::task_1", final["artifacts"])
        self.assertIn("synthesis::final", final["artifacts"])
        self.assertEqual(final["artifacts"]["critic::task_1"]["kind"], "critic_report")
        self.assertEqual(final["artifacts"]["synthesis::final"]["kind"], "aggregated_answer")
        self.assertEqual(final["final_report_record"]["final_answer"], final["final_report"])
        self.assertEqual(
            final["artifacts"]["synthesis::final"]["payload"]["final_answer"],
            final["final_report_record"]["final_answer"],
        )
        self.assertEqual(
            final["final_report_record"]["source_task_ids"],
            ["task_1", "task_2"],
        )
        self.assertEqual(
            final["final_report_record"]["source_artifact_ids"],
            ["task_1::operand_set", "task_1::calculation_plan", "task_1", "task_2"],
        )
        self.assertEqual(
            [
                row.get("artifact_id")
                for row in final["final_report_record"]["subtask_results"]
            ],
            ["task_1", "task_2"],
        )
        self.assertEqual(
            final["final_report_record"]["evidence_refs"],
            final["final_report_record"]["source_artifact_ids"],
        )
        self.assertEqual(final["task_artifact_trace"]["integrity_status"], "ok")
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
        self.assertEqual(final["final_report_record"]["final_answer"], final["final_report"])
        self.assertEqual(final["final_report_record"]["status"], "ok")
        self.assertEqual(final["task_artifact_trace"]["integrity_status"], "ok")
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

    def test_merge_replan_required_routes_back_to_planning_once(self) -> None:
        planner = StatefulPlannerCore()

        final = run_mas_graph(
            "repair incomplete calculation",
            replan_budget=1,
            orchestrator_plan_node=make_run_orchestrator_plan(planner),
            orchestrator_merge_node=make_run_orchestrator_merge(
                type("StaticMergeCore", (), {"run": lambda self, query, **kwargs: {"final_report": "merged"}})()
            ),
            analyst_node=make_replan_test_analyst_node(),
            researcher_node=no_op_researcher_node,
        )

        self.assertEqual(len(planner.calls), 2)
        self.assertNotIn("[planner feedback]", planner.calls[0])
        self.assertIn("[planner feedback]", planner.calls[1])
        self.assertEqual(final["replan_count"], 1)
        self.assertEqual(final["tasks"]["task_1"]["status"], TaskStatus.FAILED)
        self.assertEqual(final["tasks"]["task_1"]["artifact_ids"], [])
        self.assertEqual(final["tasks"]["task_2"]["status"], TaskStatus.COMPLETED)
        self.assertEqual(final["final_report_record"]["status"], "ok")
        self.assertEqual(final["task_artifact_trace"]["integrity_status"], "ok")
        self.assertEqual(
            final["final_report_record"]["source_artifact_ids"],
            ["task_2::operand_set", "task_2::calculation_plan", "task_2"],
        )
        self.assertNotIn("task_1", final["final_report_record"]["source_artifact_ids"])
        self.assertIn("Orchestrator requested replan on integrity errors", final["execution_trace"])
        self.assertIn("Orchestrator replanned 1 tasks", final["execution_trace"])


if __name__ == "__main__":
    unittest.main()
