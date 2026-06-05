import contextlib
import io
import json
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

from src.ops.report_cache_index_smoke import build_smoke_payload, main  # noqa: E402


FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "report_cache_index" / "rehydration_diagnostics.json"


class ReportCacheIndexSmokeTests(unittest.TestCase):
    def test_build_smoke_payload_uses_first_fixture_key_by_default(self) -> None:
        payload = build_smoke_payload(report_cache_index_path=FIXTURE_PATH)

        self.assertEqual(payload["report_cache_index_path"], str(FIXTURE_PATH))
        self.assertEqual(payload["summary"]["status"], "trace_only")
        self.assertFalse(payload["summary"]["enabled"])
        self.assertFalse(payload["summary"]["serving_enabled"])
        self.assertEqual(payload["summary"]["match_count"], 2)
        self.assertEqual(payload["summary"]["readable_match_count"], 2)
        self.assertEqual(payload["summary"]["rehydration_ready_match_count"], 1)
        self.assertEqual(payload["summary"]["rehydration_blocked_match_count"], 1)
        self.assertEqual(payload["summary"]["rehydration_reason_counts"]["missing_answer_slots"], 1)
        self.assertEqual(payload["summary"]["index_status"], "loaded")
        self.assertEqual(payload["summary"]["index_rehydration_ready_count"], 1)
        self.assertEqual(payload["diagnostics"]["matches"][0]["rehydration"]["status"], "blocked")
        self.assertEqual(payload["diagnostics"]["matches"][1]["rehydration"]["status"], "ready")

    def test_main_prints_and_optionally_writes_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report_cache_index_smoke.json"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--report-cache-index-path",
                        str(FIXTURE_PATH),
                        "--output",
                        str(output_path),
                    ]
                )

            printed = json.loads(stdout.getvalue())
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(printed["summary"], written["summary"])
        self.assertEqual(printed["summary"]["status"], "trace_only")
        self.assertFalse(printed["summary"]["serving_enabled"])
        self.assertEqual(printed["summary"]["rehydration_ready_match_count"], 1)
        self.assertEqual(printed["summary"]["rehydration_blocked_match_count"], 1)


if __name__ == "__main__":
    unittest.main()
