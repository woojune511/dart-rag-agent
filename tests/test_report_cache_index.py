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

from src.config.report_scoped_cache import (  # noqa: E402
    CACHE_CONSUMER_ADMISSIBLE_FOR_DESIGN,
    CACHE_CONSUMER_FALLBACK_REQUIRED,
    CACHE_ENTRY_SOURCE_ARTIFACT_STORE,
    CACHE_ENTRY_SOURCE_LOCAL_INDEX,
    REPORT_CACHE_ENTRY_VERSION,
    build_report_cache_rehydrated_candidate_artifact,
    classify_report_cache_guarded_consumer_candidate,
    normalise_report_cache_key,
    report_cache_key_id,
)
from src.storage.report_cache_index import ReportCacheIndex  # noqa: E402


def _entry(*, source: str = CACHE_ENTRY_SOURCE_LOCAL_INDEX, value: str = "123", rehydratable: bool = False) -> dict:
    key = normalise_report_cache_key(
        {
            "company": "ACME",
            "report_type": "annual",
            "rcept_no": "r1",
            "year": "2023",
            "metric_label": "metric",
            "period": "2023",
            "consolidation_scope": "consolidated",
            "statement_type": "income_statement",
            "source_section": "section",
            "source_table_id": "section::table:1",
        }
    )
    entry = {
        "entry_version": REPORT_CACHE_ENTRY_VERSION,
        "source": source,
        "key": key,
        "key_id": report_cache_key_id(key),
        "value": {"kind": "calculation_result", "rendered_value": value},
        "provenance": {"source_row_ids": ["row-1"], "evidence_refs": ["ev-1"]},
    }
    if rehydratable:
        entry["value"].update(
            {
                "answer_slots": {"primary_value": {"display": value, "raw_value": value}},
                "calculation_trace": {
                    "calculation_result": {"status": "ok", "rendered_value": value},
                    "calculation_operands": [{"label": "metric", "raw_value": value}],
                },
                "citations": ["[ACME | 2023 | section]"],
                "evidence_items": [{"source_anchor": "section", "claim": f"metric was {value}"}],
            }
        )
        entry["provenance"]["source_anchor"] = "section"
    return entry


class ReportCacheIndexTests(unittest.TestCase):
    def test_missing_index_reports_diagnostics_without_serving(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            diagnostics = ReportCacheIndex(Path(temp_dir) / "missing.json").load_diagnostics()

        self.assertEqual(diagnostics["status"], "missing")
        self.assertFalse(diagnostics["enabled"])
        self.assertFalse(diagnostics["serving_enabled"])
        self.assertEqual(diagnostics["entries"], [])

    def test_json_index_loads_readable_and_blocked_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report_cache_index.json"
            path.write_text(
                json.dumps(
                    {
                        "entries": [
                            _entry(),
                            _entry(source=CACHE_ENTRY_SOURCE_ARTIFACT_STORE),
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            diagnostics = ReportCacheIndex(path).load_diagnostics()

        self.assertEqual(diagnostics["status"], "loaded")
        self.assertFalse(diagnostics["serving_enabled"])
        self.assertEqual(diagnostics["readable_count"], 1)
        self.assertEqual(diagnostics["rehydration_ready_count"], 0)
        self.assertEqual(diagnostics["blocked_count"], 1)
        self.assertEqual(diagnostics["entries"][0]["status"], "readable")
        self.assertEqual(diagnostics["entries"][0]["rehydration"]["status"], "blocked")
        self.assertIn("missing_answer_slots", diagnostics["entries"][0]["rehydration"]["reasons"])
        self.assertEqual(diagnostics["entries"][1]["status"], "blocked")
        self.assertIn("non_read_source", diagnostics["entries"][1]["reasons"])

    def test_jsonl_index_counts_malformed_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report_cache_index.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps(_entry(), ensure_ascii=False),
                        "{not-json",
                        json.dumps(["not", "entry"], ensure_ascii=False),
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = ReportCacheIndex(path).load_diagnostics()

        self.assertEqual(diagnostics["status"], "loaded")
        self.assertEqual(diagnostics["readable_count"], 1)
        self.assertEqual(diagnostics["malformed_count"], 2)

    def test_malformed_json_returns_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report_cache_index.json"
            path.write_text("{not-json", encoding="utf-8")

            diagnostics = ReportCacheIndex(path).load_diagnostics()

        self.assertEqual(diagnostics["status"], "malformed")
        self.assertFalse(diagnostics["serving_enabled"])
        self.assertEqual(diagnostics["malformed_count"], 1)

    def test_lookup_diagnostics_match_key_without_serving_hit(self) -> None:
        entry = _entry()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report_cache_index.json"
            path.write_text(json.dumps([entry], ensure_ascii=False), encoding="utf-8")

            diagnostics = ReportCacheIndex(path).lookup_diagnostics(entry["key"])

        self.assertEqual(diagnostics["status"], "trace_only")
        self.assertFalse(diagnostics["enabled"])
        self.assertFalse(diagnostics["serving_enabled"])
        self.assertEqual(diagnostics["match_count"], 1)
        self.assertEqual(diagnostics["readable_match_count"], 1)
        self.assertEqual(diagnostics["rehydration_ready_match_count"], 0)
        self.assertEqual(diagnostics["rehydration_blocked_match_count"], 1)
        self.assertEqual(diagnostics["rehydration_reason_counts"]["missing_answer_slots"], 1)
        self.assertEqual(diagnostics["key_id"], entry["key_id"])

    def test_lookup_diagnostics_counts_rehydration_ready_matches_without_serving(self) -> None:
        entry = _entry(rehydratable=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report_cache_index.json"
            path.write_text(json.dumps([entry], ensure_ascii=False), encoding="utf-8")

            diagnostics = ReportCacheIndex(path).lookup_diagnostics(entry["key"])

        self.assertEqual(diagnostics["status"], "trace_only")
        self.assertFalse(diagnostics["enabled"])
        self.assertFalse(diagnostics["serving_enabled"])
        self.assertEqual(diagnostics["match_count"], 1)
        self.assertEqual(diagnostics["readable_match_count"], 1)
        self.assertEqual(diagnostics["rehydration_ready_match_count"], 1)
        self.assertEqual(diagnostics["rehydration_blocked_match_count"], 0)
        self.assertEqual(diagnostics["rehydration_reason_counts"], {})
        self.assertEqual(diagnostics["matches"][0]["rehydration"]["status"], "ready")

    def test_fixture_reports_readable_and_rehydratable_match_counts(self) -> None:
        fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "report_cache_index" / "rehydration_diagnostics.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        key = payload["entries"][0]["key"]

        diagnostics = ReportCacheIndex(fixture_path).lookup_diagnostics(key)

        self.assertEqual(diagnostics["status"], "trace_only")
        self.assertFalse(diagnostics["enabled"])
        self.assertFalse(diagnostics["serving_enabled"])
        self.assertEqual(diagnostics["match_count"], 2)
        self.assertEqual(diagnostics["readable_match_count"], 2)
        self.assertEqual(diagnostics["rehydration_ready_match_count"], 1)
        self.assertEqual(diagnostics["rehydration_blocked_match_count"], 1)
        self.assertEqual(diagnostics["rehydration_reason_counts"]["missing_answer_slots"], 1)
        self.assertEqual(diagnostics["index"]["rehydration_ready_count"], 1)
        self.assertEqual(
            [item["rehydration"]["status"] for item in diagnostics["matches"]],
            ["blocked", "ready"],
        )

    def test_fixture_rehydrated_candidate_artifact_only_uses_ready_entry(self) -> None:
        fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "report_cache_index" / "rehydration_diagnostics.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        blocked_entry, ready_entry = payload["entries"]

        blocked = build_report_cache_rehydrated_candidate_artifact(blocked_entry)
        ready = build_report_cache_rehydrated_candidate_artifact(
            ready_entry,
            task_id="task_1",
            artifact_id="cache::candidate::fixture",
        )

        self.assertFalse(blocked["ready"])
        self.assertIsNone(blocked["artifact"])
        self.assertTrue(ready["ready"])
        self.assertFalse(ready["enabled"])
        self.assertFalse(ready["serving_enabled"])
        self.assertEqual(ready["artifact"]["status"], "candidate")
        self.assertEqual(ready["artifact"]["payload"]["answer"], "123")
        self.assertEqual(
            ready["artifact"]["payload"]["resolved_calculation_trace"]["calculation_result"]["status"],
            "ok",
        )
        self.assertFalse(ready["artifact"]["payload"]["report_cache_rehydration"]["serving_enabled"])

    def test_fixture_guarded_consumer_classifies_ready_and_blocked_entries_without_serving(self) -> None:
        fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "report_cache_index" / "rehydration_diagnostics.json"
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        blocked_entry, ready_entry = payload["entries"]

        blocked = classify_report_cache_guarded_consumer_candidate(blocked_entry)
        ready = classify_report_cache_guarded_consumer_candidate(ready_entry)

        self.assertEqual(blocked["status"], CACHE_CONSUMER_FALLBACK_REQUIRED)
        self.assertTrue(blocked["fallback_required"])
        self.assertIn("missing_answer_slots", blocked["reasons"])
        self.assertEqual(ready["status"], CACHE_CONSUMER_ADMISSIBLE_FOR_DESIGN)
        self.assertTrue(ready["admissible"])
        self.assertFalse(ready["enabled"])
        self.assertFalse(ready["serving_enabled"])


if __name__ == "__main__":
    unittest.main()
