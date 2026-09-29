from __future__ import annotations

import unittest

from src.agent.financial_numeric_surface import extract_numeric_surface_candidates
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_source_bundles import build_semantic_source_bundles


def catalog_for(text, **metadata):
    return build_semantic_candidate_catalog([{
        "candidate_id": "chunk-bare", "candidate_kind": "chunk",
        "source_anchor": "[sample]", "text": text,
        "source_text_exact": text, "metadata": {"is_table": False, **metadata},
    }])


class ProseNumericCandidateTests(unittest.TestCase):
    def test_small_operands_share_source_display_bundle_and_keep_existing_ids(self):
        text = "Current quantity 84, previous quantity 70; reported growth is 20.0%."
        catalog = catalog_for(text)
        numeric = [row for row in catalog if row["kind"] == "numeric"]
        self.assertEqual({row["normalized_value"] for row in numeric}, {84, 70, 20})
        display = next(row for row in numeric if row["raw_unit"] == "%")
        self.assertEqual(display["candidate_id"], "cand_ddf49e56ee027417419f")
        self.assertEqual(display["source_span"], [62, 67])
        narrative = next(row for row in catalog if row["kind"] == "narrative")
        self.assertEqual(narrative["candidate_id"], "cand_3aacc80e5ed9fa57edb7")
        bundles = build_semantic_source_bundles(numeric)
        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0].source_text, text)
        self.assertEqual(len(bundles[0].candidate_ids), 3)

    def test_bare_values_are_not_filtered_by_digit_count_or_sign(self):
        for spelling, expected in (("0", 0), ("7", 7), ("43", 43), ("987", 987),
                                   ("12,345", 12345), ("-6.25", -6.25),
                                   ("(18.50)", -18.5), ("+4.5", 4.5)):
            with self.subTest(spelling=spelling):
                rows = [r for r in catalog_for(f"Observed value {spelling}; unchanged scope.")
                        if r["kind"] == "numeric"]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["normalized_value"], expected)
                self.assertEqual(rows[0]["raw_value"], spelling)
                self.assertEqual(rows[0]["raw_unit"], "")
                self.assertEqual(rows[0]["normalized_unit"], "COUNT")

    def test_exact_whitespace_and_parentheses_survive_bundle_projection(self):
        text = "Observed (32.50)\t  and earlier 25.0; report 30%."
        numeric = [r for r in catalog_for(text) if r["kind"] == "numeric"]
        self.assertEqual(len(numeric), 3)
        bundle, = build_semantic_source_bundles(numeric)
        self.assertEqual(bundle.source_text, text)
        for row in numeric:
            start, end = bundle.value_span_by_candidate_id()[row["candidate_id"]]
            self.assertEqual(text[start:end], row["raw_value"] + row["raw_unit"])

    def test_bare_values_do_not_inherit_a_different_values_currency(self):
        rows = [r for r in catalog_for("Amount 5억원; observed quantity 37 and previous 29.")
                if r["kind"] == "numeric"]
        counts = [r for r in rows if r["normalized_unit"] == "COUNT"]
        self.assertEqual({r["normalized_value"] for r in counts}, {37, 29})
        self.assertTrue(all(r["raw_unit"] == "" for r in counts))

    def test_date_time_identifier_and_numeric_list_markers_are_not_new_operands(self):
        text = "2046-09-14 at 09:30; AB7 AB-18 2.3.4 [8]; 1. Label; observed 42."
        rows = [r for r in catalog_for(text) if r["kind"] == "numeric"]
        self.assertEqual([r["normalized_value"] for r in rows], [42])

    def test_repeated_values_keep_distinct_spans_and_input_order_is_irrelevant(self):
        sources = [{"candidate_id": name, "source_anchor": name, "candidate_kind": "chunk",
                    "text": "Current 17, previous 17.", "metadata": {"is_table": False}}
                   for name in ("first", "second")]
        catalog = build_semantic_candidate_catalog(sources)
        numeric = [r for r in catalog if r["kind"] == "numeric"]
        self.assertEqual(len(numeric), 4)
        self.assertEqual(len({r["candidate_id"] for r in numeric}), 4)
        reversed_catalog = build_semantic_candidate_catalog(list(reversed(sources)))
        self.assertEqual(sorted(catalog, key=lambda row: row["candidate_id"]),
                         sorted(reversed_catalog, key=lambda row: row["candidate_id"]))
        self.assertEqual(build_semantic_source_bundles(catalog),
                         build_semantic_source_bundles(reversed_catalog))
        self.assertEqual(semantic_candidate_catalog_fingerprint(catalog),
                         semantic_candidate_catalog_fingerprint(reversed_catalog))

    def test_shared_evaluation_extractor_behavior_is_unchanged(self):
        rows = extract_numeric_surface_candidates("Observed 84 and previous 70; stated 20%.")
        self.assertEqual([r["text"] for r in rows], ["20%"])

    def test_unsupported_inline_spelling_is_not_recast_as_bare_count(self):
        rows = [r for r in catalog_for("Amount 6 USD and $7; observed 38.")
                if r["kind"] == "numeric"]
        self.assertEqual([r["normalized_value"] for r in rows], [38])

    def test_bundle_expansion_retains_the_exact_numeric_capacity_boundary(self):
        from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
        from tests.semantic_program_test_support import _obligation
        obligation = _obligation("value", "direct_value", "value")
        for count, expected in ((96, "ok"), (97, "capacity_exceeded")):
            with self.subTest(count=count):
                catalog = catalog_for("Values " + ", ".join(["1"] * count) + ".")
                numeric = [r for r in catalog if r["kind"] == "numeric"]
                self.assertEqual(len(numeric), count)
                self.assertEqual(len(build_semantic_source_bundles(numeric)), 1)
                plan = _semantic_candidate_cohorts(catalog, [obligation])
                self.assertEqual(plan["status"], expected)

    def test_authored_formula_executes_bare_operands_with_separate_source_display(self):
        from src.agent.financial_calculation_execution import execute_semantic_calculation_program
        from src.agent.financial_graph_models import SemanticCalculationProgram
        from src.ops.replay_reviewed_compiler_selection import (
            _CompilerOnlyAgent, _RecordingLLM, _ReviewedProgramQueue, _case_state,
        )
        from tests.semantic_program_test_support import _binding, _obligation, _requirement, _source_assertions
        text = "Current quantity 84, previous quantity 70; reported growth is 19.8%."
        catalog = catalog_for(text)
        ids = {r["raw_value"]: r["candidate_id"] for r in catalog if r["kind"] == "numeric"}
        obligation = _obligation("growth", "derived_value", "growth", display_unit="%",
            evidence_requirements=[_requirement("current", "quantity"), _requirement("previous", "quantity")])
        # A deliberately authored selection tests execution, not LLM semantics.
        witness = {"status": "ready", "expressions": [{
            "obligation_id": "growth", "formula": "(A / B - 1) * 100", "display_unit": "%",
            "variable_bindings": [_binding("A", ids["84"], "current"), _binding("B", ids["70"], "previous")],
            "source_display_candidate_id": ids["19.8"],
            "source_display_reason": "The source states growth separately from the displayed quantities.",
        }], "source_assertions": _source_assertions(catalog, *ids.values())}
        row = {"case_id": "authored", "question": "Report growth and recalculate it from the quantities.",
               "obligations": [obligation]}
        compiled = _CompilerOnlyAgent(_RecordingLLM(_ReviewedProgramQueue([
            SemanticCalculationProgram.model_validate(witness)
        ])))._compile_semantic_calculation_program(_case_state(row, catalog))
        execution = execute_semantic_calculation_program(
            program=compiled["semantic_program"], obligations=[obligation], candidate_catalog=catalog,
            query=row["question"], compilation_envelope=compiled["semantic_compilation_envelope"],
            require_compilation_envelope=True,
        )
        self.assertEqual(execution["status"], "ok", execution)
        output = execution["outputs_by_obligation"]["growth"]
        self.assertAlmostEqual(output["normalized_value"], 20)
        self.assertEqual(output["rendered_value"], "19.8%")
        self.assertEqual(compiled["semantic_program_retry_count"], 0)


if __name__ == "__main__":
    unittest.main()
