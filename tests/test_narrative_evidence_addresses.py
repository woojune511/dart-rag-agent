"""Provider-free lossless addressing controls, independent of model semantics."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import unittest

from src.agent.financial_evidence_addresses import (
    MAX_PIECE_CHARACTERS, build_evidence_surface, build_narrative_address_book,
    resolve_narrative_selection,
)
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint
from tests.test_narrative_claim_grounding import source


class NarrativeEvidenceAddressTests(unittest.TestCase):
    def test_lossless_multilingual_line_punctuation_and_long_text(self):
        for text in ("  Alpha acts.\r\nIt reports!  ", "주체는 검사한다. 다음 작업이다.\n",
                     "主体が検査する。 記録する。", "-Purpose: inspect.-Schedule: weekly.",
                     "가" * 601, "word " * 201, "   ", ""):
            with self.subTest(text=text[:30]):
                surface = build_evidence_surface({"source_bundle_id": "body", "source_text": text})
                parts = surface.to_projection()["pieces"]
                self.assertEqual("".join(p["text"] for p in parts), text)
                self.assertTrue(all(p.end - p.start <= MAX_PIECE_CHARACTERS for p in surface.pieces))
                if text.strip():
                    quote, span = surface.resolve(parts[0]["piece_id"], parts[-1]["piece_id"])
                    self.assertEqual((quote, span), (text, (0, len(text))))

    def test_addresses_disambiguate_repeated_occurrences(self):
        surface = build_evidence_surface({"source_bundle_id": "body", "source_text": "Same. Same."})
        self.assertEqual(surface.resolve("p1", "p1"), ("Same. ", (0, 6)))
        self.assertEqual(surface.resolve("p2", "p2"), ("Same.", (6, 11)))

    def test_physical_partitions_cannot_be_joined(self):
        surface = build_evidence_surface({"source_bundle_id": "row", "source_text": "leftright",
            "source_segments": [{"text_span": [0, 4], "cell_locator": "c1"},
                                {"text_span": [4, 9], "cell_locator": "c2"}]})
        self.assertEqual(surface.resolve("p2", "p2")[0], "right")
        with self.assertRaisesRegex(ValueError, "cross_partition"):
            surface.resolve("p1", "p2")

    def test_partition_gaps_do_not_become_visible_source(self):
        surface = build_evidence_surface({"source_bundle_id": "row", "source_text": "aSECRETb",
            "source_segments": [{"text_span": [0, 1]}, {"text_span": [7, 8]}]})
        self.assertNotIn("SECRET", str(surface.to_projection()))
        with self.assertRaisesRegex(ValueError, "cross_partition"):
            surface.resolve("p1", "p2")

    def test_invalid_reversed_and_empty_selections_fail(self):
        surface = build_evidence_surface({"source_bundle_id": "body", "source_text": "A. B."})
        for first, last in (("p0", "p1"), ("p1", "invented"), ("p2", "p1")):
            with self.assertRaises(ValueError):
                surface.resolve(first, last)
        with self.assertRaisesRegex(ValueError, "empty_narrative"):
            build_evidence_surface({"source_text": " "}).resolve("p1", "p1")

    def test_contents_provenance_and_partitions_bind_identity(self):
        original = {"source_bundle_id": "row", "source_text": "Alpha acts.", "physical_row_id": "r1"}
        surface = build_evidence_surface(original)
        for override in ({"source_text": "Alpha acts!"}, {"physical_row_id": "r2"},
                         {"source_segments": [{"text_span": [0, 5]}, {"text_span": [5, 11]}]}):
            self.assertNotEqual(surface.surface_id, build_evidence_surface({**original, **override}).surface_id)
        self.assertEqual(surface.surface_id,
            build_evidence_surface({**original, "candidate_ids": ["new-visible-member"]}).surface_id)

    def test_frozen_copied_surface_and_projection(self):
        original = {"source_bundle_id": "body", "source_text": "Alpha acts."}
        surface = build_evidence_surface(original)
        original["source_text"] = "changed"
        surface.to_projection()["pieces"][0]["text"] = "changed"
        self.assertEqual(surface.resolve("p1", "p1")[0], "Alpha acts.")
        with self.assertRaises(FrozenInstanceError):
            surface.source_text = "changed"

    def test_catalog_order_and_identity_stay_unchanged(self):
        catalog = [source("a", "Alpha acts."), source("b", "Beta acts.")]
        before = deepcopy(catalog)
        fingerprint = semantic_candidate_catalog_fingerprint(catalog)
        self.assertEqual(build_narrative_address_book(catalog), build_narrative_address_book(catalog[::-1]))
        self.assertEqual(catalog, before)
        self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)

    def test_hidden_candidate_or_foreign_attached_context_has_no_address(self):
        catalog = [source("a", "Alpha acts."), source("b", "Beta acts.")]
        catalog[1]["source_contexts"] = [{"context_id": "heading", "source_text": "Beta"}]
        book = build_narrative_address_book(catalog)
        selection = {"candidate_id": "b", "surface_id": book["b"][1].surface_id,
            "first_piece_id": "p1", "last_piece_id": "p1"}
        self.assertEqual(resolve_narrative_selection(selection, book)[1], "Beta")
        with self.assertRaisesRegex(ValueError, "unknown_narrative_surface"):
            resolve_narrative_selection({**selection, "candidate_id": "a"}, book)
        with self.assertRaisesRegex(ValueError, "unknown_narrative_surface"):
            resolve_narrative_selection(selection, build_narrative_address_book(catalog[:1]))

    def test_stale_source_selection_is_not_repaired(self):
        catalog = [source("a", "Alpha acts.")]
        book = build_narrative_address_book(catalog)
        selection = {"candidate_id": "a", "surface_id": book["a"][0].surface_id,
            "first_piece_id": "p1", "last_piece_id": "p1"}
        changed = [source("a", "Alpha acts!",)]
        with self.assertRaisesRegex(ValueError, "unknown_narrative_surface"):
            resolve_narrative_selection(selection, build_narrative_address_book(changed))


if __name__ == "__main__":
    unittest.main()
