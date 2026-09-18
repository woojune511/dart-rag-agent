"""The reviewed serialization instruction reaches every Compiler prompt kind."""
from copy import deepcopy
import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.config.retrieval_policy import CALCULATION_PROMPT_POLICY
from tests.compiler_presentation_test_support import surface_text
from tests.narrative_address_test_support import model_program
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM
from tests.test_compiler_display_intent import compile_case, fixture
from tests.test_narrative_claim_grounding import claim, source
from tests.test_narrative_retry_context import prompt_json


REVIEWED_PREFIX = (
    "Return one JSON object matching the schema. Omit optional whitespace, indentation "
    "and line breaks outside JSON strings; do not add Markdown fences or text outside "
    "the object. This is a serialization rule only: retain every required field, output, "
    "claim, qualification and evidence reference. Do not shorten content to satisfy it. "
    "Do not remove or normalize whitespace inside string values, especially spaces, "
    "line breaks and punctuation in exact source quotations.\n\n"
)


class CompilerCompactJSONPolicyTests(unittest.TestCase):
    def assert_serialization_instruction(self, text):
        self.assertTrue(text.startswith(REVIEWED_PREFIX))
        self.assertEqual(text.count(REVIEWED_PREFIX), 1)

    def test_numeric_and_narrative_templates_use_the_reviewed_preservation_instruction(self):
        for key in ("semantic_program_prompt_template", "semantic_program_narrative_prompt_template"):
            with self.subTest(template=key):
                self.assert_serialization_instruction(CALCULATION_PROMPT_POLICY[key])

    def test_numeric_initial_and_retry_keep_original_request_and_same_candidates(self):
        query = "Calculate the change and keep  exact\trequest spacing."
        agent, _, compiled = compile_case(fixture(), query, omit_first_decision=True)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(len(agent.llm.prompts), 2)
        for prompt in agent.llm.prompts:
            text = prompt.to_messages()[0].content
            self.assert_serialization_instruction(text)
            self.assertIn(query, text)
        marker = "Source bundles, candidate cohorts, and candidates_by_id:"
        self.assertEqual(prompt_json(agent.llm.prompts[0], marker),
                         prompt_json(agent.llm.prompts[1], marker))

    def test_mixed_to_narrative_retry_keeps_exact_quote_and_accepted_numeric_output(self):
        body = "Cedar  uses\tlocal partners.\r\nThe quoted label is \"A\\B\"."
        catalog = [source("note", body), _candidate("size-cell", 12)]
        owners = [_obligation("size", "direct_value", "Size"),
                  _obligation("activity", "narrative", "Describe activity.", depends_on=["size"])]
        row = claim("Cedar", "Uses local partners.", "note", body)
        good = {"narrative_bindings": [{"obligation_id": "activity", "claims": [row]}]}
        bad = deepcopy(good)
        bad["narrative_bindings"][0]["claims"][0]["evidence_bindings"][0]["evidence_text"] = "invented quote"
        bad["direct_bindings"] = [{"obligation_id": "size", "candidate_id": "size-cell"}]
        accepted = SemanticCalculationProgram(direct_bindings=bad["direct_bindings"]).model_dump()["direct_bindings"]
        llm = _StructuredQueueLLM(model_program(bad, catalog), model_program(good, catalog))
        agent = object.__new__(FinancialAgent)
        agent.llm = llm
        state = {"query": "Report size and activity.", "answer_obligations": owners,
                 "semantic_candidate_catalog": catalog, "semantic_candidate_catalog_prebuilt": True,
                 "semantic_source_candidates": []}
        original = deepcopy(state)
        compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(llm.prompts), 2)
        for prompt in llm.prompts:
            self.assert_serialization_instruction(prompt.to_messages()[0].content)
            payload = prompt_json(prompt, "Source bundles, candidate cohorts, and candidates_by_id:")
            self.assertIn(body, [surface_text(surface) for reading in payload["source_readings"]
                                 for surface in reading["bodies"]])
        self.assertIn("source_display_reason", llm.prompts[0].to_messages()[0].content)
        self.assertNotIn("source_display_reason", llm.prompts[1].to_messages()[0].content)
        self.assertEqual(compiled["semantic_program"]["direct_bindings"], accepted)
        claims = compiled["semantic_program"]["narrative_bindings"][0]["claims"]
        self.assertEqual(claims, model_program(good, catalog).model_dump()["narrative_bindings"][0]["claims"])
        self.assertEqual(state, original)


if __name__ == "__main__":
    unittest.main()
