import unittest
from graphlib import TopologicalSorter

from src.ops.render_runtime_topology import (
    TOPOLOGY_DOCUMENT,
    render_topology,
    replace_checked_block,
)


class RuntimeTopologyDocumentTests(unittest.TestCase):
    def test_checked_topology_matches_financial_graph_source(self) -> None:
        document = TOPOLOGY_DOCUMENT.read_text(encoding="utf-8")
        self.assertEqual(replace_checked_block(document, render_topology()), document)

    def test_actual_graph_is_acyclic_and_final_result_precedes_ledger(self) -> None:
        from src.agent.financial_graph import FinancialAgent

        graph = object.__new__(FinancialAgent)._build_graph().get_graph()
        predecessors = {node: set() for node in graph.nodes}
        for edge in graph.edges:
            predecessors[edge.target].add(edge.source)
        ordered = list(TopologicalSorter(predecessors).static_order())
        self.assertEqual(predecessors["assemble_ledger"], {"assemble_final"})
        self.assertEqual(predecessors["__end__"], {"assemble_ledger"})
        self.assertLess(ordered.index("execute_numeric"), ordered.index("assemble_final"))
        self.assertLess(ordered.index("build_narrative"), ordered.index("assemble_final"))


if __name__ == "__main__":
    unittest.main()
