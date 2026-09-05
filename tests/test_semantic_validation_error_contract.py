"""Explicit validator repair metadata; candidate IDs are never parsed from detail."""

from __future__ import annotations

import unittest

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program,
    validate_semantic_calculation_program,
)
from src.agent.financial_graph_calculation import _retry_candidate_exclusions
from tests.semantic_program_test_support import _candidate, _obligation, _source_assertions


class SemanticValidationErrorContractTests(unittest.TestCase):
    def test_source_assertion_errors_identify_the_known_candidate_and_format_location(self):
        candidate = {
            **_candidate("cand_value", 10), "candidate_kind": "sentence_value",
            "table_source_id": "", "source_text": "The source reports 10 items.",
        }
        assertion = _source_assertions([candidate], "cand_value")[0]
        base_program = {"direct_bindings": [{"obligation_id": "value", "candidate_id": "cand_value"}]}
        for assertions, expected_codes in (
            ([], {"missing_source_assertion"}),
            ([{**assertion, "evidence_text": "The source reports 11 items."}],
             {"source_assertion_text_mismatch", "missing_source_assertion"}),
        ):
            with self.subTest(assertions=assertions):
                program = {**base_program, "source_assertions": assertions}
                validation = validate_semantic_calculation_program(
                    program=program, obligations=[_obligation("value", "direct_value", "quantity")],
                    candidate_catalog=[candidate], query="Return the quantity.",
                )
                self.assertEqual({error["code"] for error in validation["errors"]}, expected_codes)
                for error in validation["errors"]:
                    self.assertEqual(set(error), {
                        "code", "obligation_id", "detail", "owner_id", "candidate_id", "location", "repair_action",
                    })
                    self.assertEqual(error["owner_id"], "value")
                    self.assertEqual(error["candidate_id"], "cand_value")
                    self.assertEqual(error["location"], "source_assertion")
                    self.assertEqual(error["repair_action"], "repair_program")
                self.assertEqual(_retry_candidate_exclusions(
                    program=program, validation_errors=validation["errors"], target_obligation_ids=["value"],
                ), {})

    def test_fail_closed_execution_validation_uses_the_same_error_schema(self):
        execution = execute_semantic_calculation_program(
            program={"direct_bindings": [{"obligation_id": "value", "candidate_id": "cand_value"}]},
            obligations=[_obligation("value", "direct_value", "quantity")],
            candidate_catalog=[_candidate("cand_value", 10)], query="Return the quantity.",
            require_compilation_envelope=True,
        )
        self.assertEqual(execution["outputs"], [])
        self.assertEqual(execution["validation"]["errors"], [{
            "code": "visibility_mismatch", "obligation_id": "",
            "detail": "compile-time visibility envelope is missing",
            "owner_id": "", "candidate_id": "", "location": "compilation_envelope",
            "repair_action": "repair_program",
        }])

    def test_retry_exclusion_requires_explicit_selected_pair_and_ignores_detail(self):
        program = {"direct_bindings": [{"obligation_id": "value", "candidate_id": "cand_value"}]}
        error = {
            "code": "candidate_scope_mismatch", "obligation_id": "value", "detail": "cand_value",
            "owner_id": "", "candidate_id": "", "location": "direct_binding", "repair_action": "replace_candidate",
        }
        for change, expected in (
            ({}, {}),
            ({"owner_id": "value", "candidate_id": "cand_value", "repair_action": "repair_program"}, {}),
            ({"owner_id": "wrong_owner", "candidate_id": "cand_value"}, {}),
            ({"owner_id": "value", "candidate_id": "not_selected"}, {}),
            ({"owner_id": "value", "candidate_id": "cand_value", "detail": "not_selected"}, {"value": ["cand_value"]}),
        ):
            with self.subTest(change=change):
                self.assertEqual(_retry_candidate_exclusions(
                    program=program, validation_errors=[{**error, **change}], target_obligation_ids=["value"],
                ), expected)


if __name__ == "__main__":
    unittest.main()
