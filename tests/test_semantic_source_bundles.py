from __future__ import annotations

import unittest

from src.agent.financial_reconciliation_candidates import (
    _numeric_source_bundle_projections,
    build_semantic_candidate_catalog,
    semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_source_bundles import (
    SOURCE_BUNDLE_SCHEMA_VERSION,
    build_semantic_source_bundles,
    semantic_source_bundle_fingerprint,
    source_bundle_id_by_candidate_id,
)


class SemanticSourceBundleTests(unittest.TestCase):
    def test_long_sentence_neighbor_values_share_window_without_identity_changes(self) -> None:
        text = (
            "x " * 180
            + "current 120% and prior 100% and expected 140% "
            + "tail " * 130
        )
        catalog = build_semantic_candidate_catalog(
            [{
                "candidate_id": "chunk-long",
                "source_anchor": "[sample]",
                "candidate_kind": "chunk",
                "text": text,
                "metadata": {"is_table": False},
            }]
        )
        numeric = [row for row in catalog if row["kind"] == "numeric"]
        self.assertEqual(
            [row["candidate_id"] for row in numeric],
            [
                "cand_81380f7ff4c52b71cdcd",
                "cand_372fc8374a01f2400b75",
                "cand_3c5071eb5d2e9960a341",
            ],
        )
        self.assertEqual(
            semantic_candidate_catalog_fingerprint(catalog),
            "4c80cb5c982a8ff0c10ff37bc3c7233f5a49dede1a7cb5b5f95763abdda619f8",
        )
        bundles = build_semantic_source_bundles(numeric)
        self.assertEqual(len(bundles), 1)
        bundle = bundles[0]
        self.assertLessEqual(len(bundle.source_text), 420)
        self.assertEqual(len(bundle.candidate_ids), 3)
        self.assertEqual(
            {tuple(row["source_bundle_context_span"]) for row in numeric},
            {tuple(numeric[0]["source_bundle_context_span"])},
        )
        for row in numeric:
            start, end = bundle.value_span_by_candidate_id()[row["candidate_id"]]
            self.assertEqual(bundle.source_text[start:end], row["raw_value"] + "%")

    def test_multiple_exact_windows_keep_each_value_in_one_bundle(self) -> None:
        exact = (
            "context " * 50
            + "current (120) 백만원\t  and prior (100) 백만원 "
            + "intervening " * 50
            + "later (140) 백만원\t  and following (130) 백만원 "
            + "tail " * 100
        )
        source = {
            "candidate_id": "chunk-separated",
            "source_anchor": "[sample]",
            "candidate_kind": "chunk",
            "text": " ".join(exact.split()),
            "source_text_exact": exact,
            "metadata": {"is_table": False},
        }
        catalog = build_semantic_candidate_catalog([source])
        numeric = [row for row in catalog if row["kind"] == "numeric"]
        bundles = build_semantic_source_bundles(numeric)
        self.assertEqual(len(numeric), 4)
        self.assertEqual(sorted(len(bundle.candidate_ids) for bundle in bundles), [2, 2])
        self.assertEqual(
            sum(len(bundle.candidate_ids) for bundle in bundles),
            len(source_bundle_id_by_candidate_id(bundles)),
        )
        for bundle in bundles:
            self.assertLessEqual(len(bundle.source_text), 420)
            self.assertIn(bundle.source_text, exact)
            self.assertIn("\t  ", bundle.source_text)
        for row in numeric:
            start, end = row["source_bundle_context_span"]
            value_start, value_end = row["source_bundle_value_span"]
            self.assertEqual(row["source_bundle_text"], exact[start:end])
            self.assertEqual(
                row["source_bundle_text"][value_start:value_end],
                row["raw_value"] + " 백만원",
            )
            for other in numeric:
                if other["source_bundle_context_span"] == [start, end]:
                    continue
                other_start = (
                    other["source_bundle_context_span"][0]
                    + other["source_bundle_value_span"][0]
                )
                other_end = (
                    other["source_bundle_context_span"][0]
                    + other["source_bundle_value_span"][1]
                )
                self.assertTrue(other_end <= start or other_start >= end)
        self.assertEqual(bundles, build_semantic_source_bundles(list(reversed(numeric))))
        spans = [row["source_span"] for row in numeric]
        forward = _numeric_source_bundle_projections(
            source["text"], exact, spans, max_chars=420
        )
        reverse = _numeric_source_bundle_projections(
            source["text"], exact, list(reversed(spans)), max_chars=420
        )
        self.assertEqual(forward, list(reversed(reverse)))

    def test_sentence_boundaries_remain_separate_and_numeric_spans_are_not_cut(self) -> None:
        text = "First 120%. Second 100%."
        spans = [[6, 10], [19, 23]]
        projected = _numeric_source_bundle_projections(text, text, spans, max_chars=420)
        self.assertEqual(
            [row["source_bundle_text"] for row in projected],
            ["First 120%.", " Second 100%."],
        )
        with self.assertRaisesRegex(ValueError, "source span exceeds"):
            _numeric_source_bundle_projections(
                "123456789", "123456789", [[0, 9]], max_chars=8
            )

    def test_prose_bundle_preserves_exact_period_and_parenthesis_context(self) -> None:
        canonical = (
            "당기 신용손실충당금전입액은 (3,146,409) 백만원이며, "
            "전기 신용손실충당금전입액은 (1,847,775) 백만원이다."
        )
        exact = canonical.replace("이며, 전기", "이며,\t  전기")
        catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "chunk-period",
                    "source_anchor": "[sample]",
                    "text": canonical,
                    "source_text_exact": exact,
                    "candidate_kind": "chunk",
                    "metadata": {"is_table": False, "year": 2023},
                }
            ]
        )

        self.assertEqual(
            [row["candidate_id"] for row in catalog if row["kind"] == "numeric"],
            ["cand_53ce4874e0d800448a0d", "cand_d4ff8342754a166dd11d"],
        )
        self.assertEqual(
            semantic_candidate_catalog_fingerprint(catalog),
            "ba6676c2c93bc73ef763cee34e1ddc44f7571e1b48b801bd2d68d4654b0f27cb",
        )

        bundles = build_semantic_source_bundles(catalog)
        self.assertEqual(len(bundles), 1)
        bundle = bundles[0]
        self.assertEqual(bundle.schema_version, SOURCE_BUNDLE_SCHEMA_VERSION)
        self.assertEqual(bundle.source_kind, "prose_sentence")
        self.assertEqual(bundle.source_text, exact)
        self.assertIn("\t  전기", bundle.source_text)
        spans = bundle.value_span_by_candidate_id()
        for candidate_id, expected_surface in (
            ("cand_53ce4874e0d800448a0d", "(3,146,409) 백만원"),
            ("cand_d4ff8342754a166dd11d", "(1,847,775) 백만원"),
        ):
            start, end = spans[candidate_id]
            self.assertEqual(bundle.source_text[start:end], expected_surface)

    def test_bundle_identity_and_fingerprint_ignore_catalog_order(self) -> None:
        catalog = [
            {
                "candidate_id": "cand-current",
                "kind": "numeric",
                "candidate_kind": "sentence_value",
                "source_candidate_id": "source-periods",
                "source_anchor": "[sample]",
                "context_fingerprint": "source-periods|||",
                "source_bundle_text": "current 120 and prior 100",
                "source_bundle_context_span": [0, 25],
                "source_bundle_value_span": [8, 11],
                "raw_value": "120",
            },
            {
                "candidate_id": "cand-prior",
                "kind": "numeric",
                "candidate_kind": "sentence_value",
                "source_candidate_id": "source-periods",
                "source_anchor": "[sample]",
                "context_fingerprint": "source-periods|||",
                "source_bundle_text": "current 120 and prior 100",
                "source_bundle_context_span": [0, 25],
                "source_bundle_value_span": [22, 25],
                "raw_value": "100",
            },
        ]

        forward = build_semantic_source_bundles(catalog)
        reverse = build_semantic_source_bundles(list(reversed(catalog)))
        self.assertEqual(forward, reverse)
        self.assertEqual(
            semantic_source_bundle_fingerprint(forward),
            semantic_source_bundle_fingerprint(reverse),
        )
        self.assertEqual(
            source_bundle_id_by_candidate_id(forward),
            source_bundle_id_by_candidate_id(reverse),
        )

    def test_table_cells_share_one_physical_row_bundle(self) -> None:
        catalog = [
            {
                "candidate_id": "cand-2023",
                "kind": "numeric",
                "candidate_kind": "structured_value",
                "source_anchor": "[sample table]",
                "context_fingerprint": "table-a|||",
                "physical_table_id": "table-a",
                "physical_row_id": "row-profit",
                "source_bundle_text": "영업이익 | 2023 | 2,163,234 | 2022 | 3,551,000",
                "raw_value": "2,163,234",
            },
            {
                "candidate_id": "cand-2022",
                "kind": "numeric",
                "candidate_kind": "structured_value",
                "source_anchor": "[sample table]",
                "context_fingerprint": "table-a|||",
                "physical_table_id": "table-a",
                "physical_row_id": "row-profit",
                "source_bundle_text": "영업이익 | 2023 | 2,163,234 | 2022 | 3,551,000",
                "raw_value": "3,551,000",
            },
        ]

        bundles = build_semantic_source_bundles(catalog)
        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0].source_kind, "table_row")
        self.assertEqual(bundles[0].physical_table_id, "table-a")
        self.assertEqual(bundles[0].physical_row_id, "row-profit")
        self.assertEqual(
            set(bundles[0].candidate_ids),
            {"cand-2023", "cand-2022"},
        )

    def test_table_link_alone_does_not_turn_a_sentence_value_into_a_table_row(self) -> None:
        bundles = build_semantic_source_bundles(
            [
                {
                    "candidate_id": "cand-prose-near-table",
                    "kind": "numeric",
                    "candidate_kind": "sentence_value",
                    "source_candidate_id": "source-near-table",
                    "source_anchor": "[sample note]",
                    "context_fingerprint": "table-a|unknown||",
                    "table_source_id": "table-a",
                    "source_bundle_text": "The note reports a growth rate of 11.5%.",
                    "source_bundle_context_span": [0, 39],
                    "source_bundle_value_span": [34, 39],
                    "raw_value": "11.5",
                    "raw_unit": "%",
                }
            ]
        )

        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0].source_kind, "prose_sentence")
        self.assertEqual(bundles[0].physical_table_id, "")
        self.assertEqual(bundles[0].physical_row_id, "")


if __name__ == "__main__":
    unittest.main()
