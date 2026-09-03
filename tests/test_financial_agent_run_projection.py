from __future__ import annotations

import unittest
from collections.abc import Mapping

from src.agent.financial_agent_run_projection import (
    project_query_retrieval_status,
    project_review_trace,
)
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_run_result import FINANCIAL_RUN_RESULT_SCHEMA_VERSION


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
    def test_query_retrieval_status_reports_any_bm25_fallback(self) -> None:
        status = project_query_retrieval_status(
            {
                "retrieval_debug_trace_history": [
                    {
                        "executed_queries": [
                            {
                                "search_telemetry": {
                                    "retrieval_mode": "hybrid",
                                }
                            },
                            {
                                "search_telemetry": {
                                    "retrieval_mode": "bm25_fallback",
                                    "vector_skipped_reason": "vector_store_read_error",
                                }
                            },
                        ]
                    }
                ]
            }
        )

        self.assertEqual(
            status,
            {
                "degraded": True,
                "modes": ["bm25_fallback"],
                "reasons": ["vector_store_read_error"],
            },
        )

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
        result = agent.run("return the value", include_review_trace=True)
        self.assertEqual(result.schema_version, FINANCIAL_RUN_RESULT_SCHEMA_VERSION)
        self.assertEqual(result.agent_answer["answer"], "canonical answer: 10")
        self.assertEqual(result.agent_answer["resolved_calculation_trace"], trace)
        self.assertEqual(
            [item["evidence_id"] for item in result.review_trace["evidence_items"]],
            ["cand_a"],
        )
        self.assertIsNone(result.debug_bundle)
        self.assertNotIsInstance(result, Mapping)
        self.assertFalse(hasattr(result, "get"))
        self.assertFalse(hasattr(result, "__getitem__"))
        self.assertFalse(hasattr(FinancialAgent, "_repair_public_runtime_calculation_trace"))

    def test_review_and_debug_payloads_are_absent_by_default(self) -> None:
        final = {
            "query": "q",
            "report_scope": {},
            "query_type": "qa",
            "companies": [],
            "years": [],
            "answer": "a",
            "citations": [],
            "retrieved_docs": [],
            "tasks": [],
            "artifacts": [],
        }
        agent = object.__new__(FinancialAgent)
        agent.graph = _Graph(final)
        agent.vsm = _VectorStore()
        agent.llm_usage_callback = None
        agent._project_runtime_calculation_trace = lambda _state: {}

        result = agent.run("q")

        self.assertIsNone(result.review_trace)
        self.assertIsNone(result.debug_bundle)
        self.assertEqual(
            set(result.to_projection()),
            {"schema_version", "agent_answer"},
        )


if __name__ == "__main__":
    unittest.main()
