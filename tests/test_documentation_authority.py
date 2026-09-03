from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentationAuthorityTests(unittest.TestCase):
    def test_current_authority_documents_remain_bounded(self) -> None:
        limits = {
            "AGENTS.md": 220,
            "CONTEXT.md": 150,
            "docs/README.md": 220,
            "docs/architecture/agent_runtime_contract.md": 350,
            "docs/overview/project_status.md": 150,
        }

        for relative_path, maximum_lines in limits.items():
            with self.subTest(path=relative_path):
                lines = (ROOT / relative_path).read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(len(lines), maximum_lines)

    def test_retired_work_queues_are_marked_historical(self) -> None:
        retired = (
            "DECISIONS.md",
            "PLAN.md",
            "docs/architecture/core_runtime_surface_refactoring_plan.md",
            "docs/evaluation/runtime_contract_gate.md",
            "docs/planning/backlog_and_next_epics.md",
        )

        for relative_path in retired:
            with self.subTest(path=relative_path):
                preamble = "\n".join(
                    (ROOT / relative_path)
                    .read_text(encoding="utf-8")
                    .splitlines()[:12]
                ).lower()
                self.assertIn("historical", preamble)


if __name__ == "__main__":
    unittest.main()
