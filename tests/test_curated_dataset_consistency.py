import json
import unittest
from pathlib import Path


DATASET_PATH = Path("benchmarks/datasets/single_doc_eval_full.curated.json")
SOURCE_DATASET_PATH = Path("benchmarks/datasets/single_doc_eval_full.json")


class CuratedDatasetConsistencyTest(unittest.TestCase):
    def test_hyu_t3_072_uses_one_complete_consolidated_motional_basis(self) -> None:
        data = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        item = next(row for row in data if row["id"] == "HYU_T3_072")

        required_entities = item["required_entities"]
        evidence_quotes = item["ground_truth_evidence_quotes"]

        for surface in (
            "26%",
            "700,691",
            "영업수익",
            "계속영업손실",
            "기타포괄손익",
            "총포괄손실",
        ):
            self.assertIn(surface, item["answer_key"])
            self.assertIn(surface, item["ground_truth"])
            self.assertIn(surface, required_entities)
        self.assertNotIn("25.81%", item["answer_key"])
        self.assertNotIn("1,294,367", item["answer_key"])
        self.assertIn("26%", evidence_quotes)
        self.assertIn("투자자산 700,691", evidence_quotes)
        self.assertIn("계속영업이익(손실) (803,742)", evidence_quotes)
        self.assertIn("총포괄손익 (791,627)", evidence_quotes)
        self.assertNotIn("총포괄손실 (791,627)", evidence_quotes)
        self.assertTrue(
            all("연결재무제표 주석" in row["section_path"] for row in item["evidence"])
        )

        source_data = json.loads(
            SOURCE_DATASET_PATH.read_text(encoding="utf-8")
        )
        source_item = next(
            row for row in source_data if row["id"] == "HYU_T3_072"
        )
        self.assertEqual(
            source_item["eval_checkpoints"]["required_keywords"],
            [
                "Motional",
                "지분율",
                "투자자산",
                "영업수익",
                "계속영업손실",
                "기타포괄손익",
                "총포괄손실",
            ],
        )


if __name__ == "__main__":
    unittest.main()
