"""No-provider correctness checks for the changed scoring seam."""
import copy
import math
import socket
import unittest

import numpy as np

from run import FixedStatsScorer, prior, stats_hash, validate_saved_row


class FixedStatisticsContract(unittest.TestCase):
    def setUp(self):
        self.tokens = [["a", "a", "b", "c"], ["b", "b", "c"], ["c", "d"], ["d", "e", "e", "e", "e"]]
        self.index = prior.BM25Okapi(self.tokens)

    def test_identical_views_match_existing_library_for_repeated_queries(self):
        scorer = FixedStatsScorer(self.index, self.tokens)
        for query in (["a"], ["a", "b", "a"], ["c", "d"], ["missing"], []):
            np.testing.assert_array_equal(scorer.get_scores(query), self.index.get_scores(query))

    def test_short_row_uses_original_idf_and_avgdl_with_own_length(self):
        scorer = FixedStatsScorer(self.index, [["a", "a"]])
        expected = self.index.idf["a"] * (2 * (self.index.k1 + 1)) / (
            2 + self.index.k1 * (1 - self.index.b + self.index.b * 2 / self.index.avgdl))
        self.assertAlmostEqual(float(scorer.get_scores(["a"])[0]), expected, places=14)

    def test_original_statistics_and_scores_are_immutable(self):
        before = stats_hash(self.index)
        expected = self.index.get_scores(["a", "b"]).copy()
        scorer = FixedStatsScorer(self.index, [["a"]] * 50 + [["brandnew"]])
        scorer.get_scores(["a", "b"])
        scorer.idf["a"] = 999
        self.assertEqual(stats_hash(self.index), before)
        np.testing.assert_array_equal(self.index.get_scores(["a", "b"]), expected)

    def test_new_row_vocabulary_has_zero_weight(self):
        scorer = FixedStatsScorer(self.index, [["brandnew"]])
        self.assertEqual(float(scorer.get_scores(["brandnew"])[0]), 0)

    def test_row_inventory_does_not_change_a_rows_score(self):
        one = FixedStatsScorer(self.index, [["a"]])
        many = FixedStatsScorer(self.index, [["a"], ["b"] * 100, ["a"] * 100])
        self.assertEqual(float(one.get_scores(["a"])[0]), float(many.get_scores(["a"])[0]))

    def test_parent_max_not_sum_and_original_wins_ties(self):
        docs = {"x": {"receipt": "r", "order": 0}, "y": {"receipt": "r", "order": 1}}
        folded = prior.fold_scores([1, 3, 2, 2, 3], ["x", "y", "x", "x", "y"], docs, "r")
        self.assertEqual([(h["uid"], h["score"]) for h in folded], [("y", 3), ("x", 2)])
        self.assertEqual(folded[0]["winning_view_index"], 1)

    def test_scope_and_canonical_tie_order(self):
        docs = {"x": {"receipt": "r", "order": 1}, "y": {"receipt": "r", "order": 0}, "z": {"receipt": "other", "order": 2}}
        folded = prior.fold_scores([2, 2, 100], ["x", "y", "z"], docs, "r")
        self.assertEqual([h["uid"] for h in folded], ["y", "x"])

    def test_saved_row_requires_unchanged_parent_and_search_text(self):
        body = "header\nlabel | 12 | 9\nend"
        raw = "label | 12 | 9"
        row = {"parent_uid": "p", "receipt": "r", "source_document_sha256": "source",
               "parent_text_sha256": prior.text_sha(body), "search_text": "label year 12",
               "search_text_sha256": prior.text_sha("label year 12"),
               "parent_span": [7, 7 + len(raw)], "raw_line": raw}
        docs = {"p": {"receipt": "r", "text": body}}
        validate_saved_row(row, docs, {"r": "source"})
        for key, value in (("source_document_sha256", "wrong"), ("parent_span", [0, 5]),
                           ("search_text", "label year 99"), ("parent_text_sha256", "wrong")):
            broken = copy.deepcopy(row)
            broken[key] = value
            with self.assertRaises(AssertionError):
                validate_saved_row(broken, docs, {"r": "source"})

    def test_network_connections_are_disabled(self):
        with self.assertRaisesRegex(RuntimeError, "network is disabled"):
            socket.create_connection(("example.invalid", 443))


if __name__ == "__main__":
    unittest.main()
