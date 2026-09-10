"""An island's bounded evidence is not a document-wide answer contract."""

from copy import deepcopy
import json
import unittest

from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.config.retrieval_policy import CALCULATION_PROMPT_POLICY
from tests.semantic_program_test_support import _StructuredQueueLLM, _obligation, _scope


def paragraph(candidate_id, subject, text, *, segment=""):
    return {
        "candidate_id": candidate_id, "kind": "narrative", "candidate_kind": "chunk",
        "source_candidate_id": candidate_id, "source_anchor": "[anonymous report]",
        "company": "Filing Group", "document_company": "Filing Group", "year": 2031,
        "segment": segment, "source_text": text, "local_entity_surfaces": [subject],
        "normalized_value": None, "normalized_unit": "UNKNOWN",
        "source_body_coverage": {"truncated": False},
    }


def binding(owner_id, candidate_id, text):
    return {"obligation_id": owner_id, "text": text,
        "evidence_bindings": [{"candidate_id": candidate_id, "source_requirement_id": ""}]}


def prompt_json(prompt, heading):
    content = prompt.to_messages()[0].content
    return json.JSONDecoder().raw_decode(content.split(heading + "\n", 1)[1].lstrip())[0]


class SemanticCompilationScopeTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [paragraph("source-a", "Cedar Unit", "Cedar Unit performs shared operations.", segment="Cedar Unit"),
                        paragraph("source-b", "River Unit", "River Unit uses regional distributors.", segment="River Unit")]
        self.owners = [_obligation(key, "narrative", label,
            scope=_scope(company="Filing Group", period="2031", segment=subject))
            for key, label, subject in (("operations", "shared operations", "Cedar Unit"),
                                       ("distribution", "regional distributors", "River Unit"))]
        self.bindings = [binding(owner["obligation_id"], candidate["candidate_id"], candidate["source_text"])
                         for owner, candidate in zip(self.owners, self.catalog)]

    def compile(self, programs):
        llm = _StructuredQueueLLM(*[SemanticCalculationProgram.model_validate(item) for item in programs])
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = llm
        state = {"query": "Summarize operations and distribution for Filing Group.",
            "answer_obligations": self.owners, "semantic_candidate_catalog": self.catalog,
            "semantic_source_candidates": [], "semantic_candidate_catalog_prebuilt": True}
        before = deepcopy(state)
        result = agent._compile_semantic_calculation_program(state)
        self.assertEqual(state, before)
        return result, llm.prompts

    def assert_scope(self, prompt, active_ids):
        scope = prompt_json(prompt, "Compilation scope:")
        self.assertEqual(scope, {
            "schema": "semantic_compilation_scope_v1",
            "active_obligation_ids": active_ids,
            "question_role": "context_only",
            "evidence_coverage": "bounded_excerpts",
            "document_absence_established": False,
        })
        self.assertEqual([row["obligation_id"] for row in prompt_json(prompt, "Answer obligations:")], active_ids)

    def test_independent_islands_declare_only_their_active_output_and_id_space(self):
        result, prompts = self.compile([{"narrative_bindings": [row]} for row in self.bindings])
        self.assertEqual(result["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(prompts), 2)
        for prompt, owner, candidate in zip(prompts, self.owners, self.catalog):
            self.assert_scope(prompt, [owner["obligation_id"]])
            payload = prompt_json(prompt, "Source bundles, candidate cohorts, and candidates_by_id:")
            self.assertEqual(set(payload["candidates_by_id"]), {candidate["candidate_id"]})

    def test_retry_scope_drops_accepted_output_and_preserves_its_bytes(self):
        for row in self.catalog:
            row["segment"] = ""
        for owner in self.owners:
            owner["scope"]["segment"] = ""
            owner["coupling_key"] = "same-basis"
        bad = deepcopy(self.bindings[1])
        bad["text"] = ""
        result, prompts = self.compile([
            {"narrative_bindings": [self.bindings[0], bad]},
            {"narrative_bindings": [self.bindings[1]]},
        ])
        self.assertEqual(result["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(prompts), 2)
        self.assert_scope(prompts[0], ["operations", "distribution"])
        self.assert_scope(prompts[1], ["distribution"])
        accepted = SemanticCalculationProgram.model_validate({"narrative_bindings": [self.bindings[0]]}).model_dump()["narrative_bindings"][0]
        self.assertEqual(json.dumps(result["semantic_program"]["narrative_bindings"][0], sort_keys=True),
                         json.dumps(accepted, sort_keys=True))

    def test_complete_candidate_body_does_not_assert_complete_document_coverage(self):
        self.owners, self.catalog, self.bindings = self.owners[:1], self.catalog[:1], self.bindings[:1]
        _result, prompts = self.compile([{"narrative_bindings": self.bindings}])
        self.assert_scope(prompts[0], ["operations"])
        payload = prompt_json(prompts[0], "Source bundles, candidate cohorts, and candidates_by_id:")
        self.assertFalse(payload["candidates_by_id"]["source-a"]["source_body_coverage"]["truncated"])

    def test_local_subject_and_exact_source_remain_distinct_from_filing_company(self):
        before = deepcopy(self.catalog)
        plan = _semantic_candidate_cohorts(self.catalog, self.owners)
        payload = FinancialAgent._semantic_program_prompt_payload(self.catalog, plan)
        for candidate in self.catalog:
            row = payload["candidates_by_id"][candidate["candidate_id"]]
            self.assertEqual(row["document_company"], "Filing Group")
            self.assertEqual(row["local_entity_surfaces"], candidate["local_entity_surfaces"])
            self.assertEqual(payload["source_bundles_by_id"][row["source_bundle_id"]]["source_text"], candidate["source_text"])
        self.assertEqual(self.catalog, before)

    def test_prompt_defines_owner_absence_local_subject_and_theme_boundaries(self):
        prompt = CALCULATION_PROMPT_POLICY["semantic_program_prompt_template"]
        for rule in ("active_obligation_ids", "문서 전체의 부재", "공시 주체", "필수 주제", "다른 출력"):
            self.assertIn(rule, prompt)

    def test_known_foreign_subject_remains_invalid_even_with_narrative_scope_override(self):
        program = {"narrative_bindings": [{**self.bindings[1], "obligation_id": "operations",
                                          "scope_applicability_fields": ["segment"]}]}
        result = validate_semantic_calculation_program(program=program, obligations=self.owners,
            candidate_catalog=self.catalog, query="Summarize the requested units.")
        self.assertNotEqual(result["status"], "ready")
        self.assertTrue(any(error["obligation_id"] == "operations" for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
