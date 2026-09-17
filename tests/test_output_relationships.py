from copy import deepcopy
import unittest

from src.agent.financial_graph_calculation import (
    _retry_candidate_exclusions, _semantic_candidate_visibility, build_semantic_compilation_islands,
)
from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_graph_models import SemanticCalculationProgram
from tests.narrative_address_test_support import selection
from tests.semantic_program_test_support import _obligation, _candidate
from tests.test_numeric_subject_authority import authored_interpretation


def relate(owners, query="Use a common basis."):
    relation = {"kind": "shared_basis", "output_ids": [row["obligation_id"] for row in owners],
                "request_unit_id": "request_001", "request_text": query}
    return [{**row, "output_relationships": [deepcopy(relation)]} for row in owners]


class OutputRelationshipTests(unittest.TestCase):
    def test_shared_topic_does_not_connect_but_request_relation_does(self):
        owners = [_obligation("a", "direct_value", "same topic"), _obligation("b", "direct_value", "same topic")]
        self.assertEqual(len(build_semantic_compilation_islands(owners)["islands"]), 2)
        connected = build_semantic_compilation_islands(relate(owners), query="Use a common basis.")
        self.assertEqual(len(connected["islands"]), 1)
        self.assertTrue(connected["islands"][0]["output_relationships"])

    def test_unknown_self_and_ungrounded_relations_block_before_calls(self):
        owners = relate([_obligation("a", "direct_value", "first"), _obligation("b", "direct_value", "second")])
        for field, value in (("output_ids", ["a", "unknown"]), ("output_ids", ["a", "a"]),
                             ("request_text", "Invented request"), ("request_unit_id", "request_002")):
            changed = deepcopy(owners)
            for owner in changed:
                owner["output_relationships"][0][field] = value
            with self.subTest(field=field, value=value):
                plan = build_semantic_compilation_islands(changed, query="Use a common basis.")
                self.assertEqual(plan["status"], "invalid")
                self.assertTrue(all(island["errors"] for island in plan["islands"]))

    def test_legacy_grouping_is_not_silently_accepted(self):
        owner = _obligation("a", "direct_value", "first", coupling_key="arbitrary")
        plan = build_semantic_compilation_islands([owner])
        self.assertEqual(plan["status"], "invalid")
        self.assertEqual(plan["islands"][0]["errors"][0]["repair_action"], "repair_requirements")

    def test_relation_cannot_borrow_a_request_unit_not_owned_by_every_member(self):
        owners = relate([_obligation('a', 'direct_value', 'first'), _obligation('b', 'direct_value', 'second')])
        owners[1]['request_unit_ids'] = ['request_002']
        plan = build_semantic_compilation_islands(owners, query='Use a common basis.\nReport another value.')
        self.assertEqual(plan['status'], 'invalid')
        self.assertTrue(any(error['code'] == 'ungrounded_output_relationship'
            for island in plan['islands'] for error in island['errors']))

    def test_basis_interpretation_is_distinct_from_physical_table_identity(self):
        owners = relate([_obligation("a", "direct_value", "first"), _obligation("b", "direct_value", "second")])
        catalog = [_candidate("ca", 9, context="table-a"), _candidate("cb", 9, context="table-b")]
        bindings = [{"obligation_id": row["obligation_id"], "candidate_id": candidate["candidate_id"],
            "source_interpretation": {**authored_interpretation(candidate, "Maple"), "scope": {"basis": "reported scope"}}}
            for row, candidate in zip(owners, catalog)]
        result = validate_semantic_calculation_program(program={"direct_bindings": bindings}, obligations=owners,
            candidate_catalog=catalog, query="Use a common basis.")
        self.assertEqual(result["status"], "ready", result["errors"])
        bindings[1]["source_interpretation"]["scope"]["basis"] = "different declaration"
        result = validate_semantic_calculation_program(program={"direct_bindings": bindings}, obligations=owners,
            candidate_catalog=catalog, query="Use a common basis.")
        self.assertEqual(result["status"], "invalid")
        self.assertIn("relationship_interpretation_missing_or_inconsistent", [row["code"] for row in result["errors"]])


class SharedBasisDeclarationTests(unittest.TestCase):
    """Declaration agreement, source linkage and semantic meaning are separate."""

    query = "Use a common basis."
    basis = "Reported delivery methods."

    def setUp(self):
        self.owners = relate([_obligation("a", "narrative", "First method"),
            _obligation("b", "narrative", "Second method")])
        self.catalog = []
        self.program = {"narrative_bindings": []}
        for owner_id, subject in (("a", "Birch"), ("b", "Cedar")):
            candidate_id = "source_" + owner_id
            text = f"{subject} uses local delivery."
            self.catalog.append({**_candidate(candidate_id, 0, context="table-" + owner_id),
                "kind": "narrative", "raw_value": "", "raw_unit": "",
                "normalized_value": None, "normalized_unit": "UNKNOWN",
                "source_text": text, "source_bundle_text": text})
            link = selection(self.catalog, candidate_id, text)
            self.program["narrative_bindings"].append({"obligation_id": owner_id,
                "basis_interpretation": self.basis,
                "subject_bindings": [{"subject_binding_id": "s1", "subject": subject,
                    "evidence_selections": [deepcopy(link)]}],
                "claims": [{"subject_binding_id": "s1", "text": text,
                    "fact_evidence_selections": [deepcopy(link)]}]})
        self.allowed = {"a": ["source_a"], "b": ["source_b"]}

    def validate(self):
        before = deepcopy((self.program, self.owners, self.catalog))
        program = SemanticCalculationProgram.model_validate(self.program).model_dump()
        visibility = _semantic_candidate_visibility(self.catalog,
            visible_candidate_ids=[row["candidate_id"] for row in self.catalog],
            candidate_ids_by_owner=self.allowed)
        result = validate_semantic_calculation_program(program=program, obligations=self.owners,
            candidate_catalog=self.catalog, query=self.query, candidate_visibility=visibility,
            require_narrative_claims=True)
        self.assertEqual((self.program, self.owners, self.catalog), before)
        return result

    def assert_relationship_failure(self, code):
        result = self.validate()
        self.assertEqual(result["status"], "invalid", result["errors"])
        self.assertEqual([(row["obligation_id"], row["code"]) for row in result["errors"]],
            [("a", code), ("b", code)])
        self.assertEqual(result["valid_narrative_bindings"], [])
        self.assertEqual(result["valid_direct_bindings"], [])
        self.assertTrue(all(row["repair_action"] == "repair_program" for row in result["errors"]))
        self.assertEqual(_retry_candidate_exclusions(program=self.program,
            validation_errors=result["errors"], target_obligation_ids=["a", "b"]), {})

    def make_mixed(self):
        self.owners[0]["kind"] = "direct_value"
        self.catalog[0] = _candidate("source_a", 9, context="table-a")
        self.program["narrative_bindings"] = self.program["narrative_bindings"][1:]
        self.program["direct_bindings"] = [{"obligation_id": "a", "candidate_id": "source_a",
            "source_interpretation": {**authored_interpretation(self.catalog[0], "Birch"),
                "metric": "quantity", "scope": {"basis": self.basis}}}]

    def test_identical_narrative_declarations_allow_distinct_sources(self):
        result = self.validate()
        self.assertEqual(result["status"], "ready", result["errors"])
        self.assertEqual(result["source_candidate_ids_by_obligation"], self.allowed)
        self.assertEqual([row["basis_interpretation"] for row in result["valid_narrative_bindings"]],
            [self.basis, self.basis])

    def test_shared_prefix_paraphrase_and_layout_difference_are_not_agreement(self):
        for value in (self.basis + " One output has further detail.",
                      "Delivery methods as reported.", " " + self.basis, self.basis + "\n"):
            with self.subTest(value=value):
                self.program["narrative_bindings"][1]["basis_interpretation"] = value
                self.assert_relationship_failure("relationship_interpretation_missing_or_inconsistent")

    def test_absent_or_blank_declarations_fail_even_when_equal(self):
        for value in (None, "", " \n "):
            with self.subTest(value=value):
                for row in self.program["narrative_bindings"]:
                    if value is None:
                        row.pop("basis_interpretation", None)
                    else:
                        row["basis_interpretation"] = value
                self.assert_relationship_failure("relationship_interpretation_missing_or_inconsistent")

    def test_independent_outputs_do_not_require_agreement_or_matching_source_scope(self):
        for owner in self.owners:
            owner["output_relationships"] = []
        self.program["narrative_bindings"][1]["basis_interpretation"] = "A distinct interpretation."
        self.catalog[0]["consolidation_scope"] = "consolidated"
        self.catalog[1]["consolidation_scope"] = "separate"
        self.assertEqual(self.validate()["status"], "ready")

    def test_identical_unsupported_interpretations_do_not_prove_semantic_truth(self):
        # Deliberately wrong semantics: exact agreement is not source entailment.
        for row in self.program["narrative_bindings"]:
            row["basis_interpretation"] = "Both sources describe international delivery."
        self.assertEqual(self.validate()["status"], "ready")

    def test_equal_declarations_cannot_authorize_hidden_evidence(self):
        self.allowed["b"] = []
        result = self.validate()
        self.assertNotEqual(result["status"], "ready")
        self.assertIn("candidate_not_exposed_to_compiler", [row["code"] for row in result["errors"]])

    def test_equal_declarations_cannot_ground_an_unselected_subject(self):
        self.program["narrative_bindings"][1]["subject_bindings"][0]["subject"] = "Willow"
        result = self.validate()
        self.assertNotEqual(result["status"], "ready")
        self.assertIn("ungrounded_narrative_subject", [row["code"] for row in result["errors"]])

    def test_equal_declarations_cannot_override_an_owner_scope_conflict(self):
        self.owners[1]["scope"]["consolidation_scope"] = "consolidated"
        self.catalog[1]["consolidation_scope"] = "separate"
        result = self.validate()
        self.assertNotEqual(result["status"], "ready")
        self.assertIn("candidate_scope_mismatch", [row["code"] for row in result["errors"]])

    def test_equal_narrative_declarations_cannot_mix_known_source_scopes(self):
        self.catalog[0]["consolidation_scope"] = "consolidated"
        self.catalog[1]["consolidation_scope"] = "separate"
        self.assert_relationship_failure("relationship_source_scope_conflict")

    def test_equal_mixed_declarations_cannot_mix_known_source_scopes(self):
        self.make_mixed()
        self.catalog[0]["consolidation_scope"] = "consolidated"
        self.catalog[1]["consolidation_scope"] = "separate"
        self.assert_relationship_failure("relationship_source_scope_conflict")

    def test_unknown_scope_is_not_an_explicit_conflict(self):
        for mixed in (False, True):
            if mixed:
                self.make_mixed()
            for scope in ("unknown", "consolidated"):
                with self.subTest(mixed=mixed, scope=scope):
                    self.catalog[0]["consolidation_scope"] = "consolidated"
                    self.catalog[1]["consolidation_scope"] = scope
                    self.assertEqual(self.validate()["status"], "ready")

    def test_mixed_outputs_compare_numeric_proof_with_narrative_declaration(self):
        self.make_mixed()
        self.assertEqual(self.validate()["status"], "ready")
        self.program["narrative_bindings"][0]["basis_interpretation"] = "Different declaration."
        self.assert_relationship_failure("relationship_interpretation_missing_or_inconsistent")


if __name__ == "__main__":
    unittest.main()
