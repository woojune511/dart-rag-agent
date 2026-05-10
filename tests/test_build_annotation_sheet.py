import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.build_annotation_sheet import prepare_annotation_records


class BuildAnnotationSheetTests(unittest.TestCase):
    def test_question_only_taskset_row_becomes_annotation_seed(self) -> None:
        rows = [
            {
                "id": "SAM_T1_001",
                "company": "삼성전자",
                "year": "2023",
                "theme": "1. 수익성",
                "difficulty": "L1",
                "query": "2023년 연결기준 삼성전자의 영업이익률을 계산해 줘.",
                "expected_agents": ["Analyst"],
                "eval_checkpoints": {
                    "required_operands": ["매출액", "영업이익"],
                    "reject_expected": False,
                },
            }
        ]

        records, summary = prepare_annotation_records(rows, source_name="single_doc_eval_full.json")

        self.assertEqual(summary["total_rows"], 1)
        self.assertEqual(summary["question_only_rows"], 1)
        self.assertEqual(summary["with_answer_key"], 0)
        self.assertEqual(len(records), 1)

        record = records[0]
        self.assertEqual(record["question"], "2023년 연결기준 삼성전자의 영업이익률을 계산해 줘.")
        self.assertEqual(record["answer_type"], "numeric")
        self.assertEqual(record["suggested_category"], "multi-hop-calculation")
        self.assertFalse(record["expected_refusal"])
        self.assertEqual(record["annotation_status"], "question_only")
        self.assertEqual(record["missing_fields"], ["answer_key", "expected_sections", "evidence"])
        self.assertEqual(
            [operand["label"] for operand in record["expected_operands"]],
            ["매출액", "영업이익"],
        )
        self.assertIn("expected_agents=Analyst", record["notes"])

    def test_refusal_row_collects_keywords_and_marks_partial(self) -> None:
        rows = [
            {
                "id": "SAM_T4_004",
                "company": "삼성전자",
                "year": "2023",
                "query": "삼성전자의 2023년 영업이익률을 계산하고, 애플(Apple)의 영업이익률과 비교해서 분석해 줘.",
                "expected_agents": ["Analyst", "Critic", "Orchestrator"],
                "eval_checkpoints": {
                    "required_keywords": ["애플", "데이터 없음", "비교 불가"],
                    "reject_expected": True,
                },
                "expected_sections": ["요약재무정보"],
            }
        ]

        records, summary = prepare_annotation_records(rows)

        self.assertEqual(summary["expected_refusal"], 1)
        record = records[0]
        self.assertTrue(record["expected_refusal"])
        self.assertEqual(record["answer_type"], "refusal")
        self.assertEqual(record["suggested_category"], "adversarial-out-of-domain")
        self.assertEqual(record["required_entities"], ["애플", "데이터 없음", "비교 불가"])
        self.assertEqual(record["annotation_status"], "partial")
        self.assertEqual(record["missing_fields"], ["answer_key", "evidence"])


if __name__ == "__main__":
    unittest.main()
