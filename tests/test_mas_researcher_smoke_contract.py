import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.mas_researcher_smoke import _critic_acceptance_summary  # noqa: E402


class MasResearcherSmokeContractTests(unittest.TestCase):
    def test_critic_acceptance_summary_uses_runtime_contract_not_score(self) -> None:
        summary = _critic_acceptance_summary(
            {
                "passed": False,
                "verdict": "rejected",
                "target_task_id": "task_2",
                "blocking_issues": ["missing evidence"],
                "deterministic_score": 1.0,
            }
        )

        self.assertFalse(summary["accepted"])
        self.assertEqual(summary["status"], "blocked")
        self.assertIn("critic_rejected", summary["reasons"])
        self.assertFalse(summary["deterministic_score_used_for_acceptance"])


if __name__ == "__main__":
    unittest.main()
