from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from src.ops.replay_reviewed_runtime_corpus import (
    _replay_case as _replay_current_case,
    replay_reviewed_runtime_corpus,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "reviewed_runtime_replay_corpus_v2.json"
)
PREDECESSOR_PATH = FIXTURE_PATH.with_name("reviewed_runtime_replay_corpus_v1.json")
PREDECESSOR_SHA256 = "2af019ff9d3163038bb8bd190edb88996b229b47ac88700d15d1e6068b77bb33"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _replay_case(case):
    from tests.request_unit_fixture_support import bind_fixture_request
    return _replay_current_case(bind_fixture_request(case))


class ReviewedRuntimeReplayCorpusTests(unittest.TestCase):
    def setUp(self) -> None:
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
            self.enterContext(patch(target, side_effect=AssertionError("provider-free fixture test")))

    def test_five_distinct_reviewed_questions_replay_deterministically(self) -> None:
        from tests.request_unit_fixture_support import request_bound_fixture
        authored = request_bound_fixture(self, FIXTURE_PATH)
        first = replay_reviewed_runtime_corpus(authored)
        second = replay_reviewed_runtime_corpus(authored)

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

    def test_commerce_absolute_amounts_match_reviewed_source(self) -> None:
        case = next(
            row for row in _fixture()["cases"]
            if row["question_id"] == "NAV_T2_006"
        )
        result = _replay_case(case)
        amounts = {
            row["candidate_id"]: row["normalized_value"]
            for row in result["normalization"]
        }
        # Independently reviewed amounts: the adjacent filing unit is 십억원.
        self.assertEqual(amounts["reviewed_naver_commerce_2023"], 2546600000000)
        self.assertEqual(amounts["reviewed_naver_commerce_2022"], 1801100000000)
        outputs = {
            row["obligation_id"]: row for row in result["execution"]["outputs"]
        }
        for obligation, amount, rendered in (
            ("commerce_2023", 2546600000000, "2,546.6십억원"),
            ("commerce_2022", 1801100000000, "1,801.1십억원"),
        ):
            with self.subTest(obligation=obligation):
                self.assertEqual(outputs[obligation]["normalized_value"], amount)
                self.assertEqual(outputs[obligation]["normalized_unit"], "KRW")
                self.assertEqual(outputs[obligation]["rendered_value"], rendered)
        self.assertEqual(
            [(row["source_id"], row["normalized_value"], row["raw_unit"])
             for row in outputs["commerce_growth"]["input_rows"]],
            [("commerce_2023", 2546600000000, "십억원"),
             ("commerce_2022", 1801100000000, "십억원")],
        )
        self.assertEqual(result["status"], "passed")

    def test_unit_and_values_keep_the_exact_adjacent_source_tables(self) -> None:
        case = next(row for row in _fixture()["cases"] if row["question_id"] == "NAV_T2_006")
        review = case["review"]["source_unit_review"]
        excerpt_bytes = review["source_excerpt"].encode("utf-8")
        self.assertEqual(hashlib.sha256(excerpt_bytes).hexdigest(), review["source_excerpt_sha256"])
        self.assertEqual(len(excerpt_bytes), review["utf8_byte_end"] - review["utf8_byte_start"])
        # This bounded original fragment parses strictly; no recovered full-document XPath.
        source = ElementTree.fromstring("<source>" + review["source_excerpt"] + "</source>")
        self.assertEqual([child.tag for child in source], ["TABLE", "TABLE"])
        self.assertEqual(source.findtext(review["unit_xpath"]), "(단위: 십억원)")
        self.assertEqual(
            [node.text for node in source.find(review["header_xpath"]).iter("TH")],
            ["사업부문", "연결", "제25기", "제24기", "증(감)률", "매출비중"],
        )
        row_cells = [node.text for node in source.find(review["row_xpath"])]
        self.assertEqual(row_cells, ["커머스", "2,546.6", "1,801.1", "41.4%", "26.4%"])
        for candidate, column in zip(case["candidate_catalog"][:3], ("제25기", "제24기", "증(감)률")):
            with self.subTest(candidate=candidate["candidate_id"]):
                value = source.findtext(review["value_xpaths"][candidate["candidate_id"]])
                self.assertEqual(candidate["raw_value"], value)
                self.assertEqual(candidate["row_label"], row_cells[0])
                self.assertEqual(candidate["column_headers"], ["연결", column])
                self.assertNotIn(" / 억원", candidate["source_text"])
                if column != "증(감)률":
                    self.assertEqual(candidate["raw_unit"], "십억원")
                    self.assertEqual(
                        candidate["expected_normalized_value"],
                        Decimal(value.replace(",", "")) * 1000000000,
                    )

    def test_common_scale_error_is_rejected_even_when_growth_still_matches(self) -> None:
        case = deepcopy(next(row for row in _fixture()["cases"] if row["question_id"] == "NAV_T2_006"))
        for candidate in case["candidate_catalog"][:2]:
            candidate["raw_unit"] = "억원"
            candidate["expected_normalized_value"] /= 10
        for candidate in case["candidate_catalog"][:3]:
            candidate["source_text"] = candidate["source_text"].replace("십억원", "억원")

        result = _replay_case(case)

        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["checks"]["raw_normalization_matches_review"])
        self.assertTrue(result["checks"]["validation_status_expected"])
        self.assertFalse(result["checks"]["expected_outputs_match"])
        checks = {row["obligation_id"]: row for row in result["output_checks"]}
        self.assertTrue(checks["commerce_growth"]["matches"])
        for obligation in ("commerce_2023", "commerce_2022"):
            self.assertIn("normalized_value", checks[obligation]["mismatch_fields"])
            self.assertIn("rendered_value", checks[obligation]["mismatch_fields"])

    def test_successor_preserves_predecessor_and_unrelated_contracts(self) -> None:
        old_bytes = PREDECESSOR_PATH.read_bytes()
        # Pin the Git LF content, allowing only checkout newline translation.
        self.assertEqual(
            hashlib.sha256(old_bytes.replace(b"\r\n", b"\n")).hexdigest(),
            PREDECESSOR_SHA256,
        )
        old = json.loads(old_bytes)
        current = _fixture()
        self.assertEqual(current["corpus_revision"], 2)
        self.assertEqual(current["predecessor"]["sha256"], PREDECESSOR_SHA256)
        self.assertEqual(current["schema_version"], old["schema_version"])
        for before, after in zip(old["cases"], current["cases"], strict=True):
            if before["question_id"] != "NAV_T2_006":
                self.assertEqual(before, after)
                continue
            for field in ("question", "obligations", "visibility", "program"):
                self.assertEqual(before[field], after[field])
            self.assertEqual(before["expected"]["selected_candidate_ids"], after["expected"]["selected_candidate_ids"])
            self.assertEqual(before["expected"]["outputs"], after["expected"]["outputs"][2:])
            for old_candidate, new_candidate in zip(before["candidate_catalog"], after["candidate_catalog"], strict=True):
                allowed = {"raw_unit", "source_text", "expected_normalized_value"}
                self.assertEqual(
                    {key: value for key, value in old_candidate.items() if key not in allowed},
                    {key: value for key, value in new_candidate.items() if key not in allowed},
                )
        self.assertEqual(PREDECESSOR_PATH.read_bytes(), old_bytes)

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
