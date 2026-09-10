"""Narrative evidence bindings are written once; IDs are deterministic projection."""

from copy import deepcopy
import json
import unittest

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program, validate_semantic_calculation_program,
)
from src.agent.financial_graph_calculation import _semantic_candidate_visibility
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.semantic_program_test_support import _candidate, _obligation, _requirement, _scope, _StructuredQueueLLM, _with_narrative_claims


class SemanticNarrativeProjectionTests(unittest.TestCase):
    def setUp(self):
        scope = _scope(company="sample", period="2024", consolidation_scope="consolidated")
        self.obligations = [_obligation("summary", "narrative", "Summarize both activities.", scope=scope,
            evidence_requirements=[{**_requirement("summary:" + key, key), "scope": scope}
                for key in ("first", "second")])]
        self.catalog = [{**_candidate("note-" + key, 0), **scope, "kind": "narrative",
            "normalized_value": None, "raw_value": "", "raw_unit": "", "normalized_unit": "UNKNOWN",
            "source_text": text}
            for key, text in (("first", "The teams combine shared operations."),
                ("second", "The teams provide hosted services."), ("hidden", "Hidden source."))]
        self.program = {"status": "ready", "narrative_bindings": [{
            "obligation_id": "summary",
            "evidence_bindings": [{"candidate_id": "note-" + key, "source_requirement_id": "summary:" + key}
                for key in ("first", "second")],
            "text": "The teams combine shared operations and provide hosted services.",
        }]}
        self.visibility = _semantic_candidate_visibility(self.catalog,
            visible_candidate_ids=["note-first", "note-second"], candidate_ids_by_owner={
                "summary": ["note-first", "note-second"],
                "summary:first": ["note-first"], "summary:second": ["note-second"],
            })

    def validate(self, program=None, catalog=None, obligations=None):
        return validate_semantic_calculation_program(program=program or self.program,
            candidate_catalog=catalog or self.catalog, obligations=obligations or self.obligations,
            query="Summarize both activities.", candidate_visibility=self.visibility)

    def test_provider_schema_no_longer_requests_duplicate_narrative_ids(self):
        schema = SemanticCalculationProgram.model_json_schema()
        self.assertNotIn("candidate_ids", schema["$defs"]["SemanticProgramNarrativeBinding"]["properties"])
        self.assertIn("candidate_ids", schema["$defs"]["SemanticProgramSourceAssertion"]["properties"])

    def test_model_and_raw_validator_project_the_same_members_without_input_mutation(self):
        original = deepcopy(self.program)
        projection = SemanticCalculationProgram.model_validate(self.program).model_dump()
        self.assertEqual(projection["narrative_bindings"][0]["candidate_ids"], ["note-first", "note-second"])
        raw = self.validate()
        modeled = self.validate(projection)
        self.assertEqual(raw["status"], "ready")
        self.assertEqual(raw["selected_candidate_ids"], modeled["selected_candidate_ids"])
        self.assertEqual(self.program, original)

    def test_duplicate_binding_dedupes_members_but_keeps_requirement_links(self):
        program = deepcopy(self.program)
        binding = program["narrative_bindings"][0]
        binding["evidence_bindings"].append(deepcopy(binding["evidence_bindings"][0]))
        projection = SemanticCalculationProgram.model_validate(program).model_dump()
        self.assertEqual(projection["narrative_bindings"][0]["candidate_ids"], ["note-first", "note-second"])
        self.assertEqual(len(projection["narrative_bindings"][0]["evidence_bindings"]), 3)
        self.assertEqual(self.validate(projection)["status"], "ready")

    def test_authority_scope_and_number_failures_are_still_rejected(self):
        for change, code in (
            ({"first_candidate": "invented"}, "unknown_narrative_candidate"),
            ({"first_candidate": "note-hidden"}, "candidate_not_exposed_to_compiler"),
            ({"first_candidate": "note-second"}, "candidate_not_exposed_to_compiler"),
            ({"first_requirement": "invented"}, "unknown_narrative_requirement"),
            ({"first_requirement": ""}, "missing_required_evidence_binding"),
            ({"omit_second": True}, "missing_required_evidence_binding"),
            ({"text": "The teams serve 42 clients."}, "ungrounded_narrative_number"),
            ({"legacy_ids": ["note-first"]}, "narrative_requirement_candidate_not_selected"),
            ({"period": "2022"}, "candidate_scope_mismatch"),
        ):
            with self.subTest(change=change):
                program, catalog = deepcopy(self.program), deepcopy(self.catalog)
                binding = program["narrative_bindings"][0]
                if "first_candidate" in change:
                    binding["evidence_bindings"][0]["candidate_id"] = change["first_candidate"]
                if "first_requirement" in change:
                    binding["evidence_bindings"][0]["source_requirement_id"] = change["first_requirement"]
                if change.get("omit_second"):
                    binding["evidence_bindings"].pop()
                if "legacy_ids" in change:
                    binding["candidate_ids"] = change["legacy_ids"]
                if "text" in change:
                    binding["text"] = change["text"]
                if "period" in change:
                    catalog[0]["period"] = change["period"]
                result = self.validate(program, catalog)
                self.assertNotEqual(result["status"], "ready")
                self.assertIn(code, {item["code"] for item in result["errors"]})

    def test_owner_only_evidence_needs_no_invented_requirement(self):
        obligations = deepcopy(self.obligations)
        obligations[0]["evidence_requirements"] = []
        program = deepcopy(self.program)
        for binding in program["narrative_bindings"][0]["evidence_bindings"]:
            binding.pop("source_requirement_id")
        projection = SemanticCalculationProgram.model_validate(program).model_dump()
        result = self.validate(projection, obligations=obligations)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["selected_candidate_ids"], ["note-first", "note-second"])
        # An unscoped reference may not silently satisfy a required input.
        self.assertIn("missing_required_evidence_binding", {item["code"] for item in self.validate(projection)["errors"]})

    def test_compiler_executes_first_narrative_response_without_retry(self):
        llm = _StructuredQueueLLM(self.claimed_program())
        state = _case_state({"question": "Summarize both activities.", "obligations": self.obligations}, self.catalog)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 1)
        self.assertEqual(compiled["semantic_program_retry_count"], 0)
        execution = execute_semantic_calculation_program(program=compiled["semantic_program"],
            obligations=self.obligations, candidate_catalog=self.catalog, query=state["query"],
            compilation_envelope=compiled["semantic_compilation_envelope"], require_compilation_envelope=True)
        self.assertEqual(execution["status"], "ok")
        self.assertEqual(execution["selected_candidate_ids"], ["note-first", "note-second"])

    def test_accepted_narrative_bytes_survive_other_island_retry(self):
        narrative = self.claimed_program()
        obligations = [*self.obligations, _obligation("quantity", "direct_value", "quantity")]
        catalog = [*self.catalog, _candidate("quantity-cell", 10)]
        llm = _StructuredQueueLLM(narrative,
            SemanticCalculationProgram.model_validate({"status": "ready", "direct_bindings": [{"obligation_id": "quantity", "candidate_id": "invented"}]}),
            SemanticCalculationProgram.model_validate({"status": "ready", "direct_bindings": [{"obligation_id": "quantity", "candidate_id": "quantity-cell"}]}))
        state = _case_state({"question": "Summarize activities and return the quantity.", "obligations": obligations}, catalog)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(json.dumps(compiled["semantic_program"]["narrative_bindings"], sort_keys=True),
            json.dumps(narrative.model_dump()["narrative_bindings"], sort_keys=True))

    def claimed_program(self):
        return SemanticCalculationProgram.model_validate(_with_narrative_claims(self.program,
            subject="The teams", quotes={"note-first": "The teams combine shared operations.",
                "note-second": "The teams provide hosted services."}))


if __name__ == "__main__":
    unittest.main()
