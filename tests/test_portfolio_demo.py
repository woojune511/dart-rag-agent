import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.portfolio_demo import build_demo, render_text  # noqa: E402


class PortfolioDemoTests(unittest.TestCase):
    def test_build_demo_summarizes_runtime_contract_surfaces(self) -> None:
        demo = build_demo()

        self.assertEqual(demo["readiness"]["status"], "ready")
        self.assertEqual(demo["structured_result"]["rendered_value"], "37.47%")
        self.assertEqual(
            demo["resolved_calculation_trace"]["calculation_result"]["status"],
            "ok",
        )
        self.assertEqual(demo["task_artifact_integrity"]["integrity_status"], "ok")
        self.assertEqual(demo["critic_acceptance"]["status"], "accepted")
        self.assertEqual(demo["cache_reviewer_handoff"]["status"], "ready")
        self.assertFalse(demo["cache_reviewer_handoff"]["retrieval_bypass_enabled"])
        self.assertFalse(demo["cache_reviewer_handoff"]["write_enabled"])
        self.assertFalse(demo["cache_reviewer_handoff"]["serving_enabled"])

    def test_demo_critic_acceptance_uses_runtime_contract_not_score(self) -> None:
        fixture_path = (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "portfolio_demo"
            / "demo_payload.json"
        )
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        report = payload["answer_package"]["critic_reports"][0]
        report["passed"] = True
        report["verdict"] = "passed"
        report["deterministic_score"] = 1.0
        report["acceptance_reason"] = ""

        with tempfile.TemporaryDirectory() as temp_dir:
            payload_path = Path(temp_dir) / "demo_payload.json"
            payload_path.write_text(json.dumps(payload), encoding="utf-8")

            demo = build_demo(demo_payload_path=payload_path, include_cache_review=False)

        self.assertEqual(demo["critic_acceptance"]["status"], "blocked")
        self.assertIn(
            "missing_acceptance_reason",
            demo["critic_acceptance"]["runtime_acceptance_reasons"],
        )
        self.assertFalse(
            demo["critic_acceptance"]["deterministic_score_used_for_acceptance"]
        )
        self.assertEqual(demo["readiness"]["status"], "needs_review")

    def test_render_text_includes_portfolio_sections(self) -> None:
        text = render_text(build_demo(include_cache_review=False))

        self.assertIn("# Portfolio Runtime Demo", text)
        self.assertIn("Calculation Trace:", text)
        self.assertIn("Task/Artifact Integrity:", text)
        self.assertIn("Critic Acceptance:", text)
        self.assertIn("Cache Reviewer Handoff:", text)
        self.assertIn("retrieval_bypass_enabled:", text)
        self.assertIn("write_enabled:", text)

    def test_cli_writes_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "portfolio_demo.json"

            demo_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.portfolio_demo",
                    "--format",
                    "json",
                    "--output",
                    str(output),
                ],
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(demo_result.returncode, 0, demo_result.stderr)
            self.assertIn('"readiness"', demo_result.stdout)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["readiness"]["status"], "ready")
            self.assertEqual(payload["cache_reviewer_handoff"]["mode"], "candidate_only")


if __name__ == "__main__":
    unittest.main()
