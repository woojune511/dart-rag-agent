import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.mas_graph import build_initial_state
from src.agent.mas_types import TaskStatus
from src.agent.nodes.critic_node import MAX_CRITIC_RETRIES, run_critic


class DeterministicCriticTests(unittest.TestCase):
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
                    "calculation_result": {
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
                "content": {"answer": "", "calculation_result": {"status": "insufficient_operands"}},
                "evidence_links": [],
            }
        }

        updates = run_critic(state)

        self.assertEqual(updates["tasks"]["task_1"]["status"], TaskStatus.FAILED)
        self.assertFalse(updates["critic_reports"][0]["passed"])
        self.assertIn("최대 재시도 횟수", updates["critic_reports"][0]["llm_feedback"])

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


if __name__ == "__main__":
    unittest.main()
