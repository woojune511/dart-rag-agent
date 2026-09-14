"""Exact selected-range feedback, not source search, quote repair or model accuracy."""

from copy import deepcopy
import socket
import unittest
from unittest.mock import patch

from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_evidence_addresses import build_narrative_address_book, resolve_narrative_selection
from src.agent.financial_graph_calculation import _semantic_candidate_visibility
from src.agent.financial_narrative_claims import project_narrative_retry_drafts
from tests.narrative_address_test_support import selection
from tests.semantic_program_test_support import _obligation
from tests.test_narrative_claim_grounding import source
from tests.test_narrative_subject_range_boundaries import BOUNDARY_SUBJECTS, canonical, fixture, truncated_subject


class NarrativeSubjectRetryDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        for name in ("connect", "connect_ex"):
            blocked = patch.object(socket.socket, name, side_effect=AssertionError("Provider-free test"))
            blocked.start()
            self.addCleanup(blocked.stop)
        self.owners = [_obligation("activity", "narrative", "Inspection activity")]
        self.catalog, good = fixture(BOUNDARY_SUBJECTS["abbreviation"])
        self.program = truncated_subject(good)

    def project(self, *, program=None, catalog=None, selectable=None, errors=None):
        program = self.program if program is None else program
        catalog = self.catalog if catalog is None else catalog
        selectable = {"activity": ["note"]} if selectable is None else selectable
        if errors is None:
            visibility = _semantic_candidate_visibility(catalog,
                visible_candidate_ids=[row["candidate_id"] for row in catalog],
                candidate_ids_by_owner=selectable)
            errors = validate_semantic_calculation_program(program=program, candidate_catalog=catalog,
                obligations=self.owners, query="Describe inspection activity.",
                candidate_visibility=visibility, require_narrative_claims=True)["errors"]
        return project_narrative_retry_drafts(program, obligations=self.owners,
            target_obligation_ids=["activity"], candidate_ids_by_owner=selectable,
            visible_catalog=catalog, validation_errors=errors)

    def test_failed_subject_contrasts_exact_selected_text_for_ten_anonymous_boundaries(self):
        for name, subject in BOUNDARY_SUBJECTS.items():
            with self.subTest(boundary=name):
                catalog, good = fixture(subject)
                bad = truncated_subject(good)
                before = canonical((catalog, bad))
                projected = self.project(program=bad, catalog=catalog)
                draft = projected[0]["subject_bindings"][0]
                check = draft["source_selection_check"]
                self.assertEqual(draft["location"], "subject_bindings[0]")
                self.assertEqual(check["declared_subject"], subject)
                self.assertEqual(len(check["selections"]), 1)
                row = check["selections"][0]
                link = bad["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"][0]
                surface, quote, span = resolve_narrative_selection(link, build_narrative_address_book(catalog))
                for key in ("candidate_id", "source_requirement_id", "surface_id", "first_piece_id", "last_piece_id"):
                    self.assertEqual(row[key], link[key])
                self.assertEqual(row["selected_text"].encode("utf-8"), quote.encode("utf-8"))
                self.assertEqual(row["source_span"], list(span))
                self.assertEqual(row["source_field"], surface.source_field)
                self.assertFalse(row["contains_declared_subject"])
                self.assertNotIn(subject, row["selected_text"])
                self.assertEqual(canonical((catalog, bad)), before)
                self.assertEqual(projected, self.project(program=bad, catalog=list(reversed(catalog))))

    def test_only_exact_structured_subject_error_locations_enable_diagnostics(self):
        other_errors = [
            {"code": "ungrounded_narrative_claim_number", "obligation_id": "activity", "location": "subject_bindings[0]"},
            {"code": "ungrounded_narrative_subject", "obligation_id": "accepted", "location": "subject_bindings[0]"},
            {"code": "ungrounded_narrative_subject", "obligation_id": "activity", "location": "subject_bindings[1]",
             "detail": "subject_bindings[0] is mentioned in prose, not an error address"},
        ]
        for errors in ([], other_errors):
            with patch("src.agent.financial_narrative_claims.build_narrative_address_book") as build:
                drafts = self.project(errors=errors)
                self.assertNotIn("source_selection_check", drafts[0]["subject_bindings"][0])
                build.assert_not_called()
        catalog, good = fixture(BOUNDARY_SUBJECTS["abbreviation"])
        self.assertNotIn("source_selection_check", self.project(program=good, catalog=catalog)[0]["subject_bindings"][0])

    def test_checks_use_only_current_owner_and_requirement_permitted_links(self):
        self.owners[0]["evidence_requirements"] = [{"requirement_id": "activity:a"}, {"requirement_id": "activity:b"}]
        catalog = [*self.catalog, *[source(key, f"{key} private source.", source_document_id=key)
            for key in ("b", "req-only", "excluded", "hidden", "foreign")]]
        program = deepcopy(self.program)
        subject = program["narrative_bindings"][0]["subject_bindings"][0]
        permitted = subject["evidence_selections"][0]
        links = [permitted, {**permitted, "source_requirement_id": "activity:a"},
            {**selection(catalog, "b", "b private source."), "source_requirement_id": "activity:a"},
            {**permitted, "source_requirement_id": "foreign:r"},
            {**selection(catalog, "req-only", "req-only private source."), "source_requirement_id": "activity:a"},
            *[selection(catalog, key, f"{key} private source.") for key in ("excluded", "hidden", "foreign")],
            {**permitted, "candidate_id": "invented"}]
        subject["evidence_selections"] = links
        selectable = {"activity": ["note", "b"], "activity:a": ["note", "req-only"],
            "activity:b": ["b"], "foreign:r": ["note"]}
        errors = [{"code": "ungrounded_narrative_subject", "obligation_id": "activity", "location": "subject_bindings[0]"}]
        draft = self.project(program=program, catalog=catalog, selectable=selectable, errors=errors)[0]["subject_bindings"][0]
        self.assertEqual(draft["evidence_selections"], links[:2])
        self.assertEqual(draft["omitted_evidence_binding_count"], 7)
        self.assertEqual([row["candidate_id"] for row in draft["source_selection_check"]["selections"]], ["note", "note"])
        self.assertNotIn("private source", canonical(draft).decode())
        self.assertEqual(draft, self.project(program=program, catalog=list(reversed(catalog)),
            selectable=selectable, errors=list(reversed(errors)))[0]["subject_bindings"][0])
        omitted = self.project(program=program, catalog=catalog, selectable={}, errors=errors)[0]["subject_bindings"][0]
        self.assertEqual(omitted["source_selection_check"]["selections"], [])
        not_visible = self.project(program=program, catalog=[], selectable=selectable, errors=errors)[0]["subject_bindings"][0]
        self.assertTrue(all(row["resolution_error"] == "unknown_narrative_surface"
            and "selected_text" not in row for row in not_visible["source_selection_check"]["selections"]))

    def test_invalid_addresses_report_only_resolution_error_never_nearby_source(self):
        for overrides, code in (({"surface_id": "stale"}, "unknown_narrative_surface"),
            ({"last_piece_id": "invented"}, "unknown_narrative_piece"),
            ({"first_piece_id": "p2", "last_piece_id": "p1"}, "reversed_narrative_selection")):
            with self.subTest(code=code):
                bad = deepcopy(self.program)
                bad["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"][0].update(overrides)
                check = self.project(program=bad)[0]["subject_bindings"][0]["source_selection_check"]["selections"][0]
                self.assertEqual(check["resolution_error"], code)
                self.assertNotIn("selected_text", check)
                self.assertNotIn("contains_declared_subject", check)

    def test_diagnostic_does_not_join_pieces_or_bridge_cells(self):
        catalog, good = fixture(BOUNDARY_SUBJECTS["abbreviation"])
        full = good["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"][0]
        good["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"] = [
            {**full, "last_piece_id": full["first_piece_id"]}, {**full, "first_piece_id": full["last_piece_id"]}]
        checks = self.project(program=good, catalog=catalog)[0]["subject_bindings"][0]["source_selection_check"]["selections"]
        self.assertEqual(len(checks), 2)
        self.assertTrue(all(not row["contains_declared_subject"] for row in checks))
        subject = BOUNDARY_SUBJECTS["abbreviation"]
        body = subject + " records inspections."
        boundary = body.index(" and")
        catalog, crossing = fixture(subject, source_overrides={"source_context_provenance": {
            "source_text": body, "source_segments": [{"text_span": [0, boundary], "cell_locator": "left"},
                {"text_span": [boundary, len(body)], "cell_locator": "right"}]}})
        row = self.project(program=crossing, catalog=catalog)[0]["subject_bindings"][0]["source_selection_check"]["selections"][0]
        self.assertEqual(row["resolution_error"], "cross_partition_narrative_selection")
        self.assertNotIn("selected_text", row)

    def test_attached_context_is_exact_and_cannot_be_borrowed_from_another_candidate(self):
        context = {"context_id": "heading", "relation": "ancestor_heading",
            "source_text": "Maple\r\n\r\nWorkshop", "source_span": [10, 27]}
        catalog = [source("note", "It records inspections.", source_contexts=[context]),
            source("other", "Unrelated source.", source_contexts=[{**context,
                "context_id": "other-heading", "source_text": "Not this candidate's context."}])]
        program = deepcopy(self.program)
        binding = program["narrative_bindings"][0]
        for field in ("text", "candidate_ids", "evidence_bindings"):
            binding.pop(field)
        subject = binding["subject_bindings"][0]
        subject["subject"] = "Maple Workshop"
        subject["evidence_selections"] = [selection(catalog, "note", context["source_text"], context_id="heading")]
        # A stored error may describe the predecessor validator. Reproject the
        # same permitted selections without rewriting its model statement.
        errors = [{"code": "ungrounded_narrative_subject", "obligation_id": "activity", "location": "subject_bindings[0]"}]
        check = self.project(program=program, catalog=catalog, errors=errors)[0]["subject_bindings"][0]["source_selection_check"]
        row = check["selections"][0]
        self.assertEqual(row["source_field"], "source_context")
        self.assertEqual(row["selected_text"], context["source_text"])
        self.assertFalse(row["contains_declared_subject"])
        self.assertEqual(check["subject_grounding"]["match_kind"], "whitespace_layout")
        self.assertEqual(check["subject_grounding"]["source_subject"], context["source_text"])
        foreign = selection(catalog, "other", "Not this candidate's context.", context_id="other-heading")
        subject["evidence_selections"] = [{**foreign, "candidate_id": "note"}]
        row = self.project(program=program, catalog=catalog)[0]["subject_bindings"][0]["source_selection_check"]["selections"][0]
        self.assertEqual(row["resolution_error"], "unknown_narrative_surface")
        self.assertNotIn("selected_text", row)

    def test_projection_is_an_owned_copy_not_program_or_source_mutation(self):
        before = deepcopy((self.program, self.catalog, self.owners))
        draft = self.project()[0]["subject_bindings"][0]
        draft["source_selection_check"]["declared_subject"] = "Changed label"
        row = draft["source_selection_check"]["selections"][0]
        row["selected_text"] = "Changed source"
        row["source_span"][0] = 999
        draft["evidence_selections"][0]["last_piece_id"] = "p99"
        self.assertEqual((self.program, self.catalog, self.owners), before)


if __name__ == "__main__":
    unittest.main()
