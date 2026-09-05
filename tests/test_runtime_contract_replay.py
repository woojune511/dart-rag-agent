from __future__ import annotations

from copy import deepcopy
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.agent.financial_runtime_contracts import CandidateVisibilityV1
from src.ops.replay_runtime_contract_cases import (
    FIRST_COMPATIBILITY_ID,
    FIRST_DIRECT_ID,
    _canonical_bytes,
    _explicit_legacy_expression_decisions,
    _first_attempt_visibility,
    _project_program_case,
    main,
)


def _plan(program: dict) -> dict:
    visibility = CandidateVisibilityV1.create(
        catalog_fingerprint="catalog", visible_candidate_ids=["current-candidate"],
        candidate_ids_by_owner={"ob_001": ["current-candidate"]},
    )
    return {"semantic_program": program, "candidate_visibility": visibility.to_projection()}


class RuntimeContractReplayTests(unittest.TestCase):
    def test_legacy_schema_migration_is_explicit_and_leaves_predecessor_bytes_unchanged(self) -> None:
        original = {"expressions": [{
            "obligation_id": "ob_001", "formula": "X", "result_unit": "COUNT",
            "variable_bindings": [{"variable": "X", "source_id": "candidate"}],
            "source_display_candidate_id": "",
        }]}
        before = _canonical_bytes(original)
        copied, changes = _explicit_legacy_expression_decisions(original)
        self.assertEqual(_canonical_bytes(original), before)
        self.assertIsNone(copied["expressions"][0]["source_display_candidate_id"])
        self.assertTrue(copied["expressions"][0]["source_display_reason"].strip())
        self.assertEqual({item["field"] for item in changes}, {"source_display_candidate_id", "source_display_reason"})

    def test_unchanged_saved_program_does_not_receive_default_projection_edits(self) -> None:
        program = {"direct_bindings": [{"obligation_id": "ob_001", "candidate_id": "current-candidate"}]}
        before = _canonical_bytes(program)
        copied, _visibility, mode, changes = _project_program_case("HYU_T3_072", _plan(program))
        self.assertEqual(_canonical_bytes(copied), before)
        self.assertEqual(mode, "saved_program_unchanged")
        self.assertEqual(changes, [])

    def test_counterfactual_does_not_admit_a_hidden_source_display(self) -> None:
        plan = _plan({"expressions": [{
            "obligation_id": "ob_001", "formula": "X", "result_unit": "%",
            "variable_bindings": [{"variable": "X", "source_id": "current-candidate"}],
            "source_display_candidate_id": None, "source_display_reason": "No display selected.",
        }]})
        with self.assertRaisesRegex(ValueError, "outside saved owner visibility"):
            _project_program_case("HYU_T2_010", plan)

    def test_first_attempt_authority_requires_matching_saved_cohort_and_history(self) -> None:
        plan = _plan({})
        initial = [FIRST_DIRECT_ID, FIRST_COMPATIBILITY_ID]
        plan["candidate_cohorts"] = [{"owner_id": "ob_001", "candidate_ids": initial}]
        plan["program_validation_history"] = [{"attempt": 1, "proposed_candidate_ids": list(initial), "visible_candidate_ids": list(initial)}]
        visibility = _first_attempt_visibility(plan)
        self.assertEqual(list(visibility.visible_candidate_ids), initial)
        self.assertNotIn("current-candidate", visibility.visible_candidate_ids)
        mismatched = deepcopy(plan)
        mismatched["candidate_cohorts"][0]["candidate_ids"].append("invented")
        with self.assertRaisesRegex(ValueError, "does not match saved"):
            _first_attempt_visibility(mismatched)

    def test_existing_receipt_is_not_overwritten_or_replayed(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"
            # The test creates an empty predecessor; production uses exclusive create.
            output.touch()
            with patch("src.ops.replay_runtime_contract_cases.replay_reviewed_cases") as replay:
                with self.assertRaises(SystemExit) as raised, redirect_stderr(StringIO()):
                    main(["--results", "unused.json", "--output", str(output)])
            self.assertEqual(raised.exception.code, 2)
            replay.assert_not_called()
            self.assertEqual(output.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
