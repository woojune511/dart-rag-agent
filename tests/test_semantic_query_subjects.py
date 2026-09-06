from __future__ import annotations

from copy import deepcopy
import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import RequirementPlannerOutput
from src.agent.financial_graph_planning import preserve_query_subject_surfaces
from tests.semantic_program_test_support import _StructuredQueueLLM


class SemanticQuerySubjectTests(unittest.TestCase):
    def test_query_bilingual_pair_is_preserved_from_either_spelling(self):
        query = "오로라(Aurora)의 변화와 다른회사(Other)의 현황을 설명하세요."
        for subjects in (["오로라"], ["Aurora"], ["오로라(Aurora)"]):
            with self.subTest(subjects=subjects):
                result = preserve_query_subject_surfaces(query, subjects)
                self.assertIn("오로라", result)
                self.assertIn("Aurora", result)
                self.assertNotIn("Other", result)
                self.assertEqual(result, preserve_query_subject_surfaces(query, result))
                self.assertEqual(result[:len(subjects)], subjects)

    def test_explanations_numbers_and_unselected_names_do_not_become_aliases(self):
        for query in ("오로라(성장률)", "오로라(2023)", "오로라(12%)", "다른오로라(Aurora)"):
            with self.subTest(query=query):
                self.assertEqual(preserve_query_subject_surfaces(query, ["오로라"]), ["오로라"])
        self.assertEqual(preserve_query_subject_surfaces("오로라(Aurora)", []), [])

    def test_spaces_and_fullwidth_parentheses_preserve_exact_name(self):
        self.assertEqual(
            preserve_query_subject_surfaces("오로라 （Aurora Labs, Inc.）", ["오로라"]),
            ["오로라", "Aurora Labs, Inc."],
        )

    def test_planner_applies_same_projection_to_obligations_and_requirements(self):
        response = RequirementPlannerOutput.model_validate({"obligations": [{
            "obligation_id": "context", "kind": "narrative", "label": "reported effect",
            "semantic_target": {"local_subjects": ["오로라"]},
            "evidence_requirements": [{"requirement_id": "effect", "label": "effect",
                "semantic_target": {"local_subjects": ["오로라"]}}],
        }]})
        original = deepcopy(response.model_dump())
        llm = _StructuredQueueLLM(response)
        agent = FinancialAgent.__new__(FinancialAgent)
        agent._llm_for_phase = lambda phase: llm
        plan = agent._build_llm_requirement_plan(
            query="오로라(Aurora)의 영향을 설명하세요.", topic="effect", intent="narrative", report_scope={},
        )
        owner = plan["answer_obligations"][0]
        self.assertEqual(owner["semantic_target"]["local_subjects"], ["오로라", "Aurora"])
        self.assertEqual(owner["evidence_requirements"][0]["semantic_target"]["local_subjects"], ["오로라", "Aurora"])
        self.assertEqual(response.model_dump(), original)
        self.assertEqual(llm.models, ["RequirementPlannerOutput"])


if __name__ == "__main__":
    unittest.main()
