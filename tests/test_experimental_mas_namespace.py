import unittest

from src.agent.mas_graph import run_mas_graph as legacy_run_mas_graph
from src.agent.mas_types import TaskStatus as LegacyTaskStatus
from src.agent.nodes.analyst_node import make_run_analyst as legacy_make_run_analyst
from src.agent.nodes.researcher_node import _build_enriched_query as legacy_build_enriched_query
from src.experimental.mas import TaskStatus, run_mas_graph
from src.experimental.mas.diagnostics import build_researcher_probe_query
from src.experimental.mas.nodes import make_run_analyst


class ExperimentalMasNamespaceTests(unittest.TestCase):
    def test_experimental_namespace_reexports_existing_mas_surface(self) -> None:
        self.assertIs(run_mas_graph, legacy_run_mas_graph)
        self.assertIs(TaskStatus, LegacyTaskStatus)
        self.assertIs(make_run_analyst, legacy_make_run_analyst)

    def test_experimental_diagnostics_wrap_researcher_probe_helpers(self) -> None:
        report_scope = {"company": "ACME", "year": "2023", "report_type": "annual"}

        self.assertEqual(
            build_researcher_probe_query("summarize evidence", report_scope),
            legacy_build_enriched_query("summarize evidence", report_scope),
        )

    def test_experimental_namespace_runs_dummy_mas_graph(self) -> None:
        final = run_mas_graph("삼성전자 24년 분석해줘")

        self.assertEqual(final["tasks"]["task_1"]["status"], TaskStatus.COMPLETED)
        self.assertEqual(final["tasks"]["task_2"]["status"], TaskStatus.COMPLETED)
        self.assertEqual(final["task_artifact_trace"]["integrity_status"], "ok")
        self.assertIn("Orchestrator merged final report", final["execution_trace"])


if __name__ == "__main__":
    unittest.main()
