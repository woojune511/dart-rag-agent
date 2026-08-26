import json
import os
import unicodedata
import unittest
from pathlib import Path
from unittest.mock import patch

from src.ops.calibrate_query_router import DEFAULT_EVAL_PATH
from src.routing.query_router import default_canonical_queries_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_EVAL_PATH = PROJECT_ROOT / "benchmarks" / "golden" / "query_routing_eval_v1.json"
EVAL_PATH = PROJECT_ROOT / "benchmarks" / "golden" / "query_routing_eval_v2.json"


def _normalize_query(query: str) -> str:
    normalized = unicodedata.normalize("NFKC", query).casefold()
    return " ".join(normalized.split())


class QueryRoutingDatasetContractTests(unittest.TestCase):
    def test_calibration_uses_versioned_disjoint_eval_dataset(self) -> None:
        self.assertEqual(DEFAULT_EVAL_PATH, EVAL_PATH)
        self.assertTrue(LEGACY_EVAL_PATH.is_file())
        self.assertTrue(EVAL_PATH.is_file())

    def test_v2_changes_only_the_legacy_canonical_overlap(self) -> None:
        legacy_payload = json.loads(LEGACY_EVAL_PATH.read_text(encoding="utf-8"))
        eval_payload = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
        self.assertListEqual(
            [row["query_id"] for row in legacy_payload],
            [row["query_id"] for row in eval_payload],
        )

        changed_rows = [
            (legacy_row, eval_row)
            for legacy_row, eval_row in zip(legacy_payload, eval_payload)
            if legacy_row != eval_row
        ]
        self.assertEqual(len(changed_rows), 1)

        with patch.dict(os.environ, {"QUERY_ROUTING_CANONICAL_PATH": ""}):
            canonical_path = default_canonical_queries_path()
        canonical_payload = json.loads(canonical_path.read_text(encoding="utf-8"))
        canonical_queries = {
            _normalize_query(query)
            for intent_group in canonical_payload
            for query in intent_group.get("queries", [])
            if str(query).strip()
        }
        legacy_row, eval_row = changed_rows[0]
        self.assertIn(_normalize_query(legacy_row["query"]), canonical_queries)
        self.assertNotIn(_normalize_query(eval_row["query"]), canonical_queries)

    def test_default_canonical_path_is_runtime_config_data(self) -> None:
        with patch.dict(os.environ, {"QUERY_ROUTING_CANONICAL_PATH": ""}):
            canonical_path = default_canonical_queries_path()

        self.assertEqual(
            canonical_path,
            PROJECT_ROOT / "src" / "config" / "query_routing_canonical_v1.json",
        )
        self.assertTrue(canonical_path.is_file())
        self.assertTrue(canonical_path.is_relative_to(PROJECT_ROOT / "src" / "config"))

    def test_canonical_path_environment_override_is_preserved(self) -> None:
        override_path = PROJECT_ROOT / "tests" / "fixtures" / "routing_override.json"
        with patch.dict(
            os.environ,
            {"QUERY_ROUTING_CANONICAL_PATH": str(override_path)},
        ):
            canonical_path = default_canonical_queries_path()

        self.assertEqual(canonical_path, override_path.resolve())

    def test_canonical_and_held_out_queries_are_disjoint(self) -> None:
        with patch.dict(os.environ, {"QUERY_ROUTING_CANONICAL_PATH": ""}):
            canonical_path = default_canonical_queries_path()

        canonical_payload = json.loads(canonical_path.read_text(encoding="utf-8"))
        eval_payload = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
        canonical_queries = {
            _normalize_query(query)
            for intent_group in canonical_payload
            for query in intent_group.get("queries", [])
            if str(query).strip()
        }
        eval_queries = {
            _normalize_query(row.get("query", ""))
            for row in eval_payload
            if str(row.get("query", "")).strip()
        }

        self.assertEqual(len(eval_payload), 30)
        self.assertEqual(len(eval_queries), 30)
        self.assertSetEqual(canonical_queries & eval_queries, set())


if __name__ == "__main__":
    unittest.main()
