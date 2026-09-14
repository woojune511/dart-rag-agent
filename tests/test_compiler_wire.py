from copy import deepcopy
import json
import unittest

from src.agent.financial_compiler_wire import CompilerReferencesV1, compiler_response_model, lower_compiler_response
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts, _semantic_candidate_visibility
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from tests.semantic_program_test_support import _candidate, _obligation, _requirement, _StructuredQueueLLM
from src.agent.financial_graph_models import SemanticCalculationProgram
from tests.compiler_wire_test_support import wire_fixture


class CompilerWireTests(unittest.TestCase):
    def test_reference_retry_keeps_accepted_dependency_bytes(self):
        owners = [_obligation("base", "direct_value", "quantity"),
                  _obligation("calc", "derived_value", "quantity", depends_on=["base"])]
        catalog = [_candidate("number", 7)]
        initial = SemanticCalculationProgram.model_validate({"status": "ready", "direct_bindings": [
            {"obligation_id": "base", "candidate_id": "number"}], "expressions": [{
                "obligation_id": "calc", "formula": "A", "variable_bindings": [{"variable": "A", "source_id": "hidden"}],
                "source_display_candidate_id": None, "source_display_reason": "No display"}]})
        retry = SemanticCalculationProgram.model_validate({"status": "ready", "expressions": [{
            "obligation_id": "calc", "formula": "A", "variable_bindings": [{"variable": "A", "source_id": "base"}],
            "source_display_candidate_id": None, "source_display_reason": "No display"}]})
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StructuredQueueLLM(initial, retry)
        compiled = agent._compile_semantic_calculation_program({"query": "Return the outputs.", "answer_obligations": owners,
            "semantic_candidate_catalog_prebuilt": True, "semantic_source_candidates": catalog, "semantic_candidate_catalog": catalog,
            "include_debug_bundle": True})
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready", compiled["planner_debug_trace"])
        self.assertEqual(len(agent.llm.prompts), 2)
        self.assertEqual(compiled["semantic_program"]["direct_bindings"], initial.model_dump()["direct_bindings"])
        diagnostics = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]
        self.assertEqual(diagnostics["attempts"][1]["target_obligation_ids"], ["calc"])
        self.assertEqual(diagnostics["attempts"][1]["read_only_dependency_ids"], ["base"])
    def setup_wire(self, owners, catalog):
        plan = _semantic_candidate_cohorts(catalog, owners)
        payload = FinancialAgent._semantic_program_prompt_payload(catalog, plan)
        refs = CompilerReferencesV1.build(catalog, owners, "Return the outputs.", payload)
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=plan["visible_candidate_ids"],
            candidate_ids_by_owner=plan["candidate_ids_by_owner"], evidence_bundle_constraints=[])
        return refs, compiler_response_model(owners, refs), visibility, payload

    def test_per_output_schema_has_no_narrative_expression(self):
        owners, catalog = [_obligation("note", "narrative", "note")], [_candidate("value", 1)]
        refs, model, visibility, payload = self.setup_wire(owners, catalog)
        schema = json.dumps(model.model_json_schema())
        self.assertNotIn('"formula"', schema)
        self.assertNotIn('"variable_bindings"', schema)
        raw = {"outputs": {refs.ref("note"): {"status": "ready", "result": {"formula": "1"}, "reason": "wrong kind"}}}
        with self.assertRaises(ValueError):
            lower_compiler_response(raw, model=model, refs=refs, obligations=owners, catalog=catalog, visibility=visibility)

    def test_short_refs_are_stable_and_source_text_is_not_rewritten(self):
        owners, catalog = [_obligation("value", "direct_value", "quantity")], [_candidate("cand_first", 17), _candidate("cand_second", 17)]
        catalog[0]["source_text"] = "cand_first"
        refs, model, visibility, payload = self.setup_wire(owners, catalog)
        reverse = self.setup_wire(owners, catalog[::-1])[0]
        self.assertEqual(refs.entries, reverse.entries)
        self.assertEqual(refs.project({"source_text": "cand_first", "candidate_id": "cand_first"}),
            {"source_text": "cand_first", "candidate_id": refs.ref("cand_first")})
        before = deepcopy((owners, catalog, payload))
        raw = wire_fixture({"direct_bindings": [{"obligation_id": "value", "candidate_id": "cand_first"}]}, model)
        program = lower_compiler_response(raw, model=model, refs=refs, obligations=owners, catalog=catalog, visibility=visibility)
        self.assertEqual(program["direct_bindings"][0]["candidate_id"], "cand_first")
        self.assertEqual((owners, catalog, payload), before)

    def test_hidden_and_other_period_refs_are_not_repaired(self):
        owners = [_obligation("growth", "derived_value", "growth", evidence_requirements=[
            _requirement("current", "quantity", period="2042"),
            _requirement("prior", "quantity", period="2041")])]
        catalog = [_candidate("current-value", 9, period="2042"), _candidate("prior-value", 8, period="2041")]
        refs, model, visibility, _ = self.setup_wire(owners, catalog)
        program = {"expressions": [{"obligation_id": "growth", "formula": "A", "variable_bindings": [
            {"variable": "A", "source_id": "prior-value", "source_requirement_id": "current"}],
            "source_display_candidate_id": None, "source_display_reason": "No display"}]}
        raw = wire_fixture(program, model)
        for value in (refs.ref("prior-value"), "c_hidden"):
            raw["outputs"][refs.ref("growth")]["result"]["inputs"][refs.ref("current")][0]["source_ref"] = value
            with self.assertRaises(ValueError):
                lower_compiler_response(raw, model=model, refs=refs, obligations=owners, catalog=catalog, visibility=visibility)

    def test_legacy_flat_program_is_not_a_production_response(self):
        owners, catalog = [_obligation("value", "direct_value", "quantity")], [_candidate("number", 1)]
        refs, model, visibility, _ = self.setup_wire(owners, catalog)
        with self.assertRaises(ValueError):
            lower_compiler_response({"direct_bindings": [{"obligation_id": "value", "candidate_id": "number"}]},
                model=model, refs=refs, obligations=owners, catalog=catalog, visibility=visibility)


if __name__ == "__main__":
    unittest.main()
