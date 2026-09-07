from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts, _semantic_candidate_visibility
from src.agent.financial_reconciliation_candidates import build_semantic_candidate_catalog, build_semantic_source_candidates
from src.agent.financial_calculation_execution import validate_semantic_calculation_program, execute_semantic_calculation_program
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.processing.financial_parser import FinancialParser


def catalog_from_source(headers, *, hint="백만원", context="(단위: 백만원, %)", raw="37.5", relation="preceding_block"):
    source = {"candidate_id": "fixture-row", "candidate_kind": "structured_row", "source_anchor": "fixture",
        "text": "product", "metadata": {"row_label": "product", "row_id": "row-1",
            "table_source_id": "table-1", "physical_table_id": "table-1", "year": 2024,
            "structured_cells": [{"value_text": raw, "unit_hint": hint, "column_headers": headers}],
            "source_contexts": [{"context_id": "unit-context", "relation": relation, "source_text": context,
                "source_locator": "/DOCUMENT/TABLE[1]", "document_sha256": "a" * 64,
                "source_span": [0, len(context)]}]}}
    return source, next(c for c in build_semantic_candidate_catalog([source]) if c["kind"] == "numeric")


class SemanticColumnUnitTests(unittest.TestCase):
    def test_actual_parser_to_catalog_distinguishes_amount_and_share(self):
        fixture = Path(__file__).parent / "fixtures/mixed_column_units.xml"
        chunks = FinancialParser().process_document(str(fixture), {"company": "sample", "year": 2024, "rcept_no": "mixed-units"})
        docs = [(SimpleNamespace(page_content=c.content, metadata=c.metadata), 1.0) for c in chunks]
        sources = build_semantic_source_candidates({"retrieved_docs": docs}, source_anchor_builder=lambda m: "sample")
        before = deepcopy(sources)
        catalog = build_semantic_candidate_catalog(sources)
        amounts = [c for c in catalog if c.get("row_label") == "제품군 A" and c.get("raw_value") in ("750", "600")]
        shares = [c for c in catalog if c.get("row_label") == "제품군 A" and c.get("raw_value") in ("37.5", "30.0")]
        self.assertEqual(len(amounts), 2)
        self.assertEqual(len(shares), 2)
        for c in amounts:
            self.assertEqual(c["raw_unit"], "백만원")
            self.assertEqual(c["normalized_unit"], "KRW")
            self.assertEqual(c["normalized_value"], float(c["raw_value"]) * 1_000_000)
        for c in shares:
            self.assertEqual((c["raw_unit"], c["normalized_unit"]), ("%", "PERCENT"))
            self.assertEqual(c["normalized_value"], float(c["raw_value"]))
            self.assertEqual(c["source_unit_hint"], "백만원")
            self.assertTrue(c["source_unit_provenance"]["context_ids"])
            self.assertNotIn("37.5 / 백만원", c["source_bundle_text"])
        self.assertEqual(sources, before)
        self.assertEqual(catalog, build_semantic_candidate_catalog(list(reversed(sources))))

    def test_column_resolution_preserves_candidate_identity_and_raw_hint(self):
        source, corrected = catalog_from_source(["2024", "Share"])
        source["metadata"].pop("source_contexts")
        previous = next(c for c in build_semantic_candidate_catalog([source]) if c["kind"] == "numeric")
        self.assertEqual(previous["candidate_id"], corrected["candidate_id"])
        self.assertEqual(previous["source_unit_hint"], corrected["source_unit_hint"])
        self.assertEqual(corrected["normalized_unit"], "PERCENT")
        self.assertEqual(previous["normalized_unit"], "KRW")

    def test_exact_inline_unit_and_nearest_column_unit_take_precedence(self):
        for headers, raw, expected in ((["Share"], "37.5USD", "USD"),
                                        (["Amount (USD)"], "37.5", "USD"),
                                        (["USD", "Share"], "37.5", "%"),
                                        (["2024", "%"], "37.5", "%")):
            with self.subTest(headers=headers, raw=raw):
                _, candidate = catalog_from_source(headers, raw=raw, context="(Units: USD, %)")
                self.assertEqual(candidate["raw_unit"], expected)

    def test_ambiguous_mixed_units_never_fall_back_to_first_currency(self):
        for headers, context in ((["2024", "Value"], "(Units: USD, KRW)"),
                                  (["2024", "Other"], "(Units: USD, %)"),
                                  (["2024", "Value"], "(Units: unsupported, %)")):
            with self.subTest(headers=headers, context=context):
                _, candidate = catalog_from_source(headers, context=context)
                self.assertEqual(candidate["raw_unit"], "")
                self.assertEqual(candidate["normalized_unit"], "UNKNOWN")

    def test_unrelated_context_and_single_unit_table_do_not_reassign_units(self):
        for relation, context in (("following_block", "(Units: USD, %)"),
                                   ("ancestor_heading", "(Units: USD, %)"),
                                   ("preceding_block", "(단위: 백만원)")):
            _, candidate = catalog_from_source(["Share"], relation=relation, context=context)
            self.assertEqual(candidate["raw_unit"], "백만원")

    def test_explicit_row_unit_is_not_lost_in_mixed_unit_tables(self):
        source, _ = catalog_from_source(["2024"], context="(Units: USD, %)")
        source["metadata"]["row_headers"] = ["category", "Change (%)"]
        candidate = next(c for c in build_semantic_candidate_catalog([source]) if c["kind"] == "numeric")
        self.assertEqual((candidate["raw_unit"], candidate["normalized_unit"]), ("%", "PERCENT"))
        self.assertEqual(candidate["source_unit_provenance"]["row_header"], "Change (%)")
        source["metadata"]["structured_cells"][0]["column_headers"] = ["Amount (USD)"]
        conflict = next(c for c in build_semantic_candidate_catalog([source]) if c["kind"] == "numeric")
        self.assertEqual(conflict["normalized_unit"], "UNKNOWN")

    def test_currency_category_is_not_an_explicit_row_unit(self):
        source, _ = catalog_from_source(["2024", "Assets"], context="(단위: 백만원)", raw="750")
        source["metadata"]["row_headers"] = ["USD"]
        candidate = next(c for c in build_semantic_candidate_catalog([source]) if c["kind"] == "numeric")
        self.assertEqual((candidate["raw_unit"], candidate["normalized_value"]), ("백만원", 750_000_000))

    def test_generic_count_header_does_not_erase_declared_scale(self):
        for context in ("(Units: 만 대, %)", "(Units: 만 대)"):
            _, candidate = catalog_from_source(["2024", "Count"], hint="만 대", context=context, raw="9")
            self.assertEqual((candidate["normalized_value"], candidate["normalized_unit"]), (90_000, "COUNT"))

    def test_declaration_order_is_stable_and_multiple_scales_remain_ambiguous(self):
        source, _ = catalog_from_source(["Amount"], context="(Units: 백만 원, %)")
        context = deepcopy(source["metadata"]["source_contexts"][0])
        context.update(context_id="second-unit-context", source_text="(Units: 백만원, %)")
        source["metadata"]["source_contexts"].append(context)
        first = build_semantic_candidate_catalog([source])
        source["metadata"]["source_contexts"].reverse()
        numeric = next(c for c in first if c["kind"] == "numeric")
        reversed_numeric = next(c for c in build_semantic_candidate_catalog([source]) if c["kind"] == "numeric")
        # Raw context order is retained as source provenance, not a unit decision.
        for key in ("raw_unit", "normalized_value", "normalized_unit", "source_unit_provenance", "source_bundle_text"):
            self.assertEqual(numeric[key], reversed_numeric[key])
        self.assertEqual((numeric["normalized_value"], numeric["normalized_unit"]), (37_500_000, "KRW"))
        _, ambiguous = catalog_from_source(["Amount"], context="(Units: 백만원, 천원, %)")
        self.assertEqual(ambiguous["normalized_unit"], "UNKNOWN")
        _, count = catalog_from_source(["Quantity"], context="(Units: 만 대, %)")
        self.assertEqual((count["normalized_value"], count["normalized_unit"]), (375_000, "COUNT"))

    def test_percent_candidate_is_excluded_from_amount_owner_and_executes_as_percent(self):
        _, candidate = catalog_from_source(["2024", "Share"])
        owner = {"obligation_id": "share", "kind": "direct_value", "label": "share", "required": True,
            "display_unit": "%", "scope": {"period": "2024"},
            "semantic_target": {"local_subjects": [], "concept_keys": [], "metric_surfaces": ["Share"]}}
        cohorts = _semantic_candidate_cohorts([candidate], [owner])
        visibility = _semantic_candidate_visibility([candidate], visible_candidate_ids=cohorts["visible_candidate_ids"],
            candidate_ids_by_owner=cohorts["candidate_ids_by_owner"])
        inputs = dict(program={"direct_bindings": [{"obligation_id": "share", "candidate_id": candidate["candidate_id"]}]},
            obligations=[owner], candidate_catalog=[candidate], query="2024 share")
        validation = validate_semantic_calculation_program(**inputs, candidate_visibility=visibility)
        envelope = CompilationEnvelopeV2.create(**inputs, visibility=visibility, validation=validation)
        result = execute_semantic_calculation_program(**inputs, compilation_envelope=envelope, require_compilation_envelope=True)
        self.assertEqual(result["status"], "ok", validation["errors"])
        operand = result["calculation_operands"][0]
        self.assertEqual(operand["raw_unit"], "%")
        self.assertEqual(operand["source_unit_provenance"], candidate["source_unit_provenance"])
        payload = FinancialAgent._semantic_program_prompt_payload([candidate], cohorts)
        self.assertEqual(payload["candidates_by_id"][candidate["candidate_id"]]["source_unit_provenance"], candidate["source_unit_provenance"])
        owner["display_unit"] = "USD"
        monetary = _semantic_candidate_cohorts([candidate], [owner])
        self.assertNotIn(candidate["candidate_id"], monetary["visible_candidate_ids"])


if __name__ == "__main__":
    unittest.main()
