"""Whitespace-only subject witnesses, not source repair or an identity oracle."""

from copy import deepcopy
import socket
import unittest
from unittest.mock import patch

from src.agent.financial_calculation_execution import execute_semantic_calculation_program, validate_semantic_calculation_program
from src.agent.financial_evidence_addresses import build_narrative_address_book, resolve_narrative_selection
from src.agent.financial_graph_calculation import _semantic_candidate_visibility
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_narrative_claims import validate_narrative_claims
from src.agent.financial_program_projection import render_narrative_claim
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.narrative_address_test_support import selection
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM
from tests.test_narrative_claim_grounding import source
from tests.test_narrative_retry_context import prompt_json
from tests.test_narrative_subject_range_boundaries import canonical, fixture


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

    def test_whitespace_layouts_preserve_model_source_and_exact_path(self):
        for whitespace in ("\n", "\r\n", "\t", "  ", "\u00a0", "\u2009", "\u3000", "\r\n\r\n"):
            with self.subTest(whitespace=repr(whitespace)):
                subject = "Cypress" + whitespace + "Workshop"
                catalog, exact = fixture(subject)
                display = " ".join(subject.split())
                normalized = changed_subject(exact, display)
                before = deepcopy((catalog, exact, normalized))
                self.assertEqual(render_narrative_claim({"subject": subject, "text": "Records inspections."}),
                    render_narrative_claim({"subject": display, "text": "Records inspections."}))
                original = self.validate(catalog, exact)
                self.assertEqual(original["status"], "ready")
                self.assertNotIn("subject_grounding", original["valid_narrative_bindings"][0]["claim_readings"][0])
                accepted = self.validate(catalog, normalized)
                self.assertEqual(accepted["status"], "ready", accepted["errors"])
                reading = accepted["valid_narrative_bindings"][0]["claim_readings"][0]
                witness = reading["subject_grounding"]
                self.assertEqual(witness, {"match_kind": "whitespace_layout", "model_subject": display,
                    "source_subject": subject, "source_subject_span": [0, len(subject)], "evidence_index": 0})
                self.assertEqual(reading["subject"], display)
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
        self.assertEqual(outputs[1][1], [])
        witness = outputs[1][0][0].pop("subject_grounding")
        outputs[0][0][0]["subject"] = "Cypress Workshop"
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(witness["source_subject"], "Cypress\r\nWorkshop")

    def test_witness_uses_source_surface_character_offsets_and_retains_provenance(self):
        raw = "Cypress\r\nWorkshop"
        body = "📘 Heading.\n" + raw + " records inspections."
        catalog, exact = fixture(raw, text=body)
        program = changed_subject(exact, "Cypress Workshop")
        accepted = self.validate(catalog, program)
        reading = accepted["valid_narrative_bindings"][0]["claim_readings"][0]
        witness = reading["subject_grounding"]
        evidence = reading["subject_evidence"][witness["evidence_index"]]
        span = witness["source_subject_span"]
        surface, quote, selected_span = resolve_narrative_selection(evidence, build_narrative_address_book(catalog))
        self.assertEqual(surface.source_text[slice(*span)], raw)
        self.assertEqual(span, [body.index(raw), body.index(raw) + len(raw)])
        self.assertEqual(evidence["evidence_text"], quote)
        self.assertEqual(evidence["source_span"], list(selected_span))
        self.assertEqual(evidence["source_anchor"], catalog[0]["source_anchor"])

    def test_multiple_occurrences_need_narrowing_but_duplicate_selections_do_not(self):
        raw = "Cypress\nWorkshop"
        body = raw + " records inspections. " + raw + " stores samples."
        catalog, exact = fixture(raw, text=body)
        program = changed_subject(exact, "Cypress Workshop")
        subject = program["narrative_bindings"][0]["subject_bindings"][0]
        original = deepcopy(subject["evidence_selections"])
        # Overlapping ranges covering only the same physical name dedupe as well.
        subject["evidence_selections"] = original * 2 + [selection(catalog, "note", raw + " records inspections.")]
        self.assertEqual(self.validate(catalog, program)["status"], "ready")
        for links in ([selection(catalog, "note", body)],
                original + [selection(catalog, "note", raw, occurrence=1)]):
            subject["evidence_selections"] = links
            failed = self.validate(catalog, program)
            error = next(e for e in failed["errors"] if e["code"] == "ambiguous_narrative_subject")
            self.assertEqual((error["obligation_id"], error["owner_id"], error["location"], error["repair_action"]),
                ("activity", "activity", "subject_bindings[0]", "repair_program"))
            self.assertEqual(failed["valid_narrative_bindings"], [])
        subject["evidence_selections"] = original
        self.assertEqual(self.validate(catalog, program)["status"], "ready")

    def test_exact_match_keeps_existing_behavior_even_with_repeated_positions(self):
        raw = "Cypress\nWorkshop"
        body = raw + " records inspections. " + raw + " stores samples."
        catalog, program = fixture(raw, text=body)
        program["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"] = [selection(catalog, "note", body)]
        accepted = self.validate(catalog, program)
        self.assertEqual(accepted["status"], "ready")
        self.assertNotIn("subject_grounding", canonical(accepted).decode())

    def test_same_attached_source_location_does_not_become_two_occurrences(self):
        context = {"context_id": "heading", "relation": "ancestor_heading",
            "source_text": "Cypress\nWorkshop", "source_span": [17, 33]}
        catalog, exact = fixture(context["source_text"])
        catalog = [source(key, "It records inspections.", source_contexts=[context]) for key in ("note", "copy")]
        binding = exact["narrative_bindings"][0]
        binding["subject_bindings"][0]["evidence_selections"] = [
            selection(catalog, key, context["source_text"], context_id="heading") for key in ("note", "copy")]
        binding["claims"][0]["fact_evidence_selections"] = [selection(catalog, "note", "It records inspections.")]
        program = changed_subject(exact, "Cypress Workshop")
        readings, errors = validate_narrative_claims(program["narrative_bindings"][0],
            {row["candidate_id"]: row for row in catalog}, number_check=lambda *_: [], require_addressed=True)
        self.assertEqual(errors, [])
        self.assertEqual(readings[0]["subject_grounding"]["source_subject"], context["source_text"])
        self.assertEqual(readings[0]["subject_evidence"][0]["container_source_span"], [17, 33])

    def test_layout_match_cannot_bridge_separate_selections_or_physical_cells(self):
        raw = "Cypress\r\nWorkshop"
        catalog, exact = fixture(raw)
        program = changed_subject(exact, "Cypress Workshop")
        registry = program["narrative_bindings"][0]["subject_bindings"][0]
        full = registry["evidence_selections"][0]
        registry["evidence_selections"] = [{**full, "last_piece_id": full["first_piece_id"]},
            {**full, "first_piece_id": full["last_piece_id"]}]
        self.assertIn("ungrounded_narrative_subject", {e["code"] for e in self.validate(catalog, program)["errors"]})
        body = raw + " records inspections."
        boundary = body.index("Workshop")
        catalog, exact = fixture(raw, source_overrides={"source_context_provenance": {
            "source_text": body, "source_segments": [{"text_span": [0, boundary], "cell_locator": "left"},
                {"text_span": [boundary, len(body)], "cell_locator": "right"}]}})
        failed = self.validate(catalog, changed_subject(exact, "Cypress Workshop"))
        self.assertIn("cross_partition_narrative_selection", {e["code"] for e in failed["errors"]})
        self.assertEqual(failed["valid_narrative_bindings"], [])

    def test_owner_and_requirement_permissions_precede_layout_matching(self):
        catalog, exact = fixture("Cypress\r\nWorkshop")
        program = changed_subject(exact, "Cypress Workshop")
        self.owners[0]["evidence_requirements"] = [{"requirement_id": "activity:r", "required": False}]
        for owner_ids, requirement_id in (([], ""), (["note"], "activity:r"), (["note"], "foreign:r")):
            with self.subTest(owner_ids=owner_ids, requirement_id=requirement_id):
                program["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"][0]["source_requirement_id"] = requirement_id
                program = changed_subject(program, "Cypress Workshop")
                visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=["note"],
                    candidate_ids_by_owner={"activity": owner_ids, "activity:r": [], "foreign:r": ["note"]})
                validation = validate_semantic_calculation_program(program=program, candidate_catalog=catalog,
                    obligations=self.owners, query="Describe inspection activity.",
                    candidate_visibility=visibility, require_narrative_claims=True)
                self.assertIn("ungrounded_narrative_subject", {e["code"] for e in validation["errors"]})
                self.assertEqual(validation["valid_narrative_bindings"], [])

    def test_layout_witness_does_not_supply_fact_numbers(self):
        raw = "Cypress\r\nWorkshop"
        catalog, exact = fixture(raw, text=raw + " records 37 inspections. It stores samples.")
        exact["narrative_bindings"][0]["claims"][0].update(text="Stores 37 samples.",
            fact_evidence_selections=[selection(catalog, "note", "It stores samples.")])
        validation = self.validate(catalog, changed_subject(exact, "Cypress Workshop"))
        self.assertIn("ungrounded_narrative_claim_number", {e["code"] for e in validation["errors"]})
        self.assertNotIn("ungrounded_narrative_subject", {e["code"] for e in validation["errors"]})
        self.assertEqual(validation["valid_narrative_bindings"], [])

    def test_layout_witness_survives_execution_and_is_bound_by_v2(self):
        catalog, exact = fixture("Cypress\r\nWorkshop")
        program = changed_subject(exact, "Cypress Workshop")
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=["note"],
            candidate_ids_by_owner={"activity": ["note"]})
        validation = self.validate(catalog, program)
        before = canonical((catalog, program, validation))

        def execute(rows, checked):
            envelope = CompilationEnvelopeV2.create(program=program, validation=checked, visibility=visibility,
                candidate_catalog=catalog, obligations=self.owners, query="Describe inspection activity.")
            return execute_semantic_calculation_program(program=program, candidate_catalog=rows,
                obligations=self.owners, query="Describe inspection activity.", compilation_envelope=envelope,
                require_compilation_envelope=True)

        result = execute(catalog, validation)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["outputs"][0]["claim_readings"], validation["valid_narrative_bindings"][0]["claim_readings"])
        tampered = deepcopy(validation)
        tampered["valid_narrative_bindings"][0]["claim_readings"][0]["subject_grounding"]["source_subject_span"][0] = 1
        rejected = execute(catalog, tampered)
        self.assertEqual(rejected["outputs"], [])
        self.assertIn("validation_drift", canonical(rejected).decode())
        altered_source = deepcopy(catalog)
        altered_source[0]["source_text"] += " "
        rejected = execute(altered_source, validation)
        self.assertEqual(rejected["outputs"], [])
        self.assertIn("execution_content_mismatch", canonical(rejected).decode())
        result["outputs"][0]["claim_readings"][0]["subject_grounding"]["source_subject_span"][0] = 2
        self.assertEqual(canonical((catalog, program, validation)), before)

    def test_ambiguity_retry_keeps_cohort_and_accepted_numeric_program(self):
        raw = "Cypress\r\nWorkshop"
        body = raw + " records inspections. " + raw + " stores samples."
        catalog, exact = fixture(raw, text=body)
        good = changed_subject(exact, "Cypress Workshop")
        # These IDs are assigned by lowering, not repeated in the model schema.
        good['narrative_bindings'][0]['subject_bindings'][0]['subject_binding_id'] = 's1'
        for claim in good['narrative_bindings'][0]['claims']:
            claim['subject_binding_id'] = 's1'
        bad = deepcopy(good)
        bad["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"] = [selection(catalog, "note", body)]
        accepted = SemanticCalculationProgram(direct_bindings=[{"obligation_id": "size", "candidate_id": "cell"}])
        llm = _StructuredQueueLLM(accepted, SemanticCalculationProgram.model_validate(bad),
            SemanticCalculationProgram.model_validate(good))
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(_case_state({
            "question": "Describe inspection activity.", "obligations": [
                _obligation("size", "direct_value", "Size"), *self.owners]}, [_candidate("cell", 12), *catalog]))
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(canonical(compiled["semantic_program"]["direct_bindings"]), canonical(accepted.model_dump()["direct_bindings"]))
        self.assertEqual(canonical(compiled["semantic_program"]["narrative_bindings"]), canonical(good["narrative_bindings"]))
        marker = "Source bundles, candidate cohorts, and candidates_by_id:"
        self.assertEqual(prompt_json(llm.prompts[1], marker), prompt_json(llm.prompts[2], marker))
        feedback = prompt_json(llm.prompts[2], "재시도 피드백(없으면 -):")
        draft = feedback["unvalidated_narrative_drafts"][0]
        check = draft["subject_bindings"][0]["source_selection_check"]
        self.assertEqual(check["subject_grounding"], {"match_kind": "ambiguous", "occurrence_count": 2})
        self.assertFalse(check["selections"][0]["contains_declared_subject"])
        self.assertNotIn("cell", canonical(draft).decode())

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
