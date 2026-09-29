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

from src.ops.portfolio_review_gates import render_text, run_review_gates  # noqa: E402


class PortfolioReviewGateTests(unittest.TestCase):
    def test_run_review_gates_aggregates_ready_subgates(self) -> None:
        result = run_review_gates()

        self.assertEqual(result["status"], "review_surface_ready")
        self.assertEqual(result["scope"], "review_surface_only")
        self.assertEqual(result["publication_validation"]["status"], "not_run")
        self.assertEqual(result["publication_validation"]["unit_tests"], "not_run")
        self.assertEqual(
            result["publication_validation"]["runtime_domain_term_audit"],
            "not_run",
        )
        self.assertIsNone(result["publication_validation"]["publication_ready"])
        self.assertTrue(
            result["checks"]["portfolio_demo_fixture_contract_ready"]
        )
        self.assertEqual(
            result["portfolio_demo"]["readiness"],
            "fixture_contract_ready",
        )
        self.assertEqual(result["portfolio_demo"]["scope"], "fixture_contract")
        self.assertEqual(result["portfolio_demo"]["fixture_evidence"], "verified")
        self.assertEqual(
            result["portfolio_demo"]["contract_checks_passed"],
            result["portfolio_demo"]["contract_check_count"],
        )

    def test_render_text_includes_subgate_sections(self) -> None:
        text = render_text(run_review_gates())

        self.assertIn("# Portfolio Review Gates", text)
        self.assertIn("Status: review_surface_ready", text)
        self.assertIn("Scope: review_surface_only", text)
        self.assertIn("Publication Validation: not_run", text)
        self.assertIn("unit_tests: not_run", text)
        self.assertIn("runtime_domain_term_audit: not_run", text)
        self.assertIn("Portfolio Demo:", text)
        self.assertIn("readiness: fixture_contract_ready", text)
        self.assertIn("fixture_evidence: verified", text)

    def test_cli_writes_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "portfolio_review_gates.json"

            gate_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.portfolio_review_gates",
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

            self.assertEqual(gate_result.returncode, 0, gate_result.stderr)
            self.assertIn('"status": "review_surface_ready"', gate_result.stdout)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "review_surface_ready")
            self.assertEqual(payload["scope"], "review_surface_only")
            self.assertEqual(payload["publication_validation"]["status"], "not_run")


if __name__ == "__main__":
    unittest.main()
