from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.ops.replay_reviewed_runtime_corpus import (
    _replay_case,
    replay_reviewed_runtime_corpus,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "reviewed_runtime_replay_corpus_v1.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class ReviewedRuntimeReplayCorpusTests(unittest.TestCase):
    def test_five_distinct_reviewed_questions_replay_deterministically(self) -> None:
        first = replay_reviewed_runtime_corpus(FIXTURE_PATH)
        second = replay_reviewed_runtime_corpus(FIXTURE_PATH)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "passed")
        self.assertEqual(first["provider_calls"], 0)
        self.assertEqual(first["compiler_calls"], 0)
        self.assertEqual(first["retrieval_calls"], 0)
        self.assertEqual(first["source_store_writes"], 0)
        self.assertEqual(
            first["summary"],
            {
                "case_count": 5,
                "unique_question_count": 5,
                "distinct_question_ids": True,
                "passed_case_count": 5,
                "failed_case_count": 0,
            },
        )
        self.assertEqual(
            {case["question_id"] for case in first["cases"]},
            {
                "KBF_T1_017",
                "KBF_T2_018",
                "LGE_T1_051",
                "NAV_T2_006",
                "CEL_T1_013",
            },
        )
        self.assertTrue(
            all(all(case["checks"].values()) for case in first["cases"])
        )

        by_question = {
            case["question_id"]: case for case in first["cases"]
        }
        kbf_growth = by_question["KBF_T2_018"]
        self.assertEqual(
            [row["normalized_value"] for row in kbf_growth["normalization"][:2]],
            [-3146409000000.0, -1847775000000.0],
        )
        naver_output = next(
            output
            for output in by_question["NAV_T2_006"]["execution"]["outputs"]
            if output["obligation_id"] == "commerce_growth"
        )
        self.assertEqual(naver_output["rendered_value"], "41.4%")
        self.assertAlmostEqual(
            naver_output["calculated_value"],
            41.3913719393704,
        )
        self.assertTrue(naver_output["source_stated_result_used"])

    def test_hidden_requirement_candidate_fails_closed(self) -> None:
        case = deepcopy(_fixture()["cases"][1])
        case["visibility"]["candidate_ids_by_owner"][
            "credit_loss_growth:prior"
        ] = []

        result = _replay_case(case)

        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["checks"]["validation_status_expected"])
        self.assertIn(
            "candidate_not_exposed_to_compiler",
            {row["code"] for row in result["validation"]["errors"]},
        )

    def test_reviewed_normalization_expectation_is_not_trusted_blindly(self) -> None:
        case = deepcopy(_fixture()["cases"][4])
        case["candidate_catalog"][0]["expected_normalized_value"] = 1

        result = _replay_case(case)

        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["checks"]["raw_normalization_matches_review"])
        self.assertEqual(
            result["normalization"][0]["normalized_value"],
            342736271000.0,
        )


if __name__ == "__main__":
    unittest.main()
