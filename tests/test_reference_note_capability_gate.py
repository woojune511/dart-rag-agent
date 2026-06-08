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

from src.config.reference_note_capability import reference_note_capability_status  # noqa: E402
from src.ops.reference_note_capability_gate import render_text, run_gate  # noqa: E402


class ReferenceNoteCapabilityGateTests(unittest.TestCase):
    def test_reference_note_status_is_researcher_context_only(self) -> None:
        status = reference_note_capability_status()

        self.assertEqual(status["status"], "graph_expansion_context_only")
        self.assertEqual(status["owner"], "researcher_graph_expansion")
        self.assertEqual(status["graph_relation"], "reference_note")
        self.assertEqual(status["artifact_kind"], "retrieval_bundle")
        self.assertTrue(status["retrieval_context_enabled"])
        self.assertFalse(status["cache_read_source"])
        self.assertFalse(status["cache_serving_enabled"])
        self.assertFalse(status["retrieval_bypass_enabled"])
        self.assertFalse(status["ledger_insertion_enabled"])
        self.assertFalse(status["final_acceptance_enabled"])
        self.assertEqual(status["report_cache_origin"], "")
        self.assertIn("researcher.retrieval_bundle", status["allowed_surfaces"])
        self.assertIn("report_cache_entry.source", status["blocked_surfaces"])
        self.assertIn("final_answer.acceptance_authority", status["blocked_surfaces"])

    def test_run_gate_reports_ready_boundary(self) -> None:
        result = run_gate()

        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["disabled_flags_ok"])
        self.assertEqual(result["issue_ids"], [])

    def test_render_text_includes_disabled_serving_boundary(self) -> None:
        text = render_text(run_gate())

        self.assertIn("# REFERENCE_NOTE Capability Gate", text)
        self.assertIn("Status: ready", text)
        self.assertIn("Owner: researcher_graph_expansion", text)
        self.assertIn("Graph relation: reference_note", text)
        self.assertIn("Cache serving enabled: false", text)
        self.assertIn("Retrieval bypass enabled: false", text)
        self.assertIn("Final acceptance enabled: false", text)

    def test_cli_writes_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "reference_note_gate.json"

            gate_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.reference_note_capability_gate",
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
            self.assertIn('"status": "ready"', gate_result.stdout)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ready")
            self.assertFalse(payload["capability"]["cache_serving_enabled"])
            self.assertFalse(payload["capability"]["retrieval_bypass_enabled"])


if __name__ == "__main__":
    unittest.main()
