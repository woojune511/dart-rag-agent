"""Synthetic authority counterexamples, independent of reviewed benchmark cases."""

from copy import deepcopy
import json
import unittest

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program,
    validate_semantic_calculation_program,
)
from src.agent.financial_formula_eval import safe_eval_formula
from src.agent.financial_graph_calculation import (
    _merge_targeted_program_retry,
    _semantic_candidate_visibility,
)
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from tests.semantic_program_test_support import (
    _binding, _candidate, _obligation, _requirement, _source_assertions,
)


def _expression(owner, source):
    return {
        "obligation_id": owner,
        "formula": "x",
        "variable_bindings": [_binding("x", source)],
        "source_display_candidate_id": None,
        "source_display_reason": "No independently reported result is selected.",
    }


def _validate(program, obligations, catalog):
    return validate_semantic_calculation_program(
        program=program, obligations=obligations, candidate_catalog=catalog,
        query="Return the requested outputs.",
    )


class DeclaredDependencyAuthorityTests(unittest.TestCase):
    def test_undeclared_output_cannot_become_an_expression_input(self):
        catalog = [_candidate("fact", 7)]
        obligations = [
            _obligation("reported", "direct_value", "reported"),
            _obligation("computed", "derived_value", "computed"),
        ]
        program = {
            "status": "ready",
            "direct_bindings": [{"obligation_id": "reported", "candidate_id": "fact"}],
            "expressions": [_expression("computed", "reported")],
        }
        visibility = _semantic_candidate_visibility(
            catalog, visible_candidate_ids=["fact"],
            candidate_ids_by_owner={"reported": ["fact"], "computed": []},
        )
        inputs = dict(program=program, obligations=obligations, candidate_catalog=catalog,
                      query="Return the requested outputs.")
        validation = validate_semantic_calculation_program(**inputs, candidate_visibility=visibility)
        error = next(item for item in validation["errors"]
                     if item["code"] == "undeclared_expression_dependency")
        self.assertEqual(error["obligation_id"], "computed")
        self.assertEqual(error["location"], "expression_input.source_id")
        self.assertEqual(error["repair_action"], "repair_program")
        self.assertEqual(error["candidate_id"], "")
        envelope = CompilationEnvelopeV2.create(
            visibility=visibility, validation=validation, **inputs,
        )
        execution = execute_semantic_calculation_program(
            **inputs, compilation_envelope=envelope, require_compilation_envelope=True,
        )
        self.assertEqual(list(execution["outputs_by_obligation"]), ["reported"])

    def test_declared_dependency_executes_without_borrowing_candidate_visibility(self):
        catalog = [_candidate("fact", 7)]
        obligations = [
            _obligation("reported", "direct_value", "reported"),
            _obligation("computed", "derived_value", "computed", depends_on=["reported"]),
        ]
        program = {
            "status": "ready",
            "direct_bindings": [{"obligation_id": "reported", "candidate_id": "fact"}],
            "expressions": [_expression("computed", "reported")],
        }
        visibility = _semantic_candidate_visibility(
            catalog, visible_candidate_ids=["fact"],
            candidate_ids_by_owner={"reported": ["fact"], "computed": []},
        )
        inputs = dict(program=program, obligations=obligations, candidate_catalog=catalog,
                      query="Return the requested outputs.")
        validation = validate_semantic_calculation_program(**inputs, candidate_visibility=visibility)
        self.assertEqual(validation["errors"], [])
        envelope = CompilationEnvelopeV2.create(visibility=visibility, validation=validation, **inputs)
        execution = execute_semantic_calculation_program(
            **inputs, compilation_envelope=envelope, require_compilation_envelope=True,
        )
        self.assertEqual(execution["outputs_by_obligation"]["computed"]["normalized_value"], 7)

    def test_transitive_peer_is_not_an_implicit_direct_dependency(self):
        catalog = [_candidate("fact", 7)]
        obligations = [
            _obligation("reported", "direct_value", "reported"),
            _obligation("middle", "derived_value", "middle", depends_on=["reported"]),
            _obligation("last", "derived_value", "last", depends_on=["middle"]),
        ]
        program = {
            "status": "ready",
            "direct_bindings": [{"obligation_id": "reported", "candidate_id": "fact"}],
            "expressions": [_expression("middle", "reported"), _expression("last", "reported")],
        }
        validation = _validate(program, obligations, catalog)
        self.assertEqual([item["obligation_id"] for item in validation["valid_expressions"]], ["middle"])
        self.assertIn("undeclared_expression_dependency", {item["code"] for item in validation["errors"]})


class RestrictedFormulaAuditTests(unittest.TestCase):
    def _inputs(self, formula, *, variables=("x",)):
        return {
            "program": {"status": "ready", "expressions": [{
                **_expression("result", "unused"), "formula": formula,
                "variable_bindings": [_binding(variable, f"fact_{index}", f"input_{index}")
                                      for index, variable in enumerate(variables)],
            }]},
            "obligations": [_obligation("result", "derived_value", "result", evidence_requirements=[
                _requirement(f"input_{index}", f"input {index}") for index in range(len(variables))
            ])],
            "candidate_catalog": [_candidate(f"fact_{index}", index + 7) for index in range(len(variables))],
            "query": "Return the requested result.",
        }

    def test_function_identifier_does_not_hide_same_named_variable(self):
        inputs = self._inputs("max(max, x)", variables=("max", "x"))
        execution = execute_semantic_calculation_program(**inputs)
        self.assertEqual(execution["validation"]["errors"], [])
        self.assertEqual(execution["outputs_by_obligation"]["result"]["normalized_value"], 8)

    def test_boolean_is_not_an_authorized_numeric_constant(self):
        execution = execute_semantic_calculation_program(**self._inputs("x * True"))
        self.assertIn("unsupported_formula_ast", {item["code"] for item in execution["validation"]["errors"]})
        self.assertEqual(execution["outputs_by_obligation"], {})
        with self.assertRaises(ValueError):
            safe_eval_formula("x * True", {"x": 7})

    def test_nonfinite_and_unrepresentable_numeric_literals_are_rejected_before_execution(self):
        for literal in ("1e309", "9" * 400):
            with self.subTest(literal=literal[:12]):
                inputs = self._inputs(f"x * {literal}")
                validation = validate_semantic_calculation_program(**inputs)
                self.assertIn("unsupported_formula_ast", {item["code"] for item in validation["errors"]})
                with self.assertRaises(ValueError):
                    safe_eval_formula(f"x * {literal}", {"x": 7})

    def test_noniterable_single_argument_extrema_fail_validation_not_execution(self):
        for function in ("min", "max"):
            with self.subTest(function=function):
                execution = execute_semantic_calculation_program(**self._inputs(f"{function}(x)"))
                self.assertEqual(execution["outputs_by_obligation"], {})
                self.assertEqual(execution["execution_errors"], [])
                error = next(item for item in execution["validation"]["errors"]
                             if item["code"] == "unsupported_formula_ast")
                self.assertEqual(error["repair_action"], "repair_program")


class TargetedAssertionAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [
            {**_candidate("fact_a", 7), "candidate_kind": "sentence_value", "table_source_id": "",
             "source_text": "The first source reports 7 items."},
            {**_candidate("fact_b", 13), "candidate_kind": "sentence_value", "table_source_id": "",
             "source_text": "The second source reports 13 items."},
        ]
        self.obligations = [_obligation(owner, "direct_value", owner)
                            for owner in ("first", "second")]
        self.previous = _validate({
            "status": "incomplete",
            "direct_bindings": [{"obligation_id": "first", "candidate_id": "fact_a"}],
            "source_assertions": _source_assertions(self.catalog, "fact_a"),
            "missing_obligation_ids": ["second"],
        }, self.obligations, self.catalog)
        self.retry = {
            "status": "ready",
            "direct_bindings": [{"obligation_id": "second", "candidate_id": "fact_b"}],
            "source_assertions": _source_assertions(self.catalog, "fact_b"),
        }

    def _assert_accepted_first_survives(self):
        before = deepcopy(self.previous)
        merged = _merge_targeted_program_retry(
            previous_validation=self.previous, retry_program=self.retry,
            target_obligation_ids=["second"],
        )
        validation = _validate(merged, self.obligations, self.catalog)
        self.assertEqual(self.previous, before)
        self.assertEqual([item["obligation_id"] for item in validation["valid_direct_bindings"]],
                         ["first", "second"])
        protected = {key: value for key, value in self.previous["valid_source_assertions"][0].items()
                     if key not in {"assertion_fingerprint", "covered_obligation_ids"}}
        self.assertEqual(json.dumps(merged["source_assertions"][0]), json.dumps(protected))

    def test_retry_cannot_attach_an_unowned_assertion_error_to_every_output(self):
        self.retry["source_assertions"].append({
            "source_bundle_id": "invented_bundle", "candidate_ids": ["invented_candidate"],
            "evidence_text": "An invented source.",
        })
        self._assert_accepted_first_survives()

    def test_retry_cannot_reassert_an_accepted_owner_with_different_source_text(self):
        assertion = _source_assertions(self.catalog, "fact_a")[0]
        self.retry["source_assertions"].append({**assertion, "evidence_text": "Changed source."})
        self._assert_accepted_first_survives()

    def test_invalid_target_assertion_still_rejects_only_the_target(self):
        self.retry["source_assertions"][0]["evidence_text"] = "Changed target source."
        merged = _merge_targeted_program_retry(
            previous_validation=self.previous, retry_program=self.retry,
            target_obligation_ids=["second"],
        )
        validation = _validate(merged, self.obligations, self.catalog)
        self.assertEqual([item["obligation_id"] for item in validation["valid_direct_bindings"]], ["first"])
        self.assertIn("source_assertion_text_mismatch", {item["code"] for item in validation["errors"]})

    def test_assertion_for_an_invalid_target_binding_does_not_revoke_accepted_output(self):
        self.retry["direct_bindings"][0]["candidate_id"] = "unknown_fact"
        self.retry["source_assertions"] = [{
            "source_bundle_id": "unknown_bundle", "candidate_ids": ["unknown_fact"],
            "evidence_text": "Unknown source.",
        }]
        merged = _merge_targeted_program_retry(
            previous_validation=self.previous, retry_program=self.retry,
            target_obligation_ids=["second"],
        )
        validation = _validate(merged, self.obligations, self.catalog)
        self.assertEqual([item["obligation_id"] for item in validation["valid_direct_bindings"]], ["first"])
        self.assertEqual({item["obligation_id"] for item in validation["errors"]}, {"second"})

    def test_shared_assertion_drops_replaced_target_members_not_preserved_evidence(self):
        shared = "The source reports 7 items and 13 items."
        for candidate in self.catalog:
            candidate.update(source_text=shared, source_candidate_id="one-source", evidence_id="one-source")
        previous_program = {
            "status": "ready",
            "direct_bindings": [
                {"obligation_id": "first", "candidate_id": "fact_a"},
                {"obligation_id": "second", "candidate_id": "fact_b"},
            ],
            "source_assertions": _source_assertions(self.catalog, "fact_a", "fact_b"),
        }
        self.catalog.append({
            **_candidate("fact_c", 17), "candidate_kind": "sentence_value", "table_source_id": "",
            "source_text": "Another source reports 17 items.",
        })
        previous = _validate(previous_program, self.obligations, self.catalog)
        self.assertEqual(len(previous["valid_source_assertions"]), 1)
        retry = {
            "status": "ready",
            "direct_bindings": [{"obligation_id": "second", "candidate_id": "fact_c"}],
            "source_assertions": _source_assertions(self.catalog, "fact_c"),
        }
        merged = _merge_targeted_program_retry(
            previous_validation=previous, retry_program=retry, target_obligation_ids=["second"],
        )
        validation = _validate(merged, self.obligations, self.catalog)
        self.assertEqual(validation["errors"], [])
        self.assertEqual(merged["source_assertions"][0]["candidate_ids"], ["fact_a"])
        self.assertEqual(merged["source_assertions"][0]["evidence_text"], shared)


if __name__ == "__main__":
    unittest.main()
