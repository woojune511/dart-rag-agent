import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_evidence import FinancialAgentEvidenceMixin
from src.agent.financial_retrieval_pipeline import FinancialRetrievalPipelineMixin


class FinancialRetrievalPipelineTests(unittest.TestCase):
    def test_retrieval_node_has_one_implementation_owner(self) -> None:
        self.assertIn("_retrieve", FinancialRetrievalPipelineMixin.__dict__)
        self.assertNotIn("_retrieve", FinancialAgentEvidenceMixin.__dict__)
        self.assertTrue(issubclass(FinancialAgent, FinancialRetrievalPipelineMixin))


if __name__ == "__main__":
    unittest.main()
