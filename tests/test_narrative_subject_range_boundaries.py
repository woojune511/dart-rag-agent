"""Anonymous boundary/retry characterization, not model accuracy or quote repair."""

from copy import deepcopy
import json
import socket
import unittest
from unittest.mock import patch

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program, validate_semantic_calculation_program,
)
from src.agent.financial_evidence_addresses import build_narrative_address_book, resolve_narrative_selection
from src.agent.financial_graph_calculation import _semantic_candidate_visibility
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.narrative_address_test_support import selection
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM
from tests.test_narrative_claim_grounding import source
from tests.test_narrative_retry_context import prompt_json


# None of these sources, identities, facts or answers come from a filing/benchmark.
BOUNDARY_SUBJECTS = {
    "abbreviation": "Aster Labs, Inc. and its affiliates",
    "initials": "A. B. Workshop and its branches",
    "multiple_periods": "Studio R. and Field S. Team",
    "quoted_punctuation": 'Studio "A!" and its branch',
    "line_break": "Maple\nWorkshop",
    "windows_blank_line": "햇솔\r\n\r\n작업소",
    "ideographic_punctuation": "青葉。 試験組",
    "fullwidth_punctuation": "시험！ 작업반",
    "long_token": "L" * 177 + " Workshop",
    "long_spaced_name": "Cedar " * 30 + "Team",
}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def fixture(subject, *, text=None, source_overrides=None):
    body = text if text is not None else f"{subject} records inspections."
    catalog = [source("note", body, **(source_overrides or {}))]
    full = selection(catalog, "note", subject)
    program = {"narrative_bindings": [{"obligation_id": "activity", "subject_bindings": [{
        "subject_binding_id": "subject", "subject": subject, "evidence_selections": [full],
    }], "claims": [{"subject_binding_id": "subject", "text": "Records inspections.",
        "fact_evidence_selections": [selection(catalog, "note", body)]}]}]}
    # Schema projection is the same ingress used for authored compiler responses.
    return catalog, SemanticCalculationProgram.model_validate(program).model_dump()


def truncated_subject(program):
    result = deepcopy(program)
    link = result["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"][0]
    link["last_piece_id"] = link["first_piece_id"]
    return result


class NarrativeSubjectRangeBoundaryTests(unittest.TestCase):
    query = "Describe inspection activity."

    def setUp(self):
        # Queue-backed compiler tests must never create provider traffic.
        for name in ("connect", "connect_ex"):
            blocked = patch.object(socket.socket, name, side_effect=AssertionError("Provider-free test"))
            blocked.start()
            self.addCleanup(blocked.stop)
        self.owners = [_obligation("activity", "narrative", "Inspection activity")]

    def validate_execute(self, catalog, program, *, selectable=None):
        visibility = _semantic_candidate_visibility(catalog,
            visible_candidate_ids=[c["candidate_id"] for c in catalog],
            candidate_ids_by_owner={"activity": selectable if selectable is not None else ["note"]})
        validation = validate_semantic_calculation_program(program=program, candidate_catalog=catalog,
            obligations=self.owners, query=self.query, candidate_visibility=visibility, require_narrative_claims=True)
        envelope = CompilationEnvelopeV2.create(program=program, validation=validation,
            visibility=visibility, candidate_catalog=catalog, obligations=self.owners, query=self.query)
        result = execute_semantic_calculation_program(program=program, candidate_catalog=catalog,
            obligations=self.owners, query=self.query, compilation_envelope=envelope, require_compilation_envelope=True)
        return validation, result

    def test_all_ten_mechanical_boundaries_preserve_full_subject_and_source(self):
        for name, subject in BOUNDARY_SUBJECTS.items():
            with self.subTest(boundary=name):
                catalog, program = fixture(subject)
                before = deepcopy((catalog, program))
                book = build_narrative_address_book(catalog)
                surface = book["note"][0]
                self.assertEqual("".join(p["text"] for p in surface.to_projection()["pieces"]), catalog[0]["source_text"])
                link = program["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"][0]
                self.assertNotEqual(link["first_piece_id"], link["last_piece_id"])
                self.assertIn(subject, resolve_narrative_selection(link, book)[1])
                validation, result = self.validate_execute(catalog, program)
                self.assertEqual(validation["status"], "ready", validation["errors"])
                self.assertEqual(result["status"], "ok")
                self.assertEqual((catalog, program), before)

    def test_first_piece_only_fails_even_when_fact_selection_contains_whole_subject(self):
        for name, subject in BOUNDARY_SUBJECTS.items():
            with self.subTest(boundary=name):
                catalog, program = fixture(subject)
                bad = truncated_subject(program)
                binding = bad["narrative_bindings"][0]
                fact = binding["claims"][0]["fact_evidence_selections"][0]
                self.assertIn(subject, resolve_narrative_selection(fact, build_narrative_address_book(catalog))[1])
                validation, result = self.validate_execute(catalog, bad)
                errors = [e for e in validation["errors"] if e["code"] == "ungrounded_narrative_subject"]
                self.assertEqual(len(errors), 1, validation["errors"])
                self.assertEqual((errors[0]["obligation_id"], errors[0]["location"], errors[0]["repair_action"]),
                    ("activity", "subject_bindings[0]", "repair_program"))
                self.assertEqual(result["outputs"], [])

    def test_single_piece_and_decimal_names_do_not_need_range_expansion(self):
        for subject in ("Short Studio", "Workshop 4.7"):
            catalog, program = fixture(subject)
            link = program["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"][0]
            self.assertEqual(link["first_piece_id"], link["last_piece_id"])
            self.assertEqual(self.validate_execute(catalog, program)[0]["status"], "ready")

    def test_individual_adjacent_pieces_are_not_an_implicitly_joined_subject(self):
        catalog, program = fixture(BOUNDARY_SUBJECTS["abbreviation"])
        full = program["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"][0]
        split = deepcopy(program)
        split["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"] = [
            {**full, "last_piece_id": full["first_piece_id"]},
            {**full, "first_piece_id": full["last_piece_id"]},
        ]
        validation, result = self.validate_execute(catalog, split)
        self.assertIn("ungrounded_narrative_subject", {e["code"] for e in validation["errors"]})
        self.assertEqual(result["outputs"], [])
        self.assertEqual(self.validate_execute(catalog, program)[0]["status"], "ready")

    def test_full_range_cannot_bridge_physical_cells(self):
        subject = BOUNDARY_SUBJECTS["abbreviation"]
        body = subject + " records inspections."
        boundary = body.index(" and")
        catalog, program = fixture(subject, text=body, source_overrides={"source_context_provenance": {
            "source_text": body, "source_segments": [{"text_span": [0, boundary], "cell_locator": "cell-left"},
                {"text_span": [boundary, len(body)], "cell_locator": "cell-right"}]}})
        validation, result = self.validate_execute(catalog, program)
        self.assertIn("cross_partition_narrative_selection", {e["code"] for e in validation["errors"]})
        self.assertEqual(result["outputs"], [])

    def test_complete_subject_support_cannot_borrow_another_owner_or_hidden_source(self):
        catalog, program = fixture(BOUNDARY_SUBJECTS["abbreviation"])
        catalog.append(source("foreign", catalog[0]["source_text"], source_document_id="filing:foreign"))
        bad = truncated_subject(program)
        registry = bad["narrative_bindings"][0]["subject_bindings"][0]
        registry["evidence_selections"].append(selection(catalog, "foreign", registry["subject"]))
        # Reproject explicitly derived parent IDs after changing the authored draft.
        binding = bad["narrative_bindings"][0]
        for key in ("candidate_ids", "evidence_bindings", "text"):
            binding.pop(key)
        bad = SemanticCalculationProgram.model_validate(bad).model_dump()
        validation, result = self.validate_execute(catalog, bad)
        self.assertIn("candidate_not_exposed_to_compiler", {e["code"] for e in validation["errors"]})
        self.assertEqual(result["outputs"], [])

    def test_unmentioned_suffix_and_normalized_newline_cannot_be_invented(self):
        for actual, claimed in (("Aster Labs, Inc.", "Aster Labs, Inc. and its affiliates"),
                                ("Maple\nWorkshop", "Maple Workshop")):
            catalog, program = fixture(actual)
            binding = program["narrative_bindings"][0]
            binding["subject_bindings"][0]["subject"] = claimed
            for key in ("candidate_ids", "evidence_bindings", "text"):
                binding.pop(key)
            bad = SemanticCalculationProgram.model_validate(program).model_dump()
            validation, result = self.validate_execute(catalog, bad)
            self.assertIn("ungrounded_narrative_subject", {e["code"] for e in validation["errors"]})
            self.assertEqual(result["outputs"], [])

    def test_expanded_subject_range_does_not_grant_its_numbers_to_other_facts(self):
        subject = BOUNDARY_SUBJECTS["abbreviation"]
        body = subject + " records 37 inspections. It stores samples."
        catalog, program = fixture(subject, text=body)
        binding = program["narrative_bindings"][0]
        binding["claims"][0].update(text="Stores 37 samples.", fact_evidence_selections=[
            selection(catalog, "note", "It stores samples.")])
        for key in ("candidate_ids", "evidence_bindings", "text"):
            binding.pop(key)
        program = SemanticCalculationProgram.model_validate(program).model_dump()
        validation, result = self.validate_execute(catalog, program)
        self.assertIn("ungrounded_narrative_claim_number", {e["code"] for e in validation["errors"]})
        self.assertEqual(result["outputs"], [])

    def test_stale_surface_never_becomes_valid_by_selecting_more_pieces(self):
        catalog, program = fixture(BOUNDARY_SUBJECTS["abbreviation"])
        changed = deepcopy(catalog)
        for field in ("source_text", "source_bundle_text"):
            changed[0][field] = changed[0][field].replace("Inc.", "Unit!")
        validation, result = self.validate_execute(changed, program)
        self.assertIn("unknown_narrative_surface", {e["code"] for e in validation["errors"]})
        self.assertEqual(result["outputs"], [])

    def test_authored_retry_fixes_only_range_and_preserves_accepted_numeric_island(self):
        catalog, program = fixture(BOUNDARY_SUBJECTS["abbreviation"])
        bad = SemanticCalculationProgram.model_validate(truncated_subject(program))
        good = SemanticCalculationProgram.model_validate(program)
        accepted = SemanticCalculationProgram(direct_bindings=[{"obligation_id": "size", "candidate_id": "cell"}])
        llm = _StructuredQueueLLM(accepted, bad, good)
        state = _case_state({"question": self.query, "obligations": [
            _obligation("size", "direct_value", "Size"), *self.owners]}, [_candidate("cell", 12), *catalog])
        before = deepcopy(state)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(canonical(compiled["semantic_program"]["direct_bindings"]), canonical(accepted.model_dump()["direct_bindings"]))
        marker = "Source bundles, candidate cohorts, and candidates_by_id:"
        self.assertEqual(prompt_json(llm.prompts[1], marker), prompt_json(llm.prompts[2], marker))
        feedback = prompt_json(llm.prompts[2], "재시도 피드백(없으면 -):")
        draft = feedback["unvalidated_narrative_drafts"][0]
        self.assertEqual(draft["subject_bindings"][0]["evidence_selections"],
            bad.model_dump()["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"])
        self.assertEqual(draft["claims"][0]["fact_evidence_selections"],
            good.model_dump()["narrative_bindings"][0]["claims"][0]["fact_evidence_selections"])
        check = draft["subject_bindings"][0]["source_selection_check"]
        self.assertEqual(check["declared_subject"], BOUNDARY_SUBJECTS["abbreviation"])
        self.assertEqual(check["selections"][0]["selected_text"], "Aster Labs, Inc. ")
        self.assertFalse(check["selections"][0]["contains_declared_subject"])
        self.assertIn("subject_selection_invariant", feedback["repair_contract"])
        self.assertNotIn("source_selection_check", llm.prompts[1].to_messages()[0].content)
        self.assertNotIn("source_selection_check", canonical(compiled["semantic_program"]).decode())
        self.assertNotIn("source_selection_check", canonical(compiled["semantic_program_validation"]).decode())
        self.assertNotIn("cell", canonical(draft).decode())
        self.assertEqual(state, before)

    def test_unchanged_truncated_retry_stops_without_third_attempt_or_silent_repair(self):
        catalog, program = fixture(BOUNDARY_SUBJECTS["abbreviation"])
        bad = SemanticCalculationProgram.model_validate(truncated_subject(program))
        llm = _StructuredQueueLLM(bad, bad)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(_case_state({
            "question": self.query, "obligations": self.owners}, catalog))
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(compiled["semantic_program"]["narrative_bindings"], [])
        history = compiled["planner_debug_trace"]["program_validation_history"]
        self.assertEqual(len(history), 2)
        self.assertTrue(all(any(e["code"] == "ungrounded_narrative_subject" for e in h["errors"]) for h in history))
        self.assertIn("activity", compiled["semantic_program_validation"]["missing_obligation_ids"])


if __name__ == "__main__":
    unittest.main()
