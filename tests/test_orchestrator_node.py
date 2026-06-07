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
from src.agent.mas_types import (
    Artifact,
    MultiAgentState,
    TaskStatus,
    build_agent_task,
    build_artifact,
    project_final_report_carry_forward,
)
from src.agent.nodes.orchestrator_node import (
    MERGE_ANSWER_COMPRESSION_GUIDANCE,
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


class FailingPlannerCore:
    def run(self, query: str, *, report_scope=None):
        raise RuntimeError("planner unavailable")


class FailingMergeCore:
    def run(self, query: str, *, report_scope=None, artifacts=None, critic_feedback=None):
        raise RuntimeError("merge unavailable")


class OrchestratorNodeTests(unittest.TestCase):
    def test_merge_compression_guidance_prioritizes_numeric_then_context(self) -> None:
        self.assertIn("Start with the direct numeric conclusion", MERGE_ANSWER_COMPRESSION_GUIDANCE)
        self.assertIn("2-4 material points", MERGE_ANSWER_COMPRESSION_GUIDANCE)
        self.assertIn("Preserve worker-provided values", MERGE_ANSWER_COMPRESSION_GUIDANCE)
        self.assertIn("Do not copy evidence refs", MERGE_ANSWER_COMPRESSION_GUIDANCE)
        self.assertNotIn("{", MERGE_ANSWER_COMPRESSION_GUIDANCE)
        self.assertNotIn("}", MERGE_ANSWER_COMPRESSION_GUIDANCE)

    def test_build_agent_task_normalizes_optional_contract_fields(self) -> None:
        task = build_agent_task(
            task_id=" task_x ",
            assignee=" Analyst ",
            instruction=" Do work ",
            status="completed",
            context_keys=[" numeric_values ", ""],
            retry_count=2,
            kind=" calculation ",
            label=" Label ",
            depends_on=[" task_a ", " "],
            artifact_ids=[" artifact_a ", ""],
            blocked_reason=" waiting ",
        )

        self.assertEqual(task["task_id"], "task_x")
        self.assertEqual(task["assignee"], "Analyst")
        self.assertEqual(task["instruction"], "Do work")
        self.assertEqual(task["status"], TaskStatus.COMPLETED)
        self.assertEqual(task["context_keys"], ["numeric_values"])
        self.assertEqual(task["retry_count"], 2)
        self.assertEqual(task["kind"], "calculation")
        self.assertEqual(task["label"], "Label")
        self.assertEqual(task["depends_on"], ["task_a"])
        self.assertEqual(task["artifact_ids"], ["artifact_a"])
        self.assertEqual(task["blocked_reason"], "waiting")

    def test_build_artifact_normalizes_projection_fields(self) -> None:
        artifact = build_artifact(
            task_id=" task_1 ",
            creator=" Analyst ",
            artifact_id=" artifact_1 ",
            kind=" calculation_result ",
            status="",
            summary=" Result ",
            content="42",
            evidence_links=[" chunk-a ", ""],
            metadata={"source": "unit"},
        )

        self.assertEqual(artifact["task_id"], "task_1")
        self.assertEqual(artifact["creator"], "Analyst")
        self.assertEqual(artifact["artifact_id"], "artifact_1")
        self.assertEqual(artifact["kind"], "calculation_result")
        self.assertEqual(artifact["status"], "ok")
        self.assertEqual(artifact["summary"], "Result")
        self.assertEqual(artifact["payload"], {"answer": "42"})
        self.assertEqual(artifact["evidence_links"], ["chunk-a"])
        self.assertEqual(artifact["evidence_refs"], ["chunk-a"])
        self.assertEqual(artifact["metadata"], {"source": "unit"})

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
        self.assertEqual(updates["tasks"]["task_1"]["kind"], "calculation")
        self.assertEqual(updates["tasks"]["task_1"]["context_keys"], ["numeric_values"])
        self.assertEqual(updates["tasks"]["task_2"]["kind"], "retrieval")
        self.assertEqual(updates["tasks"]["task_2"]["context_keys"], ["narrative_evidence"])
        self.assertEqual(updates["execution_trace"], ["Orchestrator planned 2 tasks"])

    def test_orchestrator_replan_closes_blocking_tasks_and_passes_feedback(self) -> None:
        planner = FakePlannerCore(
            {
                "tasks": [
                    {
                        "task_id": "task_2",
                        "assignee": "Analyst",
                        "instruction": "Recompute with required artifacts.",
                    }
                ]
            }
        )
        node = make_run_orchestrator_plan(planner)
        state: MultiAgentState = build_initial_state("Question")
        state["planner_feedback"] = "missing calculation_plan artifact"
        state["tasks"] = {
            "task_1": build_agent_task(
                task_id="task_1",
                assignee="Analyst",
                instruction="Compute incomplete result.",
                status=TaskStatus.COMPLETED,
                context_keys=["numeric_values"],
                kind="calculation",
                artifact_ids=["task_1"],
            )
        }
        state["task_artifact_trace"] = {
            "integrity_status": "error",
            "integrity_issues": [
                {
                    "type": "missing_required_artifact_kind",
                    "severity": "error",
                    "task_id": "task_1",
                    "missing_artifact_kind": "calculation_plan",
                }
            ],
        }

        updates = node(state)

        self.assertIn("[planner feedback]", planner.calls[0]["query"])
        self.assertIn("missing calculation_plan artifact", planner.calls[0]["query"])
        self.assertEqual(updates["tasks"]["task_1"]["status"], TaskStatus.FAILED)
        self.assertEqual(updates["tasks"]["task_1"]["artifact_ids"], [])
        self.assertIn("missing_required_artifact_kind", updates["tasks"]["task_1"]["blocked_reason"])
        self.assertEqual(updates["tasks"]["task_2"]["status"], TaskStatus.PENDING)
        self.assertIsNone(updates["planner_feedback"])
        self.assertEqual(updates["execution_trace"], ["Orchestrator replanned 1 tasks"])

    def test_orchestrator_fallback_plans_both_generic_workers(self) -> None:
        node = make_run_orchestrator_plan(FailingPlannerCore())
        state = build_initial_state("Summarize the report and compute any requested figures.")

        updates = node(state)

        self.assertEqual(set(updates["tasks"].keys()), {"task_1", "task_2"})
        self.assertEqual(updates["tasks"]["task_1"]["assignee"], "Analyst")
        self.assertEqual(updates["tasks"]["task_1"]["kind"], "calculation")
        self.assertEqual(updates["tasks"]["task_1"]["context_keys"], ["numeric_values"])
        self.assertIn("numeric, table-backed, or calculation", updates["tasks"]["task_1"]["instruction"])
        self.assertEqual(updates["tasks"]["task_2"]["assignee"], "Researcher")
        self.assertEqual(updates["tasks"]["task_2"]["kind"], "retrieval")
        self.assertEqual(updates["tasks"]["task_2"]["context_keys"], ["narrative_evidence"])
        self.assertIn("narrative, contextual, or explanatory", updates["tasks"]["task_2"]["instruction"])

    def test_orchestrator_merge_synthesizes_final_report(self) -> None:
        merge = FakeMergeCore("최종 보고서")
        node = make_run_orchestrator_merge(merge)
        state: MultiAgentState = build_initial_state("질문")
        state["tasks"] = {
            "task_1": {
                "task_id": "task_1",
                "assignee": "Analyst",
                "instruction": "Analyze.",
                "status": TaskStatus.COMPLETED,
                "context_keys": ["numeric_values"],
                "retry_count": 0,
                "kind": "verification",
                "label": "Analyst source",
                "artifact_ids": ["task_1"],
            },
            "task_2": {
                "task_id": "task_2",
                "assignee": "Researcher",
                "instruction": "Research.",
                "status": TaskStatus.COMPLETED,
                "context_keys": ["narrative_evidence"],
                "retry_count": 0,
                "kind": "verification",
                "label": "Researcher source",
                "artifact_ids": ["task_2"],
            },
        }
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
        self.assertEqual(updates["final_report_record"]["final_answer"], "최종 보고서")
        self.assertEqual(
            updates["final_report_record"]["source_task_ids"],
            ["task_1", "task_2"],
        )
        self.assertEqual(
            updates["final_report_record"]["source_artifact_ids"],
            ["task_1", "task_2"],
        )
        self.assertEqual(
            updates["final_report_record"]["subtask_results"],
            [
                {
                    "task_id": "task_1",
                    "artifact_id": "task_1",
                    "source_artifact_id": "task_1",
                    "answer": "영업이익률은 10.9%입니다.",
                },
                {
                    "task_id": "task_2",
                    "artifact_id": "task_2",
                    "source_artifact_id": "task_2",
                    "answer": "반도체 수요 회복이 배경입니다.",
                },
            ],
        )
        carry_forward = project_final_report_carry_forward(updates["final_report_record"])
        self.assertEqual(carry_forward["source_task_ids"], ["task_1", "task_2"])
        self.assertEqual(carry_forward["source_artifact_ids"], ["task_1", "task_2"])
        self.assertEqual(carry_forward["subtask_artifact_ids"], ["task_1", "task_2"])
        self.assertEqual(
            updates["artifacts"]["synthesis::final"]["payload"],
            updates["final_report_record"],
        )
        self.assertEqual(updates["execution_trace"], ["Orchestrator synthesized final report"])

    def test_orchestrator_merge_prefers_typed_payload_projection(self) -> None:
        node = make_run_orchestrator_merge(FailingMergeCore())
        state: MultiAgentState = build_initial_state("Question")
        state["tasks"] = {
            "task_1": {
                "task_id": "task_1",
                "assignee": "Analyst",
                "instruction": "Analyze.",
                "status": TaskStatus.COMPLETED,
                "context_keys": ["numeric_values"],
                "retry_count": 0,
                "kind": "verification",
                "label": "Analyst source",
                "artifact_ids": ["artifact_1_pre", "artifact_1"],
            },
            "task_2": {
                "task_id": "task_2",
                "assignee": "Researcher",
                "instruction": "Research.",
                "status": TaskStatus.COMPLETED,
                "context_keys": ["narrative_evidence"],
                "retry_count": 0,
                "kind": "verification",
                "label": "Researcher source",
                "artifact_ids": ["artifact_2"],
            },
        }
        state["artifacts"] = {
            "artifact_1_pre": Artifact(
                task_id="task_1",
                creator="Analyst",
                artifact_id="artifact_1_pre",
                content={"calculation_operands": [{"label": "operand"}]},
                payload={"calculation_operands": [{"label": "operand"}]},
                evidence_links=[],
                evidence_refs=["payload-ref-a"],
            ),
            "task_1": Artifact(
                task_id="task_1",
                creator="Analyst",
                artifact_id="artifact_1",
                content={"answer": "stale analyst content"},
                payload={"answer": "payload analyst answer"},
                evidence_links=[],
                evidence_refs=["payload-ref-a", "payload-ref-a", "payload-ref-shared"],
            ),
            "task_2": Artifact(
                task_id="task_2",
                creator="Researcher",
                artifact_id="artifact_2",
                content={"answer": "stale researcher content"},
                payload={"answer": "payload researcher answer"},
                evidence_links=[],
                evidence_refs=["payload-ref-shared", "payload-ref-b"],
            ),
        }

        updates = node(state)

        self.assertIn("payload analyst answer", updates["final_report"])
        self.assertIn("payload researcher answer", updates["final_report"])
        self.assertNotIn("stale analyst content", updates["final_report"])
        self.assertEqual(
            updates["final_report_record"]["subtask_results"],
            [
                {
                    "task_id": "task_1",
                    "artifact_id": "artifact_1",
                    "source_artifact_id": "artifact_1",
                    "answer": "payload analyst answer",
                },
                {
                    "task_id": "task_2",
                    "artifact_id": "artifact_2",
                    "source_artifact_id": "artifact_2",
                    "answer": "payload researcher answer",
                },
            ],
        )
        self.assertEqual(
            updates["final_report_record"]["source_artifact_ids"],
            ["artifact_1_pre", "artifact_1", "artifact_2"],
        )
        self.assertEqual(
            updates["final_report_record"]["evidence_refs"],
            ["payload-ref-a", "payload-ref-shared", "payload-ref-b"],
        )
        self.assertEqual(
            updates["artifacts"]["synthesis::final"]["evidence_refs"],
            ["payload-ref-a", "payload-ref-shared", "payload-ref-b"],
        )

    def test_orchestrator_merge_blocks_final_close_on_integrity_error(self) -> None:
        node = make_run_orchestrator_merge(FakeMergeCore("ready final"))
        state: MultiAgentState = build_initial_state("Question")
        state["tasks"] = {
            "task_1": {
                "task_id": "task_1",
                "assignee": "Analyst",
                "instruction": "Compute a result.",
                "status": TaskStatus.COMPLETED,
                "context_keys": ["numeric_values"],
                "retry_count": 0,
                "kind": "calculation",
                "label": "Calculation task",
                "artifact_ids": ["task_1"],
            }
        }
        state["artifacts"] = {
            "task_1": Artifact(
                task_id="task_1",
                creator="Analyst",
                artifact_id="task_1",
                kind="calculation_result",
                status="ok",
                summary="10.9%",
                content={"answer": "10.9%"},
                payload={"answer": "10.9%", "calculation_result": {"status": "ok", "formatted_result": "10.9%"}},
                evidence_links=["chunk-a"],
                evidence_refs=["chunk-a"],
            ),
        }

        updates = node(state)

        self.assertEqual(updates["final_report_record"]["status"], "blocked")
        self.assertIn("Cannot close as fully answered", updates["final_report"])
        self.assertEqual(updates["tasks"]["synthesis::final"]["status"], TaskStatus.FAILED)
        self.assertEqual(updates["artifacts"]["synthesis::final"]["status"], "blocked")
        self.assertEqual(updates["task_artifact_trace"]["integrity_status"], "error")
        issue_types = [issue["type"] for issue in updates["task_artifact_trace"]["integrity_issues"]]
        self.assertIn("missing_required_artifact_kind", issue_types)
        self.assertIn(
            "blocking_integrity_issues",
            updates["artifacts"]["synthesis::final"]["payload"],
        )

    def test_orchestrator_merge_requests_replan_when_budget_remains(self) -> None:
        node = make_run_orchestrator_merge(FakeMergeCore("ready final"))
        state: MultiAgentState = build_initial_state("Question", replan_budget=1)
        state["tasks"] = {
            "task_1": {
                "task_id": "task_1",
                "assignee": "Analyst",
                "instruction": "Compute a result.",
                "status": TaskStatus.COMPLETED,
                "context_keys": ["numeric_values"],
                "retry_count": 0,
                "kind": "calculation",
                "label": "Calculation task",
                "artifact_ids": ["task_1"],
            }
        }
        state["artifacts"] = {
            "task_1": Artifact(
                task_id="task_1",
                creator="Analyst",
                artifact_id="task_1",
                kind="calculation_result",
                status="ok",
                summary="10.9%",
                content={"answer": "10.9%"},
                payload={"answer": "10.9%", "calculation_result": {"status": "ok", "formatted_result": "10.9%"}},
                evidence_links=["chunk-a"],
                evidence_refs=["chunk-a"],
            ),
        }

        updates = node(state)

        self.assertIsNone(updates["final_report"])
        self.assertEqual(updates["final_report_record"]["status"], "replan_required")
        self.assertEqual(updates["replan_count"], 1)
        self.assertIn("missing_required_artifact_kind", updates["planner_feedback"])
        self.assertEqual(updates["task_artifact_trace"]["integrity_status"], "error")
        self.assertNotIn("synthesis::final", updates.get("artifacts", {}))
        self.assertEqual(updates["execution_trace"], ["Orchestrator requested replan on integrity errors"])

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
        self.assertEqual(final["final_report_record"]["final_answer"], "병합 완료")
        self.assertEqual(final["execution_trace"][0], "Orchestrator planned 2 tasks")
        self.assertEqual(final["execution_trace"][-1], "Orchestrator synthesized final report")


if __name__ == "__main__":
    unittest.main()
