import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.config.report_scoped_cache import (
    CACHE_NOT_CACHEABLE,
    CACHE_REQUIRES_EVIDENCE_VERIFICATION,
    CACHE_REUSABLE,
    classify_report_cache_candidate,
    missing_key_fields,
    normalise_report_cache_key,
    report_cache_key_id,
)
from src.agent.financial_graph_helpers import _resolve_runtime_calculation_trace, _runtime_trace_state_update


class ReportScopedCacheContractTests(unittest.TestCase):
    def test_normalise_report_cache_key_uses_report_scope_value_identity_and_provenance_scope(self) -> None:
        key = normalise_report_cache_key(
            {
                "company": "  ACME  ",
                "report_type": "사업보고서",
                "rcept_no": "20240312000736",
                "year": 2023,
                "concept": "operating_margin",
                "label": " operating margin ",
                "period_label": "2023",
                "consolidation_scope": "consolidated",
                "statement_type": "income_statement",
                "section_path": "III. financial statements",
                "table_source_id": "tbl-1",
            }
        )

        self.assertEqual(key["company"], "ACME")
        self.assertEqual(key["year"], "2023")
        self.assertEqual(key["concept_id"], "operating_margin")
        self.assertEqual(key["metric_label"], "operating margin")
        self.assertEqual(key["source_section"], "III. financial statements")
        self.assertEqual(key["source_table_id"], "tbl-1")

    def test_report_cache_key_id_is_stable_for_field_order(self) -> None:
        first = {
            "company": "ACME",
            "report_type": "annual",
            "rcept_no": "r1",
            "year": "2023",
            "concept_id": "metric",
            "period": "2023",
        }
        second = dict(reversed(list(first.items())))

        self.assertEqual(report_cache_key_id(first), report_cache_key_id(second))

    def test_missing_key_requires_report_scope_and_value_identity(self) -> None:
        missing = missing_key_fields({"company": "ACME", "year": "2023"})

        self.assertIn("report_type", missing)
        self.assertIn("rcept_no", missing)
        self.assertIn("concept_id_or_metric_label", missing)

    def test_structured_value_with_complete_scope_and_provenance_is_reusable(self) -> None:
        result = classify_report_cache_candidate(
            {
                "value_kind": "structured_row",
                "company": "ACME",
                "report_type": "annual",
                "rcept_no": "r1",
                "year": "2023",
                "concept_id": "metric",
                "period": "2023",
                "value_text": "123",
                "consolidation_scope": "consolidated",
                "statement_type": "income_statement",
                "source_section": "section",
                "table_source_id": "table-1",
                "source_row_id": "row-1",
            }
        )

        self.assertEqual(result["status"], CACHE_REUSABLE)
        self.assertEqual(result["reasons"], [])

    def test_prose_value_requires_evidence_verification_before_reuse(self) -> None:
        result = classify_report_cache_candidate(
            {
                "value_kind": "prose_lookup",
                "company": "ACME",
                "report_type": "annual",
                "rcept_no": "r1",
                "year": "2023",
                "metric_label": "metric",
                "value_text": "123",
                "source_anchor": "[ACME | 2023 | section]",
            }
        )

        self.assertEqual(result["status"], CACHE_REQUIRES_EVIDENCE_VERIFICATION)
        self.assertIn("missing_scope:consolidation_scope", result["reasons"])
        self.assertIn("missing_scope:statement_type", result["reasons"])
        self.assertIn("non_structured_value_kind", result["reasons"])

    def test_synthesized_or_value_free_payload_is_not_cacheable(self) -> None:
        synthesized = classify_report_cache_candidate(
            {
                "value_kind": "synthesized_answer",
                "company": "ACME",
                "report_type": "annual",
                "rcept_no": "r1",
                "year": "2023",
                "metric_label": "metric",
                "value_text": "123",
            }
        )
        empty = classify_report_cache_candidate(
            {
                "value_kind": "structured_row",
                "company": "ACME",
                "report_type": "annual",
                "rcept_no": "r1",
                "year": "2023",
                "metric_label": "metric",
                "source_anchor": "section",
            }
        )

        self.assertEqual(synthesized["status"], CACHE_NOT_CACHEABLE)
        self.assertEqual(empty["status"], CACHE_NOT_CACHEABLE)
        self.assertIn("missing_value", empty["reasons"])

    def test_runtime_trace_state_update_adds_read_only_cache_candidate(self) -> None:
        update = _runtime_trace_state_update(
            {
                "report_scope": {
                    "company": "ACME",
                    "report_type": "annual",
                    "rcept_no": "r1",
                    "year": "2023",
                },
                "active_subtask": {
                    "metric_family": "operating_margin",
                    "metric_label": "operating margin",
                },
            },
            calculation_operands=[
                {
                    "label": "operating income",
                    "raw_value": "123",
                    "period": "2023",
                    "consolidation_scope": "consolidated",
                    "statement_type": "income_statement",
                    "source_section": "III. financial statements",
                    "table_source_id": "table-1",
                    "source_row_id": "row-1",
                }
            ],
            calculation_plan={"operation": "lookup"},
            calculation_result={"status": "ok", "rendered_value": "123"},
        )

        candidate = update["resolved_calculation_trace"]["report_cache_candidate"]

        self.assertTrue(candidate["read_only"])
        self.assertEqual(candidate["status"], CACHE_REUSABLE)
        self.assertEqual(candidate["key"]["company"], "ACME")
        self.assertEqual(candidate["key"]["concept_id"], "operating_margin")
        self.assertIn("report-cache-v1:", candidate["key_id"])

    def test_runtime_trace_resolver_preserves_cache_candidate(self) -> None:
        resolved = _resolve_runtime_calculation_trace(
            {
                "resolved_calculation_trace": {
                    "calculation_operands": [{"label": "metric", "value": "123"}],
                    "calculation_plan": {"operation": "lookup"},
                    "calculation_result": {"status": "ok", "rendered_value": "123"},
                    "report_cache_candidate": {
                        "status": CACHE_REQUIRES_EVIDENCE_VERIFICATION,
                        "read_only": True,
                    },
                }
            },
            allow_legacy_top_level=False,
        )

        self.assertEqual(
            resolved["report_cache_candidate"]["status"],
            CACHE_REQUIRES_EVIDENCE_VERIFICATION,
        )


if __name__ == "__main__":
    unittest.main()
