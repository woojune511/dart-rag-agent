from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from src.agent.financial_runtime_contracts import (
    CandidateVisibilityV1,
    CompilationEnvelopeV2,
    execution_content_fingerprint,
)


def _inputs() -> dict:
    return {
        "candidate_catalog": [
            {
                "candidate_id": "candidate-a",
                "raw_value": "10",
                "raw_unit": "items",
                "normalized_value": 10.0,
                "normalized_unit": "COUNT",
                "company": "sample",
                "row_headers": ["group", "subject"],
                "physical_table_id": "table-a",
                "physical_row_id": "row-a",
                "physical_cell_id": "cell-a",
                "source_anchor": "[sample]",
                "source_text": "current 10 items",
                "source_span": [8, 16],
                "source_bundle_text": "current 10 items",
                "source_bundle_context_span": [0, 16],
                "source_bundle_value_span": [8, 16],
            },
            {"candidate_id": "candidate-b", "raw_value": "20", "normalized_value": 20.0},
        ],
        "obligations": [
            {"obligation_id": "first", "scope": {"period": "current"}},
            {"obligation_id": "second", "scope": {"period": "prior"}},
        ],
        "query": "Return both values.",
    }


class ExecutionContentContractTests(unittest.TestCase):
    def test_catalog_and_mapping_order_do_not_change_content_fingerprint(self) -> None:
        inputs = _inputs()
        reordered = deepcopy(inputs)
        reordered["candidate_catalog"] = [
            dict(reversed(list(candidate.items())))
            for candidate in reversed(reordered["candidate_catalog"])
        ]
        self.assertEqual(
            execution_content_fingerprint(**inputs),
            execution_content_fingerprint(**reordered),
        )
        reordered["obligations"].reverse()
        self.assertNotEqual(
            execution_content_fingerprint(**inputs),
            execution_content_fingerprint(**reordered),
        )

    def test_full_candidate_content_is_bound_including_future_fields(self) -> None:
        inputs = _inputs()
        fingerprint = execution_content_fingerprint(**inputs)
        mutations = {
            "normalized_value": 10_000_000.0,
            "normalized_unit": "USD",
            "raw_value": "11",
            "raw_unit": "other",
            "company": "another subject",
            "row_headers": ["subject", "group"],
            "physical_table_id": "table-b",
            "physical_row_id": "row-b",
            "physical_cell_id": "cell-b",
            "source_anchor": "[other source]",
            "source_text": "previous 10 items",
            "source_span": [7, 16],
            "source_bundle_text": "current\t10 items",
            "source_bundle_context_span": [1, 17],
            "source_bundle_value_span": [9, 16],
            "future_execution_metadata": {"source": "new material"},
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                changed = deepcopy(inputs)
                changed["candidate_catalog"][0][field] = value
                self.assertNotEqual(fingerprint, execution_content_fingerprint(**changed))

    def test_query_and_nested_obligation_content_are_bound(self) -> None:
        inputs = _inputs()
        fingerprint = execution_content_fingerprint(**inputs)
        changed_query = {**inputs, "query": inputs["query"] + " "}
        self.assertNotEqual(fingerprint, execution_content_fingerprint(**changed_query))
        changed_scope = deepcopy(inputs)
        changed_scope["obligations"][0]["scope"]["period"] = "prior"
        self.assertNotEqual(fingerprint, execution_content_fingerprint(**changed_scope))
        changed_display = deepcopy(inputs)
        changed_display["obligations"][0]["display_unit"] = "%"
        self.assertNotEqual(fingerprint, execution_content_fingerprint(**changed_display))

    def test_envelope_captures_content_without_retaining_mutable_inputs(self) -> None:
        inputs = _inputs()
        visibility = CandidateVisibilityV1.create(
            catalog_fingerprint="legacy-catalog-fingerprint",
            visible_candidate_ids=["candidate-a", "candidate-b"],
            candidate_ids_by_owner={"first": ["candidate-a"], "second": ["candidate-b"]},
        )
        program = {"status": "ready", "direct_bindings": [{"candidate_id": "candidate-a"}]}
        validation = {"status": "ready", "selected_candidate_ids": ["candidate-a"]}
        envelope = CompilationEnvelopeV2.create(
            visibility=visibility,
            program=program,
            validation=validation,
            **inputs,
        )
        self.assertTrue(envelope.matches_execution_content(**inputs))
        self.assertEqual(envelope.schema_version, "compilation_envelope_v2")
        self.assertEqual(len(envelope.execution_content_fingerprint), 64)
        self.assertIs(envelope.visibility, visibility)
        frozen_projection = envelope.to_projection()

        inputs["candidate_catalog"][0]["normalized_value"] = 10_000_000.0
        inputs["candidate_catalog"][0]["row_headers"].append("new subject")
        inputs["obligations"][0]["scope"]["period"] = "prior"
        program["direct_bindings"][0]["candidate_id"] = "candidate-b"
        validation["selected_candidate_ids"].append("candidate-b")
        self.assertFalse(envelope.matches_execution_content(**inputs))
        self.assertFalse(envelope.matches_program(program))
        self.assertFalse(envelope.matches_validation(validation))
        self.assertEqual(envelope.to_projection(), frozen_projection)
        self.assertFalse(hasattr(envelope, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            envelope.execution_content_fingerprint = "changed"
        with self.assertRaisesRegex(ValueError, "must be non-empty"):
            replace(envelope, execution_content_fingerprint="")


class ExecutionContentBoundaryTests(unittest.TestCase):
    def _compiled_fixture(self):
        from src.agent.financial_calculation_execution import (
            validate_semantic_calculation_program,
        )
        from src.agent.financial_reconciliation_candidates import (
            semantic_candidate_catalog_fingerprint,
        )
        from tests.semantic_program_test_support import (
            _binding,
            _candidate,
            _obligation,
            _requirement,
        )

        catalog = [_candidate("candidate-a", 10)]
        obligations = [
            _obligation(
                "first",
                "derived_value",
                "scaled quantity",
                evidence_requirements=[_requirement("input", "quantity")],
            )
        ]
        inputs = {
            "candidate_catalog": catalog,
            "obligations": obligations,
            "query": "Multiply the source value by 100.",
        }
        program = {
            "status": "ready",
            "expressions": [{
                "obligation_id": "first",
                "variable_bindings": [_binding("X", "candidate-a", "input")],
                "formula": "X * 100",
                "result_unit": "items",
                "source_display_candidate_id": None,
                "source_display_reason": "No source-stated result is available.",
            }],
        }
        visibility = CandidateVisibilityV1.create(
            catalog_fingerprint=semantic_candidate_catalog_fingerprint(catalog),
            visible_candidate_ids=["candidate-a"],
            candidate_ids_by_owner={"first": ["candidate-a"], "input": ["candidate-a"]},
        )
        validation = validate_semantic_calculation_program(
            program=program, candidate_visibility=visibility, **inputs
        )
        self.assertEqual(validation["status"], "ready", validation["errors"])
        return program, inputs, CompilationEnvelopeV2.create(
            visibility=visibility, program=program, validation=validation, **inputs
        )

    def test_matching_inputs_reach_formula_execution(self) -> None:
        from src.agent.financial_calculation_execution import (
            execute_semantic_calculation_program,
        )
        from src.agent.financial_formula_eval import safe_eval_formula

        program, inputs, envelope = self._compiled_fixture()
        with patch(
            "src.agent.financial_calculation_execution.safe_eval_formula",
            wraps=safe_eval_formula,
        ) as evaluator:
            result = execute_semantic_calculation_program(
                program=program,
                compilation_envelope=envelope,
                require_compilation_envelope=True,
                **inputs,
            )
        self.assertEqual(result["status"], "ok", result["validation"]["errors"])
        self.assertEqual(result["outputs_by_obligation"]["first"]["normalized_value"], 1000)
        evaluator.assert_called_once()

    def test_content_mutations_stop_before_validation_and_arithmetic(self) -> None:
        from src.agent.financial_calculation_execution import (
            execute_semantic_calculation_program,
        )

        program, inputs, envelope = self._compiled_fixture()
        mutations = {
            "normalized_value": 10_000_000.0,
            "normalized_unit": "USD",
            "company": "other company",
            "period": "prior",
            "consolidation_scope": "consolidated",
            "basis": "other basis",
            "source_text": "a different source sentence",
            "source_span": [0, 2],
            "source_bundle_text": "different exact source",
            "source_bundle_value_span": [1, 2],
            "source_bundle_context_span": [4, 20],
            "physical_table_id": "other-table",
            "physical_row_id": "other-row",
            "physical_cell_id": "other-cell",
            "context_fingerprint": "other-context",
        }
        cases = []
        for field, value in mutations.items():
            changed = deepcopy(inputs)
            changed["candidate_catalog"][0][field] = value
            cases.append((field, changed, "execution_content_mismatch"))
        changed_query = deepcopy(inputs)
        changed_query["query"] += " "
        cases.append(("query", changed_query, "execution_content_mismatch"))
        changed_obligations = deepcopy(inputs)
        changed_obligations["obligations"][0]["scope"]["period"] = "prior"
        cases.append(("obligations", changed_obligations, "execution_content_mismatch"))
        changed_raw = deepcopy(inputs)
        changed_raw["candidate_catalog"][0]["raw_value"] = "20"
        cases.append(("raw_value", changed_raw, "visibility_mismatch"))

        for field, changed, error_code in cases:
            with self.subTest(field=field), patch(
                "src.agent.financial_calculation_execution.validate_semantic_calculation_program",
                side_effect=AssertionError("changed content reached validation"),
            ) as validator, patch(
                "src.agent.financial_calculation_execution.safe_eval_formula",
                side_effect=AssertionError("changed content reached arithmetic"),
            ) as evaluator:
                result = execute_semantic_calculation_program(
                    program=program,
                    compilation_envelope=envelope,
                    require_compilation_envelope=True,
                    **changed,
                )
                self.assertEqual(result["outputs"], [])
                self.assertIn(
                    error_code,
                    {error["code"] for error in result["validation"]["errors"]},
                )
                validator.assert_not_called()
                evaluator.assert_not_called()

    def test_legacy_envelope_projection_cannot_enter_execution(self) -> None:
        from src.agent.financial_calculation_execution import (
            execute_semantic_calculation_program,
        )

        program, inputs, envelope = self._compiled_fixture()
        legacy_projection = envelope.to_projection()
        legacy_projection["schema_version"] = "compilation_envelope_v1"
        legacy_projection.pop("execution_content_fingerprint")
        with patch(
            "src.agent.financial_calculation_execution.validate_semantic_calculation_program",
            side_effect=AssertionError("legacy authority reached validation"),
        ) as validator, patch(
            "src.agent.financial_calculation_execution.safe_eval_formula",
            side_effect=AssertionError("legacy authority reached arithmetic"),
        ) as evaluator:
            result = execute_semantic_calculation_program(
                program=program,
                compilation_envelope=legacy_projection,
                require_compilation_envelope=True,
                **inputs,
            )
        self.assertEqual(result["outputs"], [])
        self.assertIn(
            "execution_content_mismatch",
            {error["code"] for error in result["validation"]["errors"]},
        )
        validator.assert_not_called()
        evaluator.assert_not_called()


if __name__ == "__main__":
    unittest.main()
