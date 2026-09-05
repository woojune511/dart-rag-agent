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

    def test_source_graph_is_acyclic_and_final_result_precedes_ledger(self) -> None:
        edge_block = render_topology().split("edges:\n", 1)[1].split("\n```", 1)[0]
        predecessors: dict[str, set[str]] = {}
        for raw_edge in edge_block.splitlines():
            edge = raw_edge.strip()
            if " --> " in edge:
                source = edge.split(" -- ", 1)[0]
                target = edge.rsplit(" --> ", 1)[1]
            else:
                source, target = edge.split(" -> ", 1)
            if target == "END":
                target = "__end__"
            predecessors.setdefault(source, set())
            predecessors.setdefault(target, set()).add(source)
        ordered = list(TopologicalSorter(predecessors).static_order())
        self.assertEqual(predecessors["assemble_ledger"], {"assemble_final"})
        self.assertEqual(predecessors["__end__"], {"assemble_ledger"})
        self.assertLess(ordered.index("execute_numeric"), ordered.index("assemble_final"))
        self.assertLess(ordered.index("build_narrative"), ordered.index("assemble_final"))


if __name__ == "__main__":
    unittest.main()
