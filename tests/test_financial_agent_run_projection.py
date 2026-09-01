from __future__ import annotations

import unittest

from src.agent.financial_agent_run_projection import project_review_trace
from src.agent.financial_graph import FinancialAgent


class _Graph:
    def __init__(self, final):
        self.final = final

    def invoke(self, _initial):
        return dict(self.final)


class _VectorStore:
    def reset_current_thread_embedding_usage(self):
        return None

    def get_current_thread_embedding_usage_snapshot(self):
        return {"calls": 0}


class FinancialAgentRunProjectionTests(unittest.TestCase):
    def test_review_trace_exposes_semantic_program_contract(self) -> None:
        final = {
            "retrieved_docs": [],
            "answer_obligations": [{"obligation_id": "ob_001"}],
            "semantic_candidate_catalog": [{"candidate_id": "cand_001"}],
            "semantic_program": {"status": "ready"},
            "semantic_program_validation": {"status": "ready"},
            "semantic_program_retry_count": 1,
        }
        review = project_review_trace(final, runtime_evidence=[], task_artifact_trace={})
        self.assertEqual(review["answer_obligations"], [{"obligation_id": "ob_001"}])
        self.assertEqual(review["semantic_candidate_catalog"], [{"candidate_id": "cand_001"}])
        self.assertEqual(review["semantic_program"]["status"], "ready")
        self.assertEqual(review["semantic_program_validation"]["status"], "ready")
        self.assertEqual(review["semantic_program_retry_count"], 1)

    def test_runtime_evidence_adapter_never_reconstructs_provenance_from_answer(self) -> None:
        self.assertEqual(
            FinancialAgent._runtime_evidence_from_retrieved_docs(
                {"answer": "value 42", "retrieved_docs": []}
            ),
            [],
        )
        evidence = [
            {"evidence_id": "cand_a", "claim": "A 10", "metadata": {}},
            {"evidence_id": "cand_b", "claim": "B 20", "metadata": {}},
        ]
        selected = FinancialAgent._runtime_evidence_from_retrieved_docs(
            {
                "runtime_evidence": evidence,
                "selected_claim_ids": ["cand_b"],
                "report_scope": {},
            }
        )
        self.assertEqual([item["evidence_id"] for item in selected], ["cand_b"])

    def test_run_projects_canonical_graph_answer_without_numeric_repair(self) -> None:
        trace = {
            "calculation_operands": [{"operand_id": "cand_a", "normalized_value": 10.0}],
            "calculation_plan": {"operation": "semantic_program", "program_mode": "semantic_program"},
            "calculation_result": {
                "status": "ok",
                "semantic_status": "ok",
                "formatted_result": "canonical answer: 10",
            },
        }
        final = {
            "query": "return the value",
            "report_scope": {},
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "companies": [],
            "years": [],
            "answer": "canonical answer: 10",
            "citations": [],
            "retrieved_docs": [],
            "resolved_calculation_trace": trace,
            "structured_result": {
                "status": "ok",
                "answer": "canonical answer: 10",
                "final_answer": "canonical answer: 10",
            },
            "runtime_evidence": [
                {
                    "evidence_id": "cand_a",
                    "claim": "value 10",
                    "source_anchor": "sample anchor",
                    "metadata": {},
                }
            ],
            "selected_claim_ids": ["cand_a"],
            "kept_claim_ids": ["cand_a"],
            "tasks": [],
            "artifacts": [],
        }
        agent = object.__new__(FinancialAgent)
        agent.graph = _Graph(final)
        agent.vsm = _VectorStore()
        agent.llm_usage_callback = None
        agent._project_runtime_calculation_trace = lambda _state: trace
        result = agent.run("return the value")
        self.assertEqual(result["answer"], "canonical answer: 10")
        self.assertEqual(result["resolved_calculation_trace"], trace)
        self.assertEqual([item["evidence_id"] for item in result["evidence_items"]], ["cand_a"])
        self.assertFalse(hasattr(FinancialAgent, "_repair_public_runtime_calculation_trace"))


if __name__ == "__main__":
    unittest.main()
