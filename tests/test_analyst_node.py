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
from src.agent.nodes.analyst_node import make_run_analyst


class FakeAnalystCore:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result or {}
        self.error = error
        self.calls = []

    def run(self, query: str, *, report_scope=None):
        self.calls.append({"query": query, "report_scope": dict(report_scope or {})})
        if self.error is not None:
            raise self.error
        return self.result


def _analyst_state(status: TaskStatus = TaskStatus.PENDING) -> MultiAgentState:
    state = build_initial_state(
        "삼성전자 2024년 영업이익률 알려줘",
        report_scope={
            "company": "삼성전자",
            "report_type": "사업보고서",
            "rcept_no": "20250311001085",
            "year": "2024",
            "consolidation": "연결",
        },
    )
    state["tasks"] = {
        "task_1": {
            "task_id": "task_1",
            "assignee": "Analyst",
            "instruction": "2024년 삼성전자 영업이익률을 계산해줘",
            "status": status,
            "context_keys": ["numeric_values"],
            "retry_count": 0,
        }
    }
    return state


class AnalystNodeMigrationTests(unittest.TestCase):
    def test_run_analyst_writes_artifact_and_evidence_pool(self) -> None:
        result = {
            "answer": "2024년 영업이익률은 10.9%입니다.",
            "query_type": "comparison",
            "intent": "comparison",
            "target_metric_family": "operating_margin",
            "citations": ["[삼성전자 | 2024 | III. 재무에 관한 사항 > 1. 요약재무정보]"],
            "evidence_items": [
                {
                    "source_anchor": "[삼성전자 | 2024 | III. 재무에 관한 사항 > 1. 요약재무정보]",
                    "claim": "2024년 매출액과 영업이익 수치가 제시되어 있다.",
                    "support_level": "direct",
                    "allowed_terms": ["영업이익률", "매출액", "영업이익"],
                }
            ],
            "calculation_operands": [
                {
                    "source_anchor": "[삼성전자 | 2024 | III. 재무에 관한 사항 > 1. 요약재무정보]",
                    "label": "2024년 영업이익",
                    "raw_value": "36,474,516",
                    "raw_unit": "백만원",
                    "normalized_value": 36474516000000.0,
                    "normalized_unit": "KRW",
                    "period": "2024년",
                }
            ],
            "calculation_plan": {"mode": "single_value", "formula": "A / B * 100"},
            "calculation_result": {"status": "ok", "value": 10.9, "result_unit": "%"},
            "reflection_count": 0,
            "retry_reason": "",
            "retrieved_docs": [
                (
                    Document(
                        page_content="dummy",
                        metadata={"chunk_uid": "chunk-001", "section_path": "III. 재무에 관한 사항 > 1. 요약재무정보"},
                    ),
                    0.93,
                )
            ],
        }
        fake = FakeAnalystCore(result=result)
        node = make_run_analyst(fake)

        updates = node(_analyst_state())

        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0]["report_scope"]["company"], "삼성전자")
        self.assertEqual(fake.calls[0]["report_scope"]["year"], "2024")
        self.assertEqual(updates["tasks"]["task_1"]["status"], TaskStatus.COMPLETED)
        artifact = updates["artifacts"]["task_1"]
        self.assertEqual(artifact["creator"], "Analyst")
        self.assertEqual(
            artifact["content"]["answer"],
            "2024년 영업이익률은 10.9%입니다.",
        )
        self.assertIn("chunk-001", artifact["evidence_links"])
        self.assertEqual(len(updates["evidence_pool"]), 2)
        self.assertIn("Analyst completed task_1 successfully", updates["execution_trace"])

    def test_run_analyst_marks_failed_on_incomplete_result(self) -> None:
        fake = FakeAnalystCore(
            result={
                "answer": "",
                "calculation_result": {"status": "insufficient_operands"},
            }
        )
        node = make_run_analyst(fake)

        updates = node(_analyst_state())

        self.assertEqual(updates["tasks"]["task_1"]["status"], TaskStatus.FAILED)
        self.assertEqual(updates["artifacts"], {})
        self.assertIn("Analyst failed task_1: incomplete numeric result", updates["execution_trace"])

    def test_full_graph_can_use_injected_analyst_node(self) -> None:
        fake = FakeAnalystCore(
            result={
                "answer": "2024년 영업이익률은 10.9%입니다.",
                "query_type": "comparison",
                "intent": "comparison",
                "calculation_result": {"status": "ok"},
                "calculation_plan": {"mode": "single_value"},
                "calculation_operands": [],
                "evidence_items": [],
                "citations": ["[삼성전자 | 2024 | III. 재무에 관한 사항 > 1. 요약재무정보]"],
                "retrieved_docs": [],
            }
        )
        analyst_node = make_run_analyst(fake)

        final = run_mas_graph(
            "삼성전자 24년 분석해줘",
            analyst_node=analyst_node,
        )

        self.assertIn("Analyst completed task_1 successfully", final["execution_trace"])
        self.assertIn("Critic passed all artifacts (Deterministic)", final["execution_trace"])
        self.assertTrue(final["final_report"].startswith("매출은 2024년 영업이익률은 10.9%입니다."))
        self.assertEqual(final["tasks"]["task_1"]["status"], TaskStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
