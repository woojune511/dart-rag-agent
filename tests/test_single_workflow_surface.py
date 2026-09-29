"""No classification transport or inferred filing scope before the Planner."""

import unittest
from unittest.mock import patch

from src.agent.financial_graph import FinancialAgent, planning_phase_input


class SingleWorkflowSurfaceTests(unittest.TestCase):
    def test_initialization_and_graph_need_no_routing_embeddings(self):
        class Store:
            @property
            def embeddings(self):
                raise AssertionError("Classification must not request embeddings")

        with patch("src.agent.financial_graph._load_env_once"), patch.object(
            FinancialAgent, "_build_llm_routes", return_value={"default": object()},
        ):
            agent = FinancialAgent(Store())

        graph = agent.graph.get_graph()
        entry_targets = [edge.target for edge in graph.edges if edge.source == "__start__"]
        self.assertEqual(entry_targets, ["plan_requirements"])
        self.assertNotIn("route_request", graph.nodes)
        self.assertFalse(hasattr(agent, "query_router"))

    def test_planner_gets_exact_request_and_only_explicit_filing_scope(self):
        query = "Compare 2041 and 2042, keeping the original units.\nExplain uncertainty."
        unscoped = planning_phase_input(FinancialAgent._initial_state(query, None))
        self.assertEqual(unscoped["query"], query)
        self.assertEqual(unscoped["topic"], query)
        self.assertEqual(unscoped["years"], [])
        self.assertEqual(unscoped["companies"], [])

        scope = {"company": "Issuer", "year": 2043, "rcept_no": "filing-2043"}
        state = FinancialAgent._initial_state(query, scope)
        scoped = planning_phase_input(state)
        self.assertEqual(scoped["years"], [2043])
        self.assertEqual(scoped["companies"], ["Issuer"])
        self.assertEqual(scoped["query"], query)
        self.assertEqual(scoped["report_scope"], scope)
        scoped["companies"].append("Other")
        self.assertEqual(state["request"]["report_scope"], scope)


if __name__ == "__main__":
    unittest.main()
