import unittest

from src.ops.render_runtime_topology import (
    TOPOLOGY_DOCUMENT,
    render_topology,
    replace_checked_block,
)


class RuntimeTopologyDocumentTests(unittest.TestCase):
    def test_checked_topology_matches_financial_graph_source(self) -> None:
        document = TOPOLOGY_DOCUMENT.read_text(encoding="utf-8")
        self.assertEqual(replace_checked_block(document, render_topology()), document)


if __name__ == "__main__":
    unittest.main()
