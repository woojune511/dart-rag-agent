import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.nodes.critic_node import MAX_CRITIC_RETRIES
from src.experimental.mas.graph import build_initial_state
from src.experimental.mas.nodes import run_critic
from src.experimental.mas.types import (
    TaskStatus,
    build_critic_report,
    critic_report_runtime_acceptance_state,
    project_worker_artifact_boundary,
)


class DeterministicCriticTests(unittest.TestCase):
    def test_worker_artifact_boundary_is_payload_first_and_dedupes_refs(self) -> None:
        boundary = project_worker_artifact_boundary(
            {
                "task_id": "task_1",
                "creator": "Analyst",
                "artifact_id": "artifact_1",
                "kind": "calculation_result",
                "status": "ok",
                "content": {"answer": "stale content answer"},
                "payload": {"answer": "payload answer"},
                "evidence_links": ["chunk-a"],
                "evidence_refs": ["chunk-b", "chunk-b", "chunk-a"],
            }
        )

        self.assertEqual(boundary["artifact_id"], "artifact_1")
        self.assertEqual(boundary["task_id"], "task_1")
        self.assertEqual(boundary["creator"], "Analyst")
        self.assertEqual(boundary["kind"], "calculation_result")
        self.assertEqual(boundary["status"], "ok")
        self.assertEqual(boundary["answer"], "payload answer")
        self.assertEqual(boundary["payload"], {"answer": "payload answer"})
        self.assertEqual(boundary["evidence_refs"], ["chunk-b", "chunk-a"])

    def test_critic_prefers_structured_result_when_present(self) -> None:
        state = build_initial_state("삼성전자 2024년 영업이익률 알려줘")
        state["tasks"] = {
            "task_1": {
                "task_id": "task_1",
                "assignee": "Analyst",
                "instruction": "영업이익률 계산",
                "status": TaskStatus.COMPLETED,
                "context_keys": ["numeric_values"],
                "retry_count": 0,
            }
        }
        state["artifacts"] = {
            "task_1": {
                "task_id": "task_1",
                "creator": "Analyst",
                "content": {
                    "answer": "2024년 영업이익률은 10.9%입니다.",
                    "structured_result": {
                        "status": "ok",
                        "rendered_value": "10.9%",
                        "result_unit": "%",
                    },
                    "resolved_calculation_trace": {
                        "calculation_result": {
                            "status": "stale",
                            "rendered_value": "999",
                            "result_unit": "KRW",
                        }
                    },
                },
                "evidence_links": ["chunk-001"],
            }
        }

        updates = run_critic(state)

        self.assertTrue(updates["critic_reports"][0]["passed"])
        self.assertEqual(updates["critic_reports"][0]["deterministic_score"], 1.0)
        self.assertEqual(updates["critic_reports"][0]["verdict"], "passed")
        self.assertEqual(updates["critic_reports"][0]["target_task_id"], "task_1")
        self.assertEqual(updates["critic_reports"][0]["target_artifact_ids"], ["task_1"])
        self.assertTrue(updates["critic_reports"][0]["acceptance_reason"])
        self.assertEqual(updates["critic_reports"][0]["blocking_issues"], [])
        self.assertEqual(
            updates["artifacts"]["critic::task_1"]["payload"]["critic_report"],
            updates["critic_reports"][0],
        )
        self.assertEqual(updates["tasks"]["critic::task_1"]["depends_on"], ["task_1"])
        self.assertEqual(updates["tasks"]["critic::task_1"]["artifact_ids"], ["critic::task_1"])
        self.assertIn("Critic passed all artifacts (Deterministic)", updates["execution_trace"])

    def test_critic_prefers_typed_payload_and_evidence_refs(self) -> None:
        state = build_initial_state("payload-first critic check")
        state["tasks"] = {
            "task_1": {
                "task_id": "task_1",
                "assignee": "Analyst",
                "instruction": "Use typed artifact payload.",
                "status": TaskStatus.COMPLETED,
                "context_keys": ["numeric_values"],
                "retry_count": 0,
            }
        }
        state["artifacts"] = {
            "task_1": {
                "task_id": "task_1",
                "creator": "Analyst",
                "artifact_id": "artifact_1",
                "content": {
                    "answer": "",
                    "structured_result": {
                        "status": "stale",
                        "rendered_value": "999",
                        "result_unit": "KRW",
                    },
                },
                "payload": {
                    "answer": "10.9%",
                    "structured_result": {
                        "status": "ok",
                        "rendered_value": "10.9%",
                        "result_unit": "%",
                    },
                },
                "evidence_links": [],
                "evidence_refs": ["chunk-payload"],
            }
        }

        updates = run_critic(state)

        self.assertTrue(updates["critic_reports"][0]["passed"])
        self.assertEqual(updates["critic_reports"][0]["target_artifact_ids"], ["artifact_1"])
        self.assertIn("chunk-payload", updates["artifacts"]["critic::task_1"]["evidence_refs"])

    def test_critic_rejects_analyst_artifact_without_evidence_links(self) -> None:
        state = build_initial_state("삼성전자 2024년 영업이익률 알려줘")
        state["tasks"] = {
            "task_1": {
                "task_id": "task_1",
                "assignee": "Analyst",
                "instruction": "영업이익률 계산",
                "status": TaskStatus.COMPLETED,
                "context_keys": ["numeric_values"],
                "retry_count": 0,
            }
        }
        state["artifacts"] = {
            "task_1": {
                "task_id": "task_1",
                "creator": "Analyst",
                "content": {
                    "answer": "2024년 영업이익률은 10.9%입니다.",
                    "structured_result": {
                        "status": "ok",
                        "rendered_value": "10.9%",
                        "result_unit": "%",
                    },
                },
                "evidence_links": [],
            }
        }

        updates = run_critic(state)

        self.assertEqual(updates["tasks"]["task_1"]["status"], TaskStatus.REJECTED_BY_CRITIC)
        self.assertFalse(updates["critic_reports"][0]["passed"])
        self.assertEqual(updates["critic_reports"][0]["verdict"], "rejected")
        self.assertEqual(updates["critic_reports"][0]["target_artifact_ids"], ["task_1"])
        self.assertEqual(updates["critic_reports"][0]["acceptance_reason"], "")
        self.assertEqual(
            updates["critic_reports"][0]["blocking_issues"],
            [updates["critic_reports"][0]["llm_feedback"]],
        )
        self.assertEqual(
            updates["artifacts"]["critic::task_1"]["payload"]["critic_report"],
            updates["critic_reports"][0],
        )
        self.assertIn("grounding 실패", updates["critic_reports"][0]["llm_feedback"])
        self.assertIn("Critic rejected some artifacts (Deterministic)", updates["execution_trace"])

    def test_critic_marks_failed_after_max_retries(self) -> None:
        state = build_initial_state("삼성전자 2024년 영업이익률 알려줘")
        state["tasks"] = {
            "task_1": {
                "task_id": "task_1",
                "assignee": "Analyst",
                "instruction": "영업이익률 계산",
                "status": TaskStatus.COMPLETED,
                "context_keys": ["numeric_values"],
                "retry_count": MAX_CRITIC_RETRIES,
            }
        }
        state["artifacts"] = {
            "task_1": {
                "task_id": "task_1",
                "creator": "Analyst",
                "content": {"answer": "", "structured_result": {"status": "insufficient_operands"}},
                "evidence_links": [],
            }
        }

        updates = run_critic(state)

        self.assertEqual(updates["tasks"]["task_1"]["status"], TaskStatus.FAILED)
        self.assertFalse(updates["critic_reports"][0]["passed"])
        self.assertIn("최대 재시도 횟수", updates["critic_reports"][0]["llm_feedback"])

    def test_critic_does_not_resurrect_failed_worker_task(self) -> None:
        state = build_initial_state("삼성전자 2024년 영업이익률 알려줘")
        state["tasks"] = {
            "task_1": {
                "task_id": "task_1",
                "assignee": "Analyst",
                "instruction": "영업이익률 계산",
                "status": TaskStatus.FAILED,
                "context_keys": ["numeric_values"],
                "retry_count": 0,
            }
        }
        state["artifacts"] = {}

        updates = run_critic(state)

        self.assertNotIn("task_1", updates["tasks"])
        self.assertEqual(updates["critic_reports"], [])
        self.assertIn("Critic passed all artifacts (Deterministic)", updates["execution_trace"])

    def test_critic_rejects_researcher_artifact_without_evidence_links(self) -> None:
        state = build_initial_state("삼성전자 2024년 주요 사업 현황을 요약해줘")
        state["tasks"] = {
            "task_2": {
                "task_id": "task_2",
                "assignee": "Researcher",
                "instruction": "사업 현황 요약",
                "status": TaskStatus.COMPLETED,
                "context_keys": ["narrative_evidence"],
                "retry_count": 0,
            }
        }
        state["artifacts"] = {
            "task_2": {
                "task_id": "task_2",
                "creator": "Researcher",
                "content": {"answer": "DX와 DS 중심으로 사업을 운영합니다."},
                "evidence_links": [],
            }
        }

        updates = run_critic(state)

        self.assertEqual(updates["tasks"]["task_2"]["status"], TaskStatus.REJECTED_BY_CRITIC)
        self.assertFalse(updates["critic_reports"][0]["passed"])
        self.assertIn("리서치 근거 링크", updates["critic_reports"][0]["llm_feedback"])


    def test_build_critic_report_normalizes_acceptance_and_blocking_fields(self) -> None:
        passed = build_critic_report(
            target_task_id=" task_1 ",
            passed=True,
            deterministic_score=1,
            feedback=" grounded ",
            target_artifact_id=" artifact_1 ",
        )

        self.assertEqual(passed["target_task_id"], "task_1")
        self.assertEqual(passed["verdict"], "passed")
        self.assertEqual(passed["target_artifact_ids"], ["artifact_1"])
        self.assertEqual(passed["acceptance_reason"], "grounded")
        self.assertEqual(passed["blocking_issues"], [])
        self.assertEqual(passed["llm_feedback"], "grounded")

        rejected = build_critic_report(
            target_task_id="task_2",
            passed=False,
            deterministic_score=0,
            feedback="missing evidence",
            target_artifact_ids=["artifact_2", " "],
        )

        self.assertEqual(rejected["verdict"], "rejected")
        self.assertEqual(rejected["target_artifact_ids"], ["artifact_2"])
        self.assertEqual(rejected["acceptance_reason"], "")
        self.assertEqual(rejected["blocking_issues"], ["missing evidence"])

    def test_runtime_acceptance_does_not_use_score_threshold(self) -> None:
        passed = build_critic_report(
            target_task_id="task_1",
            passed=True,
            deterministic_score=0,
            feedback="grounded",
            target_artifact_id="artifact_1",
        )

        passed_state = critic_report_runtime_acceptance_state(dict(passed))

        self.assertTrue(passed_state["accepted"])
        self.assertEqual(passed_state["runtime_acceptance_status"], "accepted")
        self.assertEqual(passed_state["reasons"], [])
        self.assertEqual(passed_state["target_refs"], ["task_1", "artifact_1"])
        self.assertFalse(passed_state["deterministic_score_used_for_acceptance"])

        rejected = build_critic_report(
            target_task_id="task_2",
            passed=False,
            deterministic_score=1,
            feedback="missing evidence",
            target_artifact_id="artifact_2",
        )

        rejected_state = critic_report_runtime_acceptance_state(dict(rejected))

        self.assertFalse(rejected_state["accepted"])
        self.assertEqual(rejected_state["runtime_acceptance_status"], "blocked")
        self.assertIn("critic_rejected", rejected_state["reasons"])
        self.assertFalse(rejected_state["deterministic_score_used_for_acceptance"])

    def test_runtime_acceptance_normalizes_verdict_or_status_without_score_threshold(self) -> None:
        verdict_only_passed = {
            "verdict": "passed",
            "target_task_id": "task_1",
            "target_artifact_ids": ["artifact_1"],
            "acceptance_reason": "grounded",
            "deterministic_score": 0.0,
        }

        passed_state = critic_report_runtime_acceptance_state(dict(verdict_only_passed))

        self.assertTrue(passed_state["accepted"])
        self.assertEqual(passed_state["runtime_acceptance_status"], "accepted")
        self.assertEqual(passed_state["reasons"], [])
        self.assertFalse(passed_state["deterministic_score_used_for_acceptance"])

        status_only_rejected = {
            "status": "rejected",
            "target_task_id": "task_2",
            "target_artifact_ids": ["artifact_2"],
            "blocking_issues": ["missing evidence"],
            "deterministic_score": 1.0,
        }

        rejected_state = critic_report_runtime_acceptance_state(dict(status_only_rejected))

        self.assertFalse(rejected_state["accepted"])
        self.assertEqual(rejected_state["runtime_acceptance_status"], "blocked")
        self.assertIn("critic_rejected", rejected_state["reasons"])
        self.assertFalse(rejected_state["deterministic_score_used_for_acceptance"])

    def test_runtime_acceptance_blocks_conflicting_verdict_signals(self) -> None:
        report = {
            "passed": True,
            "verdict": "rejected",
            "target_task_id": "task_1",
            "target_artifact_ids": ["artifact_1"],
            "acceptance_reason": "grounded",
            "deterministic_score": 1.0,
        }

        state = critic_report_runtime_acceptance_state(dict(report))

        self.assertFalse(state["accepted"])
        self.assertEqual(state["runtime_acceptance_status"], "blocked")
        self.assertIn("conflicting_verdict_signal", state["reasons"])
        self.assertFalse(state["deterministic_score_used_for_acceptance"])


if __name__ == "__main__":
    unittest.main()
