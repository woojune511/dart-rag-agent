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
    CACHE_CONSUMER_BLOCKED,
    CACHE_CONSUMER_ADMISSIBLE_FOR_DESIGN,
    CACHE_CONSUMER_ELIGIBLE,
    CACHE_CONSUMER_FALLBACK_REQUIRED,
    CACHE_ENTRY_BLOCKED,
    CACHE_ENTRY_READABLE,
    CACHE_ENTRY_SOURCE_ARTIFACT_STORE,
    CACHE_ENTRY_SOURCE_LOCAL_INDEX,
    CACHE_ENTRY_SOURCE_RUNTIME_TRACE,
    CACHE_NOT_CACHEABLE,
    CACHE_REHYDRATION_BLOCKED,
    CACHE_REHYDRATION_READY,
    CACHE_PROJECTION_VALID_FOR_CONTRACT,
    CACHE_REQUIRES_EVIDENCE_VERIFICATION,
    CACHE_REUSABLE,
    REPORT_CACHE_ENTRY_VERSION,
    classify_report_cache_candidate,
    classify_report_cache_consumer_candidate,
    classify_report_cache_entry,
    classify_report_cache_guarded_consumer_candidate,
    classify_report_cache_rehydration_candidate,
    build_report_cache_calculation_contract_projection,
    build_report_cache_rehydrated_candidate_artifact,
    missing_key_fields,
    normalise_report_cache_entry,
    normalise_report_cache_key,
    report_cache_key_id,
    validate_report_cache_calculation_contract_projection,
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

    def test_reusable_read_only_projection_is_consumer_eligible_but_disabled(self) -> None:
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

        result = classify_report_cache_consumer_candidate(
            {
                "status": CACHE_REUSABLE,
                "reasons": [],
                "key": key,
                "key_id": report_cache_key_id(key),
                "read_only": True,
            }
        )

        self.assertEqual(result["status"], CACHE_CONSUMER_ELIGIBLE)
        self.assertTrue(result["eligible"])
        self.assertFalse(result["enabled"])
        self.assertEqual(result["mode"], "trace_only")
        self.assertEqual(result["reasons"], [])

    def test_consumer_blocks_non_reusable_or_incomplete_projection(self) -> None:
        result = classify_report_cache_consumer_candidate(
            {
                "status": CACHE_REQUIRES_EVIDENCE_VERIFICATION,
                "reasons": ["missing_scope:statement_type"],
                "key": {
                    "company": "ACME",
                    "report_type": "annual",
                    "rcept_no": "r1",
                    "year": "2023",
                    "metric_label": "metric",
                    "period": "2023",
                    "consolidation_scope": "consolidated",
                    "source_section": "section",
                },
            }
        )

        self.assertEqual(result["status"], CACHE_CONSUMER_BLOCKED)
        self.assertFalse(result["eligible"])
        self.assertIn("candidate_not_reusable", result["reasons"])
        self.assertIn("missing_read_only_projection", result["reasons"])
        self.assertIn("candidate_has_reasons", result["reasons"])
        self.assertIn("missing_scope:statement_type", result["reasons"])
        self.assertIn("missing_scope:source_table_id", result["reasons"])

    def test_consumer_blocks_mismatched_key_id(self) -> None:
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

        result = classify_report_cache_consumer_candidate(
            {
                "status": CACHE_REUSABLE,
                "reasons": [],
                "key": key,
                "key_id": "wrong",
                "read_only": True,
            }
        )

        self.assertEqual(result["status"], CACHE_CONSUMER_BLOCKED)
        self.assertIn("key_id_mismatch", result["reasons"])

    def test_persisted_local_index_entry_is_readable(self) -> None:
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
            "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
            "key": key,
            "key_id": report_cache_key_id(key),
            "value": {
                "kind": "calculation_result",
                "rendered_value": "123",
                "normalized_value": 123.0,
                "normalized_unit": "KRW",
            },
            "provenance": {
                "source_row_ids": ["row-1"],
                "evidence_refs": ["ev-1"],
                "source_anchor": "section",
            },
        }

        result = classify_report_cache_entry(entry)

        self.assertEqual(result["status"], CACHE_ENTRY_READABLE)
        self.assertTrue(result["readable"])
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["entry"]["source"], CACHE_ENTRY_SOURCE_LOCAL_INDEX)

    def test_runtime_trace_projection_is_not_a_read_source(self) -> None:
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

        result = classify_report_cache_entry(
            {
                "entry_version": REPORT_CACHE_ENTRY_VERSION,
                "source": CACHE_ENTRY_SOURCE_RUNTIME_TRACE,
                "key": key,
                "key_id": report_cache_key_id(key),
                "value": {"rendered_value": "123"},
                "provenance": {"source_row_ids": ["row-1"]},
            }
        )

        self.assertEqual(result["status"], CACHE_ENTRY_BLOCKED)
        self.assertFalse(result["readable"])
        self.assertIn("non_read_source", result["reasons"])

    def test_artifact_store_projection_is_not_a_read_source(self) -> None:
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

        result = classify_report_cache_entry(
            {
                "entry_version": REPORT_CACHE_ENTRY_VERSION,
                "source": CACHE_ENTRY_SOURCE_ARTIFACT_STORE,
                "key": key,
                "key_id": report_cache_key_id(key),
                "value": {"rendered_value": "123"},
                "provenance": {"source_row_ids": ["row-1"]},
            }
        )

        self.assertEqual(result["status"], CACHE_ENTRY_BLOCKED)
        self.assertIn("non_read_source", result["reasons"])

    def test_cache_entry_requires_value_and_provenance(self) -> None:
        result = classify_report_cache_entry(
            {
                "entry_version": REPORT_CACHE_ENTRY_VERSION,
                "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
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

        self.assertEqual(result["status"], CACHE_ENTRY_BLOCKED)
        self.assertIn("missing_value", result["reasons"])
        self.assertIn("missing_provenance", result["reasons"])

    def test_cache_entry_normalisation_keeps_value_and_provenance_surfaces(self) -> None:
        entry = normalise_report_cache_entry(
            {
                "entry_version": REPORT_CACHE_ENTRY_VERSION,
                "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
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
                "rendered_value": "123",
                "source_row_id": "row-1",
            }
        )

        self.assertEqual(entry["value"]["rendered_value"], "123")
        self.assertEqual(entry["provenance"]["source_row_ids"], ["row-1"])
        self.assertEqual(entry["key_id"], report_cache_key_id(entry["key"]))

    def test_rehydration_requires_answer_slots_citations_and_calculation_trace(self) -> None:
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

        result = classify_report_cache_rehydration_candidate(
            {
                "entry_version": REPORT_CACHE_ENTRY_VERSION,
                "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
                "key": key,
                "key_id": report_cache_key_id(key),
                "value": {"kind": "calculation_result", "rendered_value": "123"},
                "provenance": {"source_row_ids": ["row-1"]},
            }
        )

        self.assertEqual(result["entry_status"], CACHE_ENTRY_READABLE)
        self.assertEqual(result["status"], CACHE_REHYDRATION_BLOCKED)
        self.assertFalse(result["ready"])
        self.assertFalse(result["enabled"])
        self.assertFalse(result["serving_enabled"])
        self.assertIn("missing_answer_slots", result["reasons"])
        self.assertIn("missing_primary_answer_slot", result["reasons"])
        self.assertIn("missing_citation_or_source_anchor", result["reasons"])
        self.assertIn("missing_calculation_trace", result["reasons"])

    def test_rehydration_ready_entry_remains_disabled_for_future_consumer(self) -> None:
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
            "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
            "key": key,
            "key_id": report_cache_key_id(key),
            "value": {
                "kind": "calculation_result",
                "rendered_value": "123",
                "answer_slots": {"primary_value": {"display": "123", "raw_value": "123"}},
                "calculation_trace": {
                    "calculation_result": {"status": "ok", "rendered_value": "123"},
                    "calculation_operands": [{"label": "metric", "raw_value": "123"}],
                },
                "citations": ["[ACME | 2023 | section]"],
                "evidence_items": [{"source_anchor": "section", "claim": "metric was 123"}],
            },
            "provenance": {
                "source_row_ids": ["row-1"],
                "evidence_refs": ["ev-1"],
                "source_anchor": "section",
            },
        }

        result = classify_report_cache_rehydration_candidate(entry)

        self.assertEqual(result["status"], CACHE_REHYDRATION_READY)
        self.assertTrue(result["ready"])
        self.assertFalse(result["enabled"])
        self.assertFalse(result["serving_enabled"])
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["entry"]["value"]["answer_slots"]["primary_value"]["display"], "123")
        self.assertEqual(result["entry"]["value"]["citations"], ["[ACME | 2023 | section]"])

    def test_guarded_consumer_admits_rehydration_ready_entry_for_design_only(self) -> None:
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
        result = classify_report_cache_guarded_consumer_candidate(
            {
                "entry_version": REPORT_CACHE_ENTRY_VERSION,
                "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
                "key": key,
                "key_id": report_cache_key_id(key),
                "value": {
                    "kind": "calculation_result",
                    "rendered_value": "123",
                    "answer_slots": {"primary_value": {"display": "123", "raw_value": "123"}},
                    "calculation_trace": {
                        "calculation_result": {"status": "ok", "rendered_value": "123"},
                        "calculation_operands": [{"label": "metric", "raw_value": "123"}],
                    },
                    "citations": ["[ACME | 2023 | section]"],
                    "evidence_items": [{"source_anchor": "section", "claim": "metric was 123"}],
                },
                "provenance": {
                    "source_row_ids": ["row-1"],
                    "evidence_refs": ["ev-1"],
                    "source_anchor": "section",
                },
            },
            expected_key=key,
        )

        self.assertEqual(result["status"], CACHE_CONSUMER_ADMISSIBLE_FOR_DESIGN)
        self.assertTrue(result["admissible"])
        self.assertFalse(result["fallback_required"])
        self.assertFalse(result["enabled"])
        self.assertFalse(result["serving_enabled"])
        self.assertEqual(result["mode"], "trace_only")
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["rehydration_status"], CACHE_REHYDRATION_READY)

    def test_guarded_consumer_falls_back_for_incomplete_rehydration_candidate(self) -> None:
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

        result = classify_report_cache_guarded_consumer_candidate(
            {
                "entry_version": REPORT_CACHE_ENTRY_VERSION,
                "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
                "key": key,
                "key_id": report_cache_key_id(key),
                "value": {"kind": "calculation_result", "rendered_value": "123"},
                "provenance": {"source_row_ids": ["row-1"]},
            },
            expected_key=key,
        )

        self.assertEqual(result["status"], CACHE_CONSUMER_FALLBACK_REQUIRED)
        self.assertFalse(result["admissible"])
        self.assertTrue(result["fallback_required"])
        self.assertIn("rehydration_not_ready", result["reasons"])
        self.assertIn("missing_answer_slots", result["reasons"])
        self.assertIn("missing_calculation_trace", result["reasons"])

    def test_guarded_consumer_falls_back_for_scope_mismatch_or_ambiguous_match(self) -> None:
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
        expected_key = dict(key)
        expected_key["source_table_id"] = "section::table:other"
        entry = {
            "entry_version": REPORT_CACHE_ENTRY_VERSION,
            "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
            "key": key,
            "key_id": report_cache_key_id(key),
            "value": {
                "kind": "calculation_result",
                "rendered_value": "123",
                "answer_slots": {"primary_value": {"display": "123"}},
                "calculation_trace": {
                    "calculation_result": {"status": "ok", "rendered_value": "123"},
                    "calculation_operands": [{"label": "metric", "raw_value": "123"}],
                },
                "citations": ["[ACME | 2023 | section]"],
                "evidence_items": [{"source_anchor": "section", "claim": "metric was 123"}],
            },
            "provenance": {"source_row_ids": ["row-1"], "evidence_refs": ["ev-1"]},
        }

        result = classify_report_cache_guarded_consumer_candidate(
            entry,
            expected_key=expected_key,
            selected_match_count=2,
        )

        self.assertEqual(result["status"], CACHE_CONSUMER_FALLBACK_REQUIRED)
        self.assertIn("ambiguous_rehydration_match", result["reasons"])
        self.assertIn("scope_mismatch:source_table_id", result["reasons"])

    def test_rehydrated_candidate_artifact_blocks_incomplete_entry_without_serving(self) -> None:
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

        result = build_report_cache_rehydrated_candidate_artifact(
            {
                "entry_version": REPORT_CACHE_ENTRY_VERSION,
                "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
                "key": key,
                "key_id": report_cache_key_id(key),
                "value": {"kind": "calculation_result", "rendered_value": "123"},
                "provenance": {"source_row_ids": ["row-1"]},
            }
        )

        self.assertEqual(result["status"], CACHE_REHYDRATION_BLOCKED)
        self.assertFalse(result["ready"])
        self.assertFalse(result["enabled"])
        self.assertFalse(result["serving_enabled"])
        self.assertIsNone(result["artifact"])
        self.assertEqual(result["consumer_admissibility"]["status"], CACHE_CONSUMER_FALLBACK_REQUIRED)
        self.assertFalse(result["consumer_admissibility"]["serving_enabled"])
        self.assertIn("missing_answer_slots", result["reasons"])

    def test_rehydrated_candidate_artifact_preserves_payload_without_serving(self) -> None:
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
            "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
            "key": key,
            "key_id": report_cache_key_id(key),
            "value": {
                "kind": "calculation_result",
                "rendered_value": "123",
                "answer_slots": {"primary_value": {"display": "123", "raw_value": "123"}},
                "calculation_trace": {
                    "calculation_result": {"status": "ok", "rendered_value": "123"},
                    "calculation_operands": [{"label": "metric", "raw_value": "123"}],
                },
                "citations": ["[ACME | 2023 | section]"],
                "evidence_items": [{"source_anchor": "section", "claim": "metric was 123"}],
            },
            "provenance": {
                "source_row_ids": ["row-1"],
                "evidence_refs": ["ev-1"],
                "source_anchor": "section",
            },
        }

        result = build_report_cache_rehydrated_candidate_artifact(
            entry,
            task_id="task_1",
            artifact_id="cache::candidate::1",
        )

        artifact = result["artifact"]
        payload = artifact["payload"]
        self.assertEqual(result["status"], CACHE_REHYDRATION_READY)
        self.assertTrue(result["ready"])
        self.assertFalse(result["enabled"])
        self.assertFalse(result["serving_enabled"])
        self.assertEqual(artifact["artifact_id"], "cache::candidate::1")
        self.assertEqual(artifact["task_id"], "task_1")
        self.assertEqual(artifact["status"], "candidate")
        self.assertEqual(artifact["metadata"]["source"], "report_cache_rehydration")
        self.assertEqual(artifact["metadata"]["cache_origin"], CACHE_ENTRY_SOURCE_LOCAL_INDEX)
        self.assertEqual(artifact["metadata"]["report_cache_key_id"], report_cache_key_id(key))
        self.assertEqual(artifact["metadata"]["rehydration_status"], CACHE_REHYDRATION_READY)
        self.assertEqual(
            artifact["metadata"]["consumer_admissibility_status"],
            CACHE_CONSUMER_ADMISSIBLE_FOR_DESIGN,
        )
        self.assertFalse(artifact["metadata"]["serving_enabled"])
        self.assertFalse(artifact["metadata"]["ledger_insertion_enabled"])
        self.assertEqual(payload["answer"], "123")
        self.assertEqual(payload["citations"], ["[ACME | 2023 | section]"])
        self.assertEqual(payload["evidence_items"], [{"source_anchor": "section", "claim": "metric was 123"}])
        self.assertEqual(payload["structured_result"]["answer_slots"]["primary_value"]["display"], "123")
        self.assertEqual(payload["resolved_calculation_trace"]["calculation_result"]["rendered_value"], "123")
        self.assertEqual(payload["cache_origin"], CACHE_ENTRY_SOURCE_LOCAL_INDEX)
        self.assertEqual(payload["report_cache_key_id"], report_cache_key_id(key))
        self.assertEqual(payload["report_cache_rehydration"]["status"], CACHE_REHYDRATION_READY)
        self.assertFalse(payload["report_cache_rehydration"]["serving_enabled"])
        self.assertEqual(payload["consumer_admissibility"]["status"], CACHE_CONSUMER_ADMISSIBLE_FOR_DESIGN)
        self.assertFalse(payload["consumer_admissibility"]["serving_enabled"])
        self.assertIn("ev-1", artifact["evidence_refs"])
        self.assertIn("row-1", artifact["evidence_refs"])

    def test_rehydrated_candidate_projects_calculation_contract_without_ledger_insertion(self) -> None:
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
            "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
            "key": key,
            "key_id": report_cache_key_id(key),
            "value": {
                "kind": "calculation_result",
                "rendered_value": "123",
                "answer_slots": {"primary_value": {"display": "123", "raw_value": "123"}},
                "calculation_trace": {
                    "calculation_plan": {"operation": "lookup"},
                    "calculation_result": {"status": "ok", "rendered_value": "123"},
                    "calculation_operands": [{"label": "metric", "raw_value": "123"}],
                },
                "citations": ["[ACME | 2023 | section]"],
                "evidence_items": [{"source_anchor": "section", "claim": "metric was 123"}],
            },
            "provenance": {
                "source_row_ids": ["row-1"],
                "evidence_refs": ["ev-1"],
                "source_anchor": "section",
            },
        }

        result = build_report_cache_calculation_contract_projection(entry, task_id="task_1")

        projection = result["projection"]
        task = projection["task"]
        artifacts = projection["artifacts"]
        self.assertEqual(result["status"], CACHE_REHYDRATION_READY)
        self.assertTrue(result["ready"])
        self.assertFalse(result["serving_enabled"])
        self.assertFalse(result["ledger_insertion_enabled"])
        self.assertEqual(task["status"], "candidate")
        self.assertEqual(task["kind"], "calculation")
        self.assertEqual(
            task["artifact_ids"],
            ["task_1::operand_set", "task_1::calculation_plan", "task_1"],
        )
        self.assertEqual(task["artifact_kinds"], ["operand_set", "calculation_plan", "calculation_result"])
        self.assertFalse(task["metadata"]["ledger_insertion_enabled"])
        self.assertEqual(artifacts["task_1::operand_set"]["kind"], "operand_set")
        self.assertEqual(
            artifacts["task_1::operand_set"]["payload"]["calculation_operands"],
            [{"label": "metric", "raw_value": "123"}],
        )
        self.assertEqual(artifacts["task_1::calculation_plan"]["kind"], "calculation_plan")
        self.assertEqual(
            artifacts["task_1::calculation_plan"]["payload"]["calculation_plan"]["operation"],
            "lookup",
        )
        self.assertEqual(artifacts["task_1"]["kind"], "calculation_result")
        self.assertEqual(artifacts["task_1"]["payload"]["calculation_result"]["rendered_value"], "123")
        self.assertEqual(
            artifacts["task_1"]["payload"]["consumer_admissibility"]["status"],
            CACHE_CONSUMER_ADMISSIBLE_FOR_DESIGN,
        )
        for artifact in artifacts.values():
            self.assertEqual(artifact["status"], "candidate")
            self.assertEqual(artifact["metadata"]["cache_origin"], CACHE_ENTRY_SOURCE_LOCAL_INDEX)
            self.assertEqual(artifact["metadata"]["report_cache_key_id"], report_cache_key_id(key))
            self.assertFalse(artifact["metadata"]["serving_enabled"])
            self.assertFalse(artifact["metadata"]["ledger_insertion_enabled"])
            self.assertIn("ev-1", artifact["evidence_refs"])
            self.assertIn("row-1", artifact["evidence_refs"])

    def test_rehydrated_candidate_projection_validator_accepts_contract_shape_without_serving(self) -> None:
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
            "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
            "key": key,
            "key_id": report_cache_key_id(key),
            "value": {
                "kind": "calculation_result",
                "rendered_value": "123",
                "answer_slots": {"primary_value": {"display": "123", "raw_value": "123"}},
                "calculation_trace": {
                    "calculation_plan": {"operation": "lookup"},
                    "calculation_result": {"status": "ok", "rendered_value": "123"},
                    "calculation_operands": [{"label": "metric", "raw_value": "123"}],
                },
                "citations": ["[ACME | 2023 | section]"],
                "evidence_items": [{"source_anchor": "section", "claim": "metric was 123"}],
            },
            "provenance": {
                "source_row_ids": ["row-1"],
                "evidence_refs": ["ev-1"],
                "source_anchor": "section",
            },
        }

        result = validate_report_cache_calculation_contract_projection(entry, task_id="task_1")

        self.assertEqual(result["status"], CACHE_PROJECTION_VALID_FOR_CONTRACT)
        self.assertTrue(result["valid_for_contract"])
        self.assertFalse(result["fallback_required"])
        self.assertFalse(result["serving_enabled"])
        self.assertFalse(result["ledger_insertion_enabled"])
        self.assertEqual(result["reasons"], [])
        self.assertEqual(
            result["required_artifact_kinds"],
            ["operand_set", "calculation_plan", "calculation_result"],
        )
        projection = result["projection"]
        self.assertEqual(projection["task"]["artifact_ids"], ["task_1::operand_set", "task_1::calculation_plan", "task_1"])
        self.assertEqual(
            projection["artifacts"]["task_1"]["payload"]["calculation_result"]["rendered_value"],
            "123",
        )

    def test_blocked_candidate_has_no_calculation_contract_projection(self) -> None:
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

        result = build_report_cache_calculation_contract_projection(
            {
                "entry_version": REPORT_CACHE_ENTRY_VERSION,
                "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
                "key": key,
                "key_id": report_cache_key_id(key),
                "value": {"kind": "calculation_result", "rendered_value": "123"},
                "provenance": {"source_row_ids": ["row-1"]},
            },
            task_id="task_1",
        )

        self.assertEqual(result["status"], CACHE_REHYDRATION_BLOCKED)
        self.assertFalse(result["ready"])
        self.assertIsNone(result["projection"])
        self.assertFalse(result["serving_enabled"])
        self.assertFalse(result["ledger_insertion_enabled"])
        self.assertEqual(result["consumer_admissibility"]["status"], CACHE_CONSUMER_FALLBACK_REQUIRED)
        self.assertIn("missing_answer_slots", result["reasons"])

    def test_blocked_candidate_projection_validator_requires_fallback(self) -> None:
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

        result = validate_report_cache_calculation_contract_projection(
            {
                "entry_version": REPORT_CACHE_ENTRY_VERSION,
                "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
                "key": key,
                "key_id": report_cache_key_id(key),
                "value": {"kind": "calculation_result", "rendered_value": "123"},
                "provenance": {"source_row_ids": ["row-1"]},
            },
            task_id="task_1",
        )

        self.assertEqual(result["status"], CACHE_CONSUMER_FALLBACK_REQUIRED)
        self.assertFalse(result["valid_for_contract"])
        self.assertTrue(result["fallback_required"])
        self.assertIsNone(result["projection"])
        self.assertFalse(result["serving_enabled"])
        self.assertFalse(result["ledger_insertion_enabled"])
        self.assertIn("projection_not_available", result["reasons"])
        self.assertIn("missing_answer_slots", result["reasons"])

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
        self.assertTrue(candidate["retrieval_bypass"]["eligible"])
        self.assertFalse(candidate["retrieval_bypass"]["enabled"])
        self.assertEqual(candidate["retrieval_bypass"]["mode"], "trace_only")

    def test_runtime_trace_cache_candidate_derives_section_from_table_id(self) -> None:
        update = _runtime_trace_state_update(
            {
                "report_scope": {
                    "company": "ACME",
                    "report_type": "annual",
                    "rcept_no": "r1",
                    "year": "2023",
                },
                "active_subtask": {
                    "metric_family": "metric",
                    "metric_label": "metric",
                },
            },
            calculation_operands=[
                {
                    "label": "metric",
                    "raw_value": "123",
                    "period": "2023",
                    "consolidation_scope": "consolidated",
                    "statement_type": "statement",
                    "table_source_id": "section path::table:1",
                    "source_row_id": "row-1",
                }
            ],
            calculation_plan={"operation": "lookup"},
            calculation_result={"status": "ok", "rendered_value": "123"},
        )

        candidate = update["resolved_calculation_trace"]["report_cache_candidate"]

        self.assertEqual(candidate["status"], CACHE_REUSABLE)
        self.assertEqual(candidate["key"]["source_section"], "section path")
        self.assertEqual(candidate["key"]["source_table_id"], "section path::table:1")

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
