"""Anonymous declaration/reference controls; authored replies are not model evidence."""
from copy import deepcopy
import json
import unittest

from jsonschema import Draft202012Validator

from src.agent.financial_calculation_execution import execute_semantic_calculation_program
from src.agent.financial_compiler_wire import CompilerReferencesV1, lower_compiler_response
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import (
    _merge_targeted_program_retry, _semantic_candidate_cohorts, _semantic_candidate_visibility,
)
from src.agent.financial_graph_models import SemanticCalculationProgram, compiler_response_model
from src.agent.financial_output_relationships import output_relationships
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.ops.compiler_fixture_transport import project_offline_program_to_wire
from src.utils.openai_structured import strict_openai_schema
from tests.narrative_address_test_support import selection
from tests.semantic_program_test_support import _obligation, _requirement, _StructuredQueueLLM
from tests.source_interpretation_fixture_support import authored_relationship_program
import tests.test_output_relationships as fixtures


def fixture():
    case = fixtures.SharedBasisDeclarationTests()
    case.setUp()
    return case


def wire_setup(case, *, active=None, frozen=None):
    owners = case.owners if active is None else [row for row in case.owners if row["obligation_id"] in active]
    plan = _semantic_candidate_cohorts(case.catalog, case.owners)
    payload = FinancialAgent._semantic_program_prompt_payload(case.catalog, plan)
    refs = CompilerReferencesV1.build(case.catalog, case.owners, case.query, payload)
    visibility = _semantic_candidate_visibility(case.catalog,
        visible_candidate_ids=[row["candidate_id"] for row in case.catalog], candidate_ids_by_owner=case.allowed)
    model = compiler_response_model(owners, refs, visibility, read_only_relationship_declarations=frozen)
    return owners, refs, visibility, model


def lowered(case, wire, setup):
    owners, refs, visibility, model = setup
    return lower_compiler_response(wire, model=model, refs=refs, visibility=visibility,
        obligations=owners, catalog=case.catalog)


def compile_fixture(case, *programs):
    agent = FinancialAgent.__new__(FinancialAgent)
    agent.llm = _StructuredQueueLLM(*(SemanticCalculationProgram.model_validate(row) for row in programs))
    result = agent._compile_semantic_calculation_program({"query": case.query, "answer_obligations": case.owners,
        "semantic_candidate_catalog_prebuilt": True, "semantic_source_candidates": case.catalog,
        "semantic_candidate_catalog": case.catalog, "include_debug_bundle": True})
    return result, agent.llm


def add_third(case):
    text = "Willow uses scheduled delivery."
    candidate = {**deepcopy(case.catalog[1]), "candidate_id": "source_c", "source_candidate_id": "source-c",
        "source_row_id": "row-c", "context_fingerprint": "table-c", "table_source_id": "table-c",
        "source_text": text, "source_bundle_text": text}
    case.catalog.append(candidate)
    case.owners.append(_obligation("c", "narrative", "Third method"))
    case.allowed["c"] = ["source_c"]
    link = selection(case.catalog, "source_c", text)
    case.program["narrative_bindings"].append({"obligation_id": "c", "basis_interpretation": "Third local context.",
        "subject_bindings": [{"subject_binding_id": "s1", "subject": "Willow", "evidence_selections": [link]}],
        "claims": [{"subject_binding_id": "s1", "text": text, "fact_evidence_selections": [deepcopy(link)]}]})


class SharedBasisCompilerTests(unittest.TestCase):
    def test_wire_declares_once_and_preserves_different_local_interpretations(self):
        case = fixture()
        case.program["narrative_bindings"][0]["basis_interpretation"] = "First local context."
        case.program["narrative_bindings"][1]["basis_interpretation"] = "Second local context."
        setup = wire_setup(case)
        wire = project_offline_program_to_wire(case.program, setup[-1])
        self.assertEqual(wire["relationship_declarations"], case.program["relationship_declarations"])
        self.assertEqual(len(wire["relationship_declarations"]), 1)
        for owner in ("a", "b"):
            self.assertEqual(wire["outputs"][owner]["result"]["relationship_refs"],
                case.program["relationship_bindings"][owner])
        # The actual strict transport schema accepts the fully explicit model dump.
        explicit = setup[-1].model_validate(wire).model_dump()
        Draft202012Validator(strict_openai_schema(setup[-1])).validate(explicit)
        result = lowered(case, wire, setup)
        self.assertEqual(result, SemanticCalculationProgram.model_validate(case.program).model_dump())
        case.program = result
        self.assertEqual(case.validate()["status"], "ready")

    def test_schema_has_only_owned_relationship_refs_and_no_unrelated_fields(self):
        case = fixture()
        add_third(case)
        _, _, _, model = wire_setup(case)
        schema = model.model_json_schema()
        related = schema["$defs"]["Related_a"]["properties"]["relationship_refs"]["items"]["enum"]
        self.assertEqual(related, list(case.program["relationship_declarations"]))
        self.assertNotIn("relationship_refs", schema["$defs"]["Narrative_c"]["properties"])
        for owner in case.owners:
            owner["output_relationships"] = []
        self.assertNotIn("relationship_declarations", wire_setup(case)[-1].model_fields)

    def test_missing_declaration_is_not_reconstructed_from_local_text(self):
        case = fixture()
        setup = wire_setup(case)
        wire = project_offline_program_to_wire(case.program, setup[-1])
        wire.pop("relationship_declarations")
        with self.assertRaises(ValueError):
            lowered(case, wire, setup)
        case.program.pop("relationship_declarations")
        self.assertIn("relationship_declaration_missing", [row["code"] for row in case.validate()["errors"]])

    def test_missing_duplicate_foreign_or_unowned_reference_fails_same_cohort(self):
        for change in ([], ["unknown"], None, "not-a-list"):
            with self.subTest(change=change):
                case = fixture()
                case.program["relationship_bindings"]["b"] = change
                # Raw validator boundary must fail safely even before typed parsing.
                from src.agent.financial_calculation_execution import validate_semantic_calculation_program
                raw = deepcopy(case.program)
                base = SemanticCalculationProgram.model_validate({key: value for key, value in raw.items()
                    if key != "relationship_bindings"}).model_dump()
                base["relationship_bindings"] = raw["relationship_bindings"]
                result = validate_semantic_calculation_program(program=base, obligations=case.owners,
                    candidate_catalog=case.catalog, query=case.query, require_narrative_claims=True)
                self.assertEqual(result["status"], "invalid")
                self.assertIn("relationship_reference_missing_or_invalid", [row["code"] for row in result["errors"]])
        case = fixture()
        case.program["relationship_bindings"]["b"] *= 2
        self.assertEqual(case.validate()["status"], "invalid")
        add_third(case)
        case.program["relationship_bindings"]["c"] = case.program["relationship_bindings"]["a"][:]
        self.assertNotEqual(case.validate()["status"], "ready")

    def test_unknown_declaration_and_unknown_binding_owner_fail_closed(self):
        for key in ("relationship_declarations", "relationship_bindings"):
            case = fixture()
            case.program[key]["unknown"] = "invented" if key.endswith("declarations") else []
            self.assertEqual(case.validate()["status"], "invalid")

    def test_shared_declaration_cannot_replace_numeric_source_interpretation(self):
        for relation_on_numeric_owner in (True, False):
            with self.subTest(relation_on_numeric_owner=relation_on_numeric_owner):
                case = fixture()
                case.make_mixed()
                if not relation_on_numeric_owner:
                    # A valid relationship may be declared by only one member.
                    case.owners[0].pop("output_relationships")
                self.assertEqual(case.validate()["status"], "ready")
                case.program["direct_bindings"][0].pop("source_interpretation")
                self.assertIn("missing_source_interpretation", [row["code"] for row in case.validate()["errors"]])

    def test_overlapping_relations_retain_independent_declarations(self):
        case = fixture()
        add_third(case)
        second = {"kind": "shared_basis", "output_ids": ["b", "c"],
            "request_unit_id": "request_001", "request_text": case.query}
        for owner in case.owners[1:]:
            owner.setdefault("output_relationships", []).append(deepcopy(second))
        case.program.pop("relationship_declarations")
        case.program.pop("relationship_bindings")
        case.program = authored_relationship_program(case.program, case.owners, case.query)
        for index, key in enumerate(case.program["relationship_declarations"]):
            case.program["relationship_declarations"][key] = f"Distinct common interpretation {index}."
        self.assertEqual(len(case.program["relationship_bindings"]["b"]), 2)
        result, queue = compile_fixture(case, case.program)
        self.assertEqual(result["semantic_program_validation"]["status"], "ready", result["planner_debug_trace"])
        self.assertEqual(len(queue.prompts), 1)
        self.assertEqual(result["semantic_program"]["relationship_declarations"], case.program["relationship_declarations"])
        self.assertEqual(result["semantic_program"]["relationship_bindings"], case.program["relationship_bindings"])

    def test_abstention_needs_no_invented_declaration_or_extra_call(self):
        case = fixture()
        case.program["status"] = "incomplete"
        case.program["narrative_bindings"] = []
        case.program["missing_obligation_ids"] = ["a", "b"]
        case.program["relationship_bindings"] = {}
        case.program["relationship_declarations"] = {key: None for key in case.program["relationship_declarations"]}
        result, queue = compile_fixture(case, case.program)
        self.assertEqual(len(queue.prompts), 1)
        self.assertEqual(result["semantic_program_validation"]["errors"], [])
        self.assertEqual(result["semantic_program_validation"]["missing_obligation_ids"], ["a", "b"])

    def test_partial_source_repair_freezes_declaration_and_accepted_output(self):
        case = fixture()
        initial = deepcopy(case.program)
        initial["narrative_bindings"][1]["subject_bindings"][0]["subject"] = "Unselected name"
        retry = deepcopy(case.program)
        retry["narrative_bindings"] = retry["narrative_bindings"][1:]
        retry["relationship_bindings"].pop("a")
        retry["relationship_declarations"] = {}  # The accepted declaration is supplied read-only.
        result, queue = compile_fixture(case, initial, retry)
        self.assertEqual(result["semantic_program_validation"]["status"], "ready", result["planner_debug_trace"])
        self.assertEqual(len(queue.prompts), 2)
        self.assertEqual(result["semantic_program"]["narrative_bindings"][0],
            SemanticCalculationProgram.model_validate(initial).model_dump()["narrative_bindings"][0])
        self.assertNotIn("relationship_declarations", queue.model_instances[1].model_fields)
        text = queue.prompts[1].to_messages()[0].content
        scope = json.JSONDecoder().raw_decode(text.split("Compilation scope:\n", 1)[1])[0]
        self.assertEqual(scope["active_obligation_ids"], ["b"])
        self.assertEqual(scope["read_only_relationship_declarations"], case.program["relationship_declarations"])
        self.assertEqual(scope["output_relationships"], output_relationships(case.owners, case.query)[0])
        self.assertEqual(result["semantic_program"]["relationship_declarations"], case.program["relationship_declarations"])

    def test_retry_cannot_overwrite_a_declaration_used_by_an_accepted_member(self):
        case = fixture()
        validation = case.validate()
        replacement = deepcopy(case.program)
        key = next(iter(replacement["relationship_declarations"]))
        replacement["relationship_declarations"][key] = "Attempted overwrite."
        replacement["narrative_bindings"][0]["basis_interpretation"] = "Attempted accepted edit."
        result = _merge_targeted_program_retry(previous_validation=validation, retry_program=replacement,
            target_obligation_ids=["b"], previous_program=case.program)
        self.assertEqual(result["relationship_declarations"], case.program["relationship_declarations"])
        self.assertEqual(result["narrative_bindings"][0], case.program["narrative_bindings"][0])
        setup = wire_setup(case, active=["b"], frozen=case.program["relationship_declarations"])
        wire = project_offline_program_to_wire({**case.program,
            "narrative_bindings": case.program["narrative_bindings"][1:]}, setup[-1])
        wire["relationship_declarations"] = {key: "Attempted overwrite."}
        with self.assertRaises(ValueError):
            lowered(case, wire, setup)

    def test_multiple_islands_preserve_only_accepted_relationship_proofs(self):
        case = fixture()
        initial = deepcopy(case.program)
        add_third(case)
        third = {"narrative_bindings": [case.program["narrative_bindings"][-1]]}
        result, queue = compile_fixture(case, initial, third)
        self.assertEqual(result["semantic_program_validation"]["status"], "ready", result["planner_debug_trace"])
        self.assertEqual(len(queue.prompts), 2)
        self.assertEqual(result["semantic_program"]["relationship_bindings"], initial["relationship_bindings"])
        self.assertNotIn("relationship_declarations", queue.model_instances[1].model_fields)

    def test_bad_reference_retries_the_group_with_unchanged_candidates(self):
        case = fixture()
        initial = deepcopy(case.program)
        initial["relationship_bindings"]["b"] = ["foreign_relationship"]
        result, queue = compile_fixture(case, initial, case.program)
        self.assertEqual(result["semantic_program_validation"]["status"], "ready", result["planner_debug_trace"])
        self.assertEqual(len(queue.prompts), 2)
        payloads = []
        for prompt in queue.prompts:
            text = prompt.to_messages()[0].content
            scope = json.JSONDecoder().raw_decode(text.split("Compilation scope:\n", 1)[1])[0]
            self.assertEqual(scope["active_obligation_ids"], ["a", "b"])
            self.assertEqual(scope["read_only_relationship_declarations"], {})
            payloads.append(json.JSONDecoder().raw_decode(text.split(
                "Source bundles, candidate cohorts, and candidates_by_id:\n", 1)[1])[0])
        self.assertEqual(*payloads)

    def test_direct_and_derived_sources_retain_separate_interpretation_proofs(self):
        case = fixture()
        case.owners[0]["kind"], case.owners[1]["kind"] = "direct_value", "derived_value"
        case.owners[1]["evidence_requirements"] = [_requirement("b:quantity", "Quantity")]
        case.allowed["b:quantity"] = ["source_b"]
        case.catalog = [fixtures._candidate("source_a", 9), fixtures._candidate("source_b", 17, context="table-b")]
        proofs = [{**fixtures.authored_interpretation(candidate, "Birch"), "metric": "quantity",
                   "scope": {"basis": f"Local interpretation {index}."}}
                  for index, candidate in enumerate(case.catalog)]
        case.program["narrative_bindings"] = []
        case.program["direct_bindings"] = [{"obligation_id": "a", "candidate_id": "source_a",
                                            "source_interpretation": proofs[0]}]
        case.program["expressions"] = [{"obligation_id": "b", "formula": "B", "variable_bindings": [
            {"variable": "B", "source_id": "source_b", "source_requirement_id": "b:quantity",
             "source_interpretation": proofs[1]}],
            "source_display_candidate_id": None, "source_display_reason": "Requested calculated result."}]
        result, queue = compile_fixture(case, case.program)
        self.assertEqual(result["semantic_program_validation"]["status"], "ready", result["planner_debug_trace"])
        self.assertEqual(len(queue.prompts), 1)
        program = result["semantic_program"]
        self.assertEqual(program["direct_bindings"][0]["source_interpretation"]["scope"]["basis"], proofs[0]["scope"]["basis"])
        self.assertEqual(program["expressions"][0]["variable_bindings"][0]["source_interpretation"]["scope"]["basis"], proofs[1]["scope"]["basis"])

    def test_partial_abstention_preserves_the_ready_members_explicit_proof(self):
        case = fixture()
        case.program["status"] = "incomplete"
        case.program["narrative_bindings"] = case.program["narrative_bindings"][:1]
        case.program["missing_obligation_ids"] = ["b"]
        case.program["relationship_bindings"].pop("b")
        result, queue = compile_fixture(case, case.program)
        self.assertEqual(len(queue.prompts), 1)
        self.assertEqual(result["semantic_program_validation"]["errors"], [])
        self.assertEqual(result["semantic_program_validation"]["missing_obligation_ids"], ["b"])
        self.assertEqual(result["semantic_program"]["relationship_declarations"], case.program["relationship_declarations"])

    def test_recomputed_validation_binds_the_declaration_and_original_request(self):
        case = fixture()
        case.program = SemanticCalculationProgram.model_validate(case.program).model_dump()
        validation = case.validate()
        _, _, visibility, _ = wire_setup(case)
        changed = deepcopy(validation)
        key = next(iter(changed["valid_relationship_declarations"]))
        changed["valid_relationship_declarations"][key] = "Invented validation."
        envelope = CompilationEnvelopeV2.create(program=case.program, validation=changed,
            visibility=visibility, candidate_catalog=case.catalog, obligations=case.owners, query=case.query)
        result = execute_semantic_calculation_program(program=case.program, obligations=case.owners,
            candidate_catalog=case.catalog, query=case.query, compilation_envelope=envelope,
            require_compilation_envelope=True)
        self.assertEqual(result["outputs"], [])
        self.assertIn("validation_drift", [row["code"] for row in result["validation"]["errors"]])
        envelope = CompilationEnvelopeV2.create(program=case.program, validation=validation,
            visibility=visibility, candidate_catalog=case.catalog, obligations=case.owners, query=case.query)
        owners = deepcopy(case.owners)
        owners[0]["output_relationships"][0]["request_text"] = "Use a common"
        result = execute_semantic_calculation_program(program=case.program, obligations=owners,
            candidate_catalog=case.catalog, query=case.query, compilation_envelope=envelope,
            require_compilation_envelope=True)
        self.assertEqual(result["outputs"], [])
        self.assertIn("execution_content_mismatch", [row["code"] for row in result["validation"]["errors"]])

    def test_v2_binds_declaration_references_and_validation(self):
        case = fixture()
        case.program = SemanticCalculationProgram.model_validate(case.program).model_dump()
        validation = case.validate()
        _, _, visibility, _ = wire_setup(case)
        envelope = CompilationEnvelopeV2.create(program=case.program, validation=validation,
            visibility=visibility, candidate_catalog=case.catalog, obligations=case.owners, query=case.query)
        baseline = execute_semantic_calculation_program(program=case.program, obligations=case.owners,
            candidate_catalog=case.catalog, query=case.query, compilation_envelope=envelope,
            require_compilation_envelope=True)
        self.assertEqual(baseline["status"], "ok", baseline["validation"]["errors"])
        for field in ("relationship_declarations", "relationship_bindings"):
            changed = deepcopy(case.program)
            key = next(iter(changed[field]))
            changed[field][key] = "Changed interpretation" if field.endswith("declarations") else []
            result = execute_semantic_calculation_program(program=changed, obligations=case.owners,
                candidate_catalog=case.catalog, query=case.query, compilation_envelope=envelope,
                require_compilation_envelope=True)
            self.assertEqual(result["validation"]["status"], "invalid")
            self.assertTrue(any(row["code"] == "validation_drift" for row in result["validation"]["errors"]))
            self.assertFalse(result["validation"].get("valid_relationship_declarations"))


if __name__ == "__main__":
    unittest.main()
