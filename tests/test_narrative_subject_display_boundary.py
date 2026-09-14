"""Characterize display/source asymmetry without changing runtime authority."""

from copy import deepcopy
import socket
import unittest
from unittest.mock import patch

from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_graph_calculation import _semantic_candidate_visibility
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_narrative_claims import validate_narrative_claims
from src.agent.financial_program_projection import render_narrative_claim
from tests.semantic_program_test_support import _obligation
from tests.test_narrative_subject_range_boundaries import fixture


def changed_subject(program, subject):
    result = deepcopy(program)
    binding = result["narrative_bindings"][0]
    binding["subject_bindings"][0]["subject"] = subject
    for key in ("candidate_ids", "evidence_bindings", "text"):
        binding.pop(key, None)
    return SemanticCalculationProgram.model_validate(result).model_dump()


class NarrativeSubjectDisplayBoundaryTests(unittest.TestCase):
    def setUp(self):
        for name in ("connect", "connect_ex"):
            blocked = patch.object(socket.socket, name, side_effect=AssertionError("Provider-free characterization"))
            blocked.start()
            self.addCleanup(blocked.stop)
        self.owners = [_obligation("activity", "narrative", "Inspection activity")]

    def validate(self, catalog, program):
        return validate_semantic_calculation_program(program=program, candidate_catalog=catalog,
            obligations=self.owners, query="Describe inspection activity.", require_narrative_claims=True,
            candidate_visibility=_semantic_candidate_visibility(catalog,
                visible_candidate_ids=["note"], candidate_ids_by_owner={"activity": ["note"]}))

    def test_identical_display_does_not_imply_identical_current_source_validation(self):
        for whitespace in ("\n", "\r\n", "\t", "  ", "\u00a0", "\u2009", "\u3000", "\r\n\r\n"):
            with self.subTest(whitespace=repr(whitespace)):
                subject = "Cypress" + whitespace + "Workshop"
                catalog, exact = fixture(subject)
                display = " ".join(subject.split())
                normalized = changed_subject(exact, display)
                before = deepcopy((catalog, exact, normalized))
                self.assertEqual(render_narrative_claim({"subject": subject, "text": "Records inspections."}),
                    render_narrative_claim({"subject": display, "text": "Records inspections."}))
                self.assertEqual(self.validate(catalog, exact)["status"], "ready")
                failed = self.validate(catalog, normalized)
                self.assertEqual([e["code"] for e in failed["errors"]], ["ungrounded_narrative_subject"])
                self.assertEqual(failed["errors"][0]["location"], "subject_bindings[0]")
                self.assertEqual((catalog, exact, normalized), before)

    def test_display_mismatch_does_not_mutate_exact_selected_evidence_or_offsets(self):
        catalog, exact = fixture("Cypress\r\nWorkshop")
        normalized = changed_subject(exact, "Cypress Workshop")
        outputs = []
        for program in (exact, normalized):
            readings, errors = validate_narrative_claims(program["narrative_bindings"][0], {"note": catalog[0]},
                number_check=lambda *_: [], visible_candidate_ids=["note"], require_addressed=True)
            outputs.append((readings, errors))
        self.assertEqual(outputs[0][0][0]["evidence"], outputs[1][0][0]["evidence"])
        self.assertEqual(outputs[0][0][0]["subject_evidence"], outputs[1][0][0]["subject_evidence"])
        self.assertIn("Cypress\r\nWorkshop", outputs[1][0][0]["subject_evidence"][0]["evidence_text"])
        self.assertEqual(outputs[0][1], [])
        self.assertEqual([e["code"] for e in outputs[1][1]], ["ungrounded_narrative_subject"])

    def test_non_whitespace_name_changes_are_not_display_equivalence(self):
        catalog, exact = fixture("Cypress Workshop, Ltd.")
        for subject in ("CypressWorkshop, Ltd.", "Cy press Workshop, Ltd.", "cypress Workshop, Ltd.",
                "Cypress Workshop Ltd.", "Cypres\u200bs Workshop, Ltd.", "Cypress Workshops, Ltd.",
                "Cypress Workshop, Ltd. and its branch", "Willow Workshop, Ltd."):
            with self.subTest(subject=subject):
                failed = self.validate(catalog, changed_subject(exact, subject))
                self.assertIn("ungrounded_narrative_subject", [e["code"] for e in failed["errors"]])

    def test_unselected_tail_is_not_available_even_if_full_fact_selection_contains_subject(self):
        catalog, exact = fixture("Cypress\r\nWorkshop")
        changed = changed_subject(exact, "Cypress Workshop")
        binding = changed["narrative_bindings"][0]
        link = binding["subject_bindings"][0]["evidence_selections"][0]
        link["last_piece_id"] = link["first_piece_id"]
        readings, errors = validate_narrative_claims(binding, {"note": catalog[0]},
            number_check=lambda *_: [], visible_candidate_ids=["note"], require_addressed=True)
        self.assertIn("Workshop", readings[0]["evidence"][0]["evidence_text"])
        self.assertNotIn("Workshop", readings[0]["subject_evidence"][0]["evidence_text"])
        self.assertIn("ungrounded_narrative_subject", [e["code"] for e in errors])

    def test_exact_substring_is_not_a_full_entity_or_group_scope_oracle(self):
        # Intentional semantic negative: existing containment accepts a shorter
        # source-copied label; do not describe whitespace matching as fixing this.
        catalog, exact = fixture("Cypress Workshop and its branch")
        shorter = changed_subject(exact, "Cypress Workshop")
        self.assertEqual(self.validate(catalog, shorter)["status"], "ready")
        self.assertNotEqual(exact["narrative_bindings"][0]["subject_bindings"][0]["subject"],
            shorter["narrative_bindings"][0]["subject_bindings"][0]["subject"])


if __name__ == "__main__":
    unittest.main()
