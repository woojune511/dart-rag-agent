"""Subject display is deterministic; evidence authority is checked separately."""

from copy import deepcopy
import json
import unittest

from src.agent.financial_calculation_execution import (
    assemble_semantic_execution_result, execute_semantic_calculation_program,
    validate_semantic_calculation_program,
)
from src.agent.financial_graph_calculation import _semantic_candidate_visibility
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_program_projection import project_narrative_claims
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM
from tests.test_narrative_claim_grounding import claim, source


class NarrativeClaimRenderingTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [source("note", "Aspen distributes through partners.")]
        self.owners = [_obligation("activity", "narrative", "Describe activity.")]
        self.program = {"narrative_bindings": [{"obligation_id": "activity", "claims": [
            claim("Aspen", "Distributes through partners.", "note", self.catalog[0]["source_text"])]}]}
        self.visibility = _semantic_candidate_visibility(self.catalog,
            visible_candidate_ids=["note"], candidate_ids_by_owner={"activity": ["note"]})

    def validate(self, program=None):
        return validate_semantic_calculation_program(program=program or self.program,
            obligations=self.owners, candidate_catalog=self.catalog, query="Describe activity.",
            candidate_visibility=self.visibility, require_narrative_claims=True)

    def test_projection_scopes_fragments_without_rewriting_full_statements(self):
        for subject, text, expected in (
            ("Aspen", "Distributes through partners.", "Aspen: Distributes through partners."),
            ("Aspen", "Aspen distributes through partners.", "Aspen distributes through partners."),
            ("Orion Labs", "Operates independently.", "Orion Labs: Operates independently."),
            ("해솔", "외부 팀과 협력합니다.", "해솔: 외부 팀과 협력합니다."),
            ("みどり", "共同で運営します。", "みどり: 共同で運営します。"),
            ("North  Unit", "North\nUnit serves clients.", "North Unit serves clients."),
        ):
            with self.subTest(subject=subject, text=text):
                binding = {"claims": [claim(subject, text, "note", "unchanged quote")]}
                before = deepcopy(binding)
                projected = project_narrative_claims(binding)
                self.assertEqual(projected["text"], expected)
                self.assertEqual(projected["claims"], before["claims"])
                self.assertEqual(project_narrative_claims(projected), projected)
                self.assertEqual(binding, before)

    def test_raw_model_validator_executor_and_final_assembler_share_display(self):
        before = deepcopy(self.program)
        modeled = SemanticCalculationProgram.model_validate(self.program).model_dump()
        raw, validation = self.validate(), self.validate(modeled)
        self.assertEqual(raw["status"], "ready")
        self.assertEqual(validation["status"], "ready")
        self.assertEqual(modeled, SemanticCalculationProgram.model_validate(modeled).model_dump())
        envelope = CompilationEnvelopeV2.create(program=modeled, validation=validation, visibility=self.visibility,
            candidate_catalog=self.catalog, obligations=self.owners, query="Describe activity.")
        execution = execute_semantic_calculation_program(program=modeled, obligations=self.owners,
            candidate_catalog=self.catalog, query="Describe activity.", compilation_envelope=envelope,
            require_compilation_envelope=True)
        self.assertEqual(execution["status"], "ok")
        output = execution["outputs"][0]
        expected = "Aspen: Distributes through partners."
        self.assertEqual(output["text"], expected)
        self.assertEqual(output["candidate_ids"], ["note"])
        reading = output["claim_readings"][0]
        self.assertEqual(reading["text"], "Distributes through partners.")
        self.assertEqual(reading["rendered_text"], expected)
        self.assertEqual(reading["evidence"][0]["evidence_text"], self.catalog[0]["source_text"])
        final = assemble_semantic_execution_result(execution=execution, obligations=self.owners,
            calculation_plan={}, query="Describe activity.")
        self.assertIn(expected, final["answer"])
        self.assertEqual(final["structured_result"]["subtask_results"][0]["answer"], expected)
        self.assertEqual(self.program, before)

    def test_fragment_cannot_bypass_subject_quote_number_or_id_authority(self):
        for field, value, code in (
            ("subject", "Issuer", "ungrounded_narrative_subject"),
            ("text", "Serves 918 clients.", "ungrounded_narrative_claim_number"),
            ("evidence_text", "Aspen distributes through partners!", "invalid_narrative_claim_quote"),
            ("candidate_id", "foreign", "unknown_narrative_candidate"),
        ):
            with self.subTest(field=field):
                program = deepcopy(self.program)
                row = program["narrative_bindings"][0]["claims"][0]
                target = row if field in ("subject", "text") else row["evidence_bindings"][0]
                target[field] = value
                validation = self.validate(program)
                self.assertNotEqual(validation["status"], "ready")
                self.assertIn(code, {item["code"] for item in validation["errors"]})

    def test_blank_or_nonstring_subject_and_text_cannot_pass_validation(self):
        for field in ("subject", "text"):
            for value in (None, 3, "", " \n "):
                with self.subTest(field=field, value=value):
                    program = deepcopy(self.program)
                    program["narrative_bindings"][0]["claims"][0][field] = value
                    self.assertNotEqual(self.validate(program)["status"], "ready")

    def test_explicit_flat_text_cannot_drop_renderer_subject(self):
        program = deepcopy(self.program)
        program["narrative_bindings"][0]["text"] = "Distributes through partners."
        self.assertIn("narrative_claim_projection_mismatch", {
            item["code"] for item in self.validate(program)["errors"]})

    def test_fragment_compiles_once_and_preserves_an_independent_program(self):
        accepted = SemanticCalculationProgram(direct_bindings=[{
            "obligation_id": "size", "candidate_id": "size-cell"}])
        llm = _StructuredQueueLLM(accepted, SemanticCalculationProgram.model_validate(self.program))
        owners = [_obligation("size", "direct_value", "Size"), *self.owners]
        catalog = [_candidate("size-cell", 12), *self.catalog]
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(
            _case_state({"question": "Describe activity and size.", "obligations": owners}, catalog))
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(compiled["semantic_program_retry_count"], 0)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(json.dumps(compiled["semantic_program"]["direct_bindings"], sort_keys=True),
            json.dumps(accepted.model_dump()["direct_bindings"], sort_keys=True))

    def test_failed_claim_attempts_retain_actionable_diagnostics_after_merge(self):
        bad = deepcopy(self.program)
        bad["narrative_bindings"][0]["claims"][0]["evidence_bindings"][0]["evidence_text"] = "Wrong quote."
        modeled = SemanticCalculationProgram.model_validate(bad)
        llm = _StructuredQueueLLM(modeled, modeled)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(
            _case_state({"question": "Describe activity.", "obligations": self.owners}, self.catalog))
        self.assertEqual(len(llm.prompts), 2)
        history = compiled["planner_debug_trace"]["program_validation_history"]
        self.assertEqual([row["attempt"] for row in history], [1, 2])
        for observation in history:
            error = next(row for row in observation["errors"] if row["code"] == "invalid_narrative_claim_quote")
            self.assertEqual(error["candidate_id"], "note")
            self.assertTrue(error["detail"])
            self.assertEqual(error["repair_action"], "repair_program")
        retry_text = llm.prompts[1].to_messages()[0].content
        self.assertIn(history[0]["errors"][0]["detail"], retry_text)
        self.assertEqual(history[0]["visible_candidate_ids"], history[1]["visible_candidate_ids"])
        self.assertEqual(compiled["semantic_program_validation"]["errors"], [])


if __name__ == "__main__":
    unittest.main()
