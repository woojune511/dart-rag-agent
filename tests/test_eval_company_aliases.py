import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.benchmark_runner import _select_eval_examples
from src.ops.evaluator import EvalExample, _compute_retrieval_hit_at_k


class _Doc:
    def __init__(self, metadata):
        self.metadata = metadata


class EvalCompanyAliasTests(unittest.TestCase):
    def test_select_eval_examples_matches_source_report_company_alias(self) -> None:
        dataset = [
            {
                "id": "NAV_T1_071",
                "company": "네이버",
                "year": 2023,
                "question": "질문",
                "ground_truth": "정답",
                "source_report": {
                    "corp_name": "NAVER",
                    "year": 2023,
                    "rcept_no": "20240318000844",
                },
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir) / "dataset.json"
            dataset_path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
            examples = _select_eval_examples(
                {
                    "eval_dataset_path": str(dataset_path),
                    "eval_mode": "question_ids",
                    "question_ids": ["NAV_T1_071"],
                },
                {"company": "NAVER", "year": 2023},
            )
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0].id, "NAV_T1_071")

    def test_all_filtered_eval_limit_zero_selects_all_company_examples(self) -> None:
        dataset = [
            {
                "id": f"NAV_T1_{idx:03d}",
                "company": "네이버",
                "year": 2023,
                "question": "질문",
                "ground_truth": "정답",
            }
            for idx in range(7)
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir) / "dataset.json"
            dataset_path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
            examples = _select_eval_examples(
                {
                    "eval_dataset_path": str(dataset_path),
                    "eval_mode": "all_filtered",
                    "eval_limit": 0,
                },
                {"company": "네이버", "year": 2023},
            )
        self.assertEqual(len(examples), 7)

    def test_retrieval_hit_accepts_company_alias_match(self) -> None:
        example = EvalExample(
            id="NAV_T1_071",
            question="질문",
            ground_truth="정답",
            company="네이버",
            year=2023,
            section="III. 재무에 관한 사항",
            expected_sections=["III. 재무에 관한 사항 > 3. 연결재무제표 주석 > 28. 법인세비용 (연결)"],
            company_aliases=["NAVER"],
        )
        retrieved_docs = [
            (
                _Doc(
                    {
                        "company": "NAVER",
                        "year": 2023,
                        "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석 > 28. 법인세비용 (연결)",
                    }
                ),
                0.99,
            )
        ]
        self.assertEqual(_compute_retrieval_hit_at_k(example, retrieved_docs), 1.0)


if __name__ == "__main__":
    unittest.main()
