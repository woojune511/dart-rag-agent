"""Every requested output needs an explicit evidence/coverage contract."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import RequirementPlannerOutput, SemanticCalculationProgram
from src.agent.financial_retrieval_hints import evidence_extraction_focus_terms
from src.config.retrieval_policy import (
    CALCULATION_NARRATIVE_POLICY, DIVIDEND_POLICY_ASSEMBLY_POLICY,
    EVIDENCE_EXTRACTION_POLICY, QUERY_FOCUS_STOPWORDS,
)
from src.utils.provider_errors import ProviderAdmissionError
from tests.semantic_program_test_support import _candidate, _StructuredQueueLLM, _with_narrative_claims


def _plan():
    return RequirementPlannerOutput.model_validate({
        "topic": "shared operations and service provision",
        "obligations": [
            {"request_unit_ids": ["request_001"], "kind": "narrative", "label": label,
             "evidence_requirements": [{"label": label, "retrieval_hints": [label]}]}
            for label in ("shared operations", "service provision")
        ],
    })


def _program(index):
    owner = f"ob_{index:03d}"
    text = "The teams combine shared operations." if index == 1 else "The teams provide hosted services."
    return SemanticCalculationProgram.model_validate(_with_narrative_claims({"narrative_bindings": [{
        "obligation_id": owner,
        "evidence_bindings": [{"candidate_id": f"note-{index}",
                               "source_requirement_id": owner + ":req_001"}],
        "text": ("The teams combine shared operations." if index == 1
                 else "The teams provide hosted services."),
    }]}, subject="The teams", quotes={f"note-{index}": text}))


class UniformRequirementContractTests(unittest.TestCase):
    @staticmethod
    def _agent(llm):
        agent = object.__new__(FinancialAgent)
        agent.llm, agent.llm_routes, agent.llm_usage_callback = llm, {}, None
        agent.vsm = None
        return agent

    def test_intent_and_display_format_cannot_bypass_requirements(self):
        for intent in ("qa", "risk", "business_overview", "numeric_fact", "comparison", "trend"):
            for form in ("paragraph", "table", "mixed"):
                with self.subTest(intent=intent, form=form):
                    llm = _StructuredQueueLLM(_plan())
                    state = {"query": "Explain shared operations and service provision.",
                             "intent": intent, "format_preference": form}
                    before = deepcopy(state)
                    planned = self._agent(llm)._plan_answer_obligation_program(state)
                    self.assertTrue(planned["semantic_plan"]["program_required"])
                    self.assertFalse(planned["semantic_plan"]["fallback_to_general_search"])
                    self.assertEqual(len(planned["answer_obligations"]), 2)
                    self.assertEqual(len(llm.prompts), 1)
                    self.assertEqual(state, before)

    def test_planner_terminal_admission_failure_is_not_missing_evidence(self):
        error = ProviderAdmissionError("budget_reservation_exceeded", "synthetic terminal stop")
        llm = _StructuredQueueLLM()
        llm.invoke = Mock(side_effect=error)
        with self.assertRaises(ProviderAdmissionError) as raised:
            self._agent(llm)._plan_answer_obligation_program({
                "query": "Explain both activities.", "intent": "qa",
            })
        self.assertIs(raised.exception, error)
        self.assertEqual(llm.invoke.call_count, 1)

    def test_retained_evidence_helpers_do_not_retry_terminal_admission_errors(self):
        from src.agent import financial_graph_evidence

        for name in ("_extract_evidence", "_compress_answer", "_validate_answer"):
            with self.subTest(name=name):
                error = ProviderAdmissionError("budget_reservation_exceeded", "synthetic terminal stop")
                chain = Mock()
                chain.invoke.side_effect = error

                class Prompt:
                    def __or__(self, other):
                        return chain

                agent = self._agent(Mock())
                evidence = [{"evidence_id": "note", "claim": "The teams share operations.", "metadata": {}}]
                agent._build_evidence_context = Mock(return_value={
                    "anchor_lookup": {}, "available_anchors": [], "context": "source"})
                agent._compose_entity_table_summary_answer = Mock(return_value=None)
                agent._select_evidence_for_compression = Mock(return_value=evidence)
                agent._filter_evidence_by_ids = Mock(return_value=evidence)
                agent._format_evidence_for_prompt = Mock(return_value="source")
                state = {"query": "Explain the activities.", "retrieved_docs": [object()],
                         "evidence_items": evidence, "compressed_answer": "The teams share operations."}
                with patch.object(financial_graph_evidence, "chat_prompt_template_from_template", return_value=Prompt()):
                    with self.assertRaises(ProviderAdmissionError) as raised:
                        getattr(agent, name)(state)
                self.assertIs(raised.exception, error)
                self.assertEqual(chain.invoke.call_count, 1)

    def test_public_graph_records_uncovered_narrative_and_preserves_covered_output(self):
        for covered in (False, True):
            with self.subTest(covered=covered):
                second = _program(2) if covered else SemanticCalculationProgram.model_validate({
                    "status": "incomplete", "missing_obligation_ids": ["ob_002"],
                    "rationale": "No supporting source for the requested service provision.",
                })
                llm = _StructuredQueueLLM(_plan(), _program(1), second)
                agent = self._agent(llm)
                agent._classify_query = Mock(return_value={"intent": "qa", "query_type": "qa"})
                agent._extract_entities = Mock(return_value={"companies": [], "years": [], "topic": "activities"})
                agent._retrieve = Mock(return_value={"retrieved_docs": [], "seed_retrieved_docs": []})
                agent._expand_via_structure_graph = Mock(return_value={"retrieved_docs": []})
                catalog = [{**_candidate(f"note-{index}", 0), "kind": "narrative",
                            "normalized_value": None, "normalized_unit": "UNKNOWN",
                            "raw_value": "", "raw_unit": "", "source_text": text}
                           for index, text in enumerate(("The teams combine shared operations.",
                                                        "The teams provide hosted services."), 1)]
                agent._semantic_source_candidates_for_state = Mock(return_value=catalog)
                agent._semantic_candidate_catalog_for_state = Mock(return_value=catalog)
                agent._format_citations = Mock(return_value={"citations": []})
                # No second unconstrained summarization path is allowed.
                agent._extract_evidence = Mock(side_effect=AssertionError("unplanned narrative path"))
                state = agent._build_graph().invoke(agent._initial_state(
                    "Explain shared operations and service provision.", {}))
                execution = state["numeric_result"]["execution"]
                self.assertEqual(execution["status"], "ok" if covered else "partial")
                self.assertEqual(execution["missing_obligation_ids"], [] if covered else ["ob_002"])
                final = state["final_result"]
                self.assertIn("The teams combine shared operations.", final["agent_answer"]["answer"])
                result = final["agent_answer"]["structured_result"]
                self.assertEqual(result["status"], "ok" if covered else "partial")
                self.assertEqual(result["missing_obligation_ids"], [] if covered else ["ob_002"])
                self.assertEqual(len(llm.prompts), 3)
                agent._extract_evidence.assert_not_called()
                ledger = state["ledger"]
                self.assertEqual(ledger["task_artifact_trace"]["integrity_status"], "ok")
                artifact = next(item for item in ledger["artifacts"] if item["kind"] == "aggregated_answer")
                self.assertEqual(artifact["payload"]["structured_result"], result)
                aggregate = next(item for item in ledger["tasks"] if item["task_id"] == "aggregate")
                self.assertEqual(aggregate["status"], "completed" if covered else "partial")

    def test_query_years_are_not_a_fixed_stopword_list(self):
        expected = evidence_extraction_focus_terms("운영 구성 설명")
        for year in (2022, 2024, 2038, 2091):
            with self.subTest(year=year):
                self.assertEqual(evidence_extraction_focus_terms(f"{year}년 운영 구성 설명"), expected)
        collections = (CALCULATION_NARRATIVE_POLICY["context_stopwords"],
                       QUERY_FOCUS_STOPWORDS, EVIDENCE_EXTRACTION_POLICY["focus_term_stopwords"])
        for values in collections:
            self.assertFalse(any(str(value).removesuffix("년").isdigit() and len(str(value).removesuffix("년")) == 4
                                 for value in values))

    def test_policy_clause_has_no_absolute_period_priority(self):
        agent = self._agent(None)
        for first, second in (("2038", "2024"), ("2024", "2038")):
            text = f"{first} first source sentence. {second} 2026 second source sentence."
            self.assertEqual(agent._extract_dividend_policy_clause(text), text)
        self.assertNotIn("preferred_policy_period_markers", DIVIDEND_POLICY_ASSEMBLY_POLICY)
        self.assertNotIn("stale_policy_period_markers", DIVIDEND_POLICY_ASSEMBLY_POLICY)


if __name__ == "__main__":
    unittest.main()
