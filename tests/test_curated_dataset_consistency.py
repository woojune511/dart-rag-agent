import json
import unittest
from pathlib import Path


DATASET_PATH = Path("benchmarks/datasets/single_doc_eval_full.curated.json")


class CuratedDatasetConsistencyTest(unittest.TestCase):
    def test_hyu_t3_072_uses_year_end_motional_ownership_entity(self) -> None:
        data = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        item = next(row for row in data if row["id"] == "HYU_T3_072")

        required_entities = item["required_entities"]
        evidence_quotes = item["ground_truth_evidence_quotes"]

        self.assertIn("25.81%", item["answer_key"])
        self.assertIn("25.81%", item["ground_truth"])
        self.assertIn("25.81%", required_entities)
        self.assertNotIn("25.92%", required_entities)
        self.assertIn("25.81%", evidence_quotes)
        self.assertNotIn("25.92%", evidence_quotes)


if __name__ == "__main__":
    unittest.main()
