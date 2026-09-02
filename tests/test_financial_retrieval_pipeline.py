import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_evidence import FinancialAgentEvidenceMixin
from src.agent.financial_retrieval_pipeline import FinancialRetrievalPipelineMixin


class FinancialRetrievalPipelineTests(unittest.TestCase):
    def test_retrieval_node_has_one_implementation_owner(self) -> None:
        self.assertIn("_retrieve", FinancialRetrievalPipelineMixin.__dict__)
        self.assertNotIn("_retrieve", FinancialAgentEvidenceMixin.__dict__)
        self.assertTrue(issubclass(FinancialAgent, FinancialRetrievalPipelineMixin))

    def test_retrieval_boundary_runs_four_stages_in_order(self) -> None:
        calls = []

        class Harness(FinancialRetrievalPipelineMixin):
            def _build_plan(self, state):
                calls.append(("build_plan", state))
                return {"plan": True}

            def _execute_searches(self, state, plan):
                calls.append(("execute_searches", plan))
                return {"searches": True}

            def _select_evidence(self, state, plan, searches):
                calls.append(("select_evidence", searches))
                return {"selection": True}

            def _build_trace(self, state, plan, searches, selection):
                calls.append(("build_trace", selection))
                return {"done": True}

        state = {"query": "q"}
        result = Harness()._retrieve(state)

        self.assertEqual(result, {"done": True})
        self.assertEqual(
            [name for name, _payload in calls],
            ["build_plan", "execute_searches", "select_evidence", "build_trace"],
        )


if __name__ == "__main__":
    unittest.main()
