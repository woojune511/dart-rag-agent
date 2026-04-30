import sys
import unittest
from pathlib import Path

from langchain_core.documents import Document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.mas_graph import build_initial_state, run_mas_graph
from src.agent.mas_types import MultiAgentState, TaskStatus
from src.agent.nodes.researcher_node import make_run_researcher


class FakeResearcherCore:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result or {}
        self.error = error
        self.calls = []

    def run(self, query: str, *, report_scope=None):
        self.calls.append({"query": query, "report_scope": dict(report_scope or {})})
        if self.error is not None:
            raise self.error
        return self.result


def _researcher_state(status: TaskStatus = TaskStatus.PENDING) -> MultiAgentState:
    state = build_initial_state(
        "삼성전자 2024년 주요 사업 현황을 요약해줘",
        report_scope={
            "company": "삼성전자",
            "report_type": "사업보고서",
            "rcept_no": "20250311001085",
            "year": "2024",
            "consolidation": "연결",
        },
    )
    state["tasks"] = {
        "task_2": {
            "task_id": "task_2",
            "assignee": "Researcher",
            "instruction": "삼성전자 2024년 주요 사업 현황을 짧게 요약해줘.",
            "status": status,
            "context_keys": ["narrative_evidence"],
            "retry_count": 0,
        }
    }
    return state


class ResearcherNodeMigrationTests(unittest.TestCase):
    def test_run_researcher_writes_artifact_and_evidence_pool(self) -> None:
        result = {
            "answer": "DX와 DS를 중심으로 글로벌 전자 사업을 운영하며, 모바일·반도체·디스플레이가 핵심입니다.",
            "citations": ["[삼성전자 | 2024 | II. 사업의 내용 > 1. 사업의 개요]"],
            "summary_points": ["DX/DS 중심", "모바일/반도체/디스플레이 핵심"],
            "retrieved_docs": [
                (
                    Document(
                        page_content="삼성전자는 DX와 DS를 중심으로 사업을 영위한다.",
                        metadata={"chunk_uid": "chunk-r-001", "section_path": "II. 사업의 내용 > 1. 사업의 개요"},
                    ),
                    0.88,
                )
            ],
        }
        fake = FakeResearcherCore(result=result)
        node = make_run_researcher(fake)

        updates = node(_researcher_state())

        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0]["report_scope"]["company"], "삼성전자")
        self.assertEqual(updates["tasks"]["task_2"]["status"], TaskStatus.COMPLETED)
        artifact = updates["artifacts"]["task_2"]
        self.assertEqual(artifact["creator"], "Researcher")
        self.assertIn("DX와 DS", artifact["content"]["answer"])
        self.assertIn("chunk-r-001", artifact["evidence_links"])
        self.assertEqual(len(updates["evidence_pool"]), 1)
        self.assertIn("Researcher completed task_2", updates["execution_trace"])

    def test_run_researcher_marks_failed_on_empty_result(self) -> None:
        fake = FakeResearcherCore(result={"answer": ""})
        node = make_run_researcher(fake)

        updates = node(_researcher_state())

        self.assertEqual(updates["tasks"]["task_2"]["status"], TaskStatus.FAILED)
        self.assertEqual(updates["artifacts"], {})
        self.assertIn("Researcher failed task_2: empty narrative result", updates["execution_trace"])

    def test_full_graph_can_use_injected_researcher_node(self) -> None:
        fake = FakeResearcherCore(
            result={
                "answer": "주요 사업은 DX와 DS 중심으로 운영됩니다.",
                "citations": ["[삼성전자 | 2024 | II. 사업의 내용 > 1. 사업의 개요]"],
                "summary_points": ["DX와 DS 중심"],
                "retrieved_docs": [
                    (
                        Document(
                            page_content="dummy",
                            metadata={"chunk_uid": "chunk-r-002", "section_path": "II. 사업의 내용 > 1. 사업의 개요"},
                        ),
                        0.9,
                    )
                ],
            }
        )
        final = run_mas_graph(
            "삼성전자 24년 분석해줘",
            researcher_node=make_run_researcher(fake),
        )

        self.assertIn("Researcher completed task_2", final["execution_trace"])
        self.assertEqual(final["tasks"]["task_2"]["status"], TaskStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
