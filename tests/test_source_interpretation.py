from copy import deepcopy
import unittest

from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_source_interpretation import interpretation_axis_sources, validate_source_interpretation
from tests.test_numeric_subject_authority import numeric, owner, direct


def interpreted(candidate, *, subject="Maple division", metric="quantity"):
    return {"request_unit_ids": ["request_001"], "subject": subject, "metric": metric,
            "axis_refs": list(interpretation_axis_sources(candidate)), "context_evidence": []}


class SourceInterpretationTests(unittest.TestCase):
    def test_attached_heading_and_foreign_heading_have_different_authority(self):
        candidate = numeric(subject="Maple")
        candidate.update(source_document_sha256="doc", source_table_locator="/section[1]/table[1]",
            source_contexts=[{"context_id": "heading", "document_sha256": "doc",
                "relation": "ancestor_heading", "parent_locator": "/section[1]",
                "source_locator": "/section[1]/title[1]", "source_text": "Maple division", "source_span": [1, 15]}])
        proof = interpreted(candidate)
        proof.update(axis_refs=[], context_evidence=[{"context_id": "heading", "evidence_text": "Maple division"}])
        validate_source_interpretation(candidate, proof, owner=owner(), query="Maple")
        for field, value in (("document_sha256", "foreign"), ("parent_locator", "/section[2]"),
                             ("relation", "table_text_row")):
            changed = deepcopy(candidate)
            changed["source_contexts"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "not_attached"):
                validate_source_interpretation(changed, proof, owner=owner(), query="Maple")
        proof["context_evidence"][0]["evidence_text"] = "Maple Division"
        with self.assertRaisesRegex(ValueError, "quote_not_exact"):
            validate_source_interpretation(candidate, proof, owner=owner(), query="Maple")

    def test_source_interpretation_cannot_override_period_or_consolidation(self):
        for field, actual, requested in (("period", "2023", "2024"),
                                         ("consolidation_scope", "separate", "consolidated")):
            candidate, obligation = numeric(subject="Maple"), owner("Maple division")
            candidate[field] = actual
            obligation["scope"][field] = requested
            program = direct(candidate["candidate_id"])
            program["direct_bindings"][0]["source_interpretation"] = interpreted(candidate)
            result = validate_semantic_calculation_program(program=program, obligations=[obligation],
                candidate_catalog=[candidate], query="Return the Maple division quantity.")
            self.assertNotEqual(result["status"], "ready", field)

    def test_wrapper_maps_to_full_own_axes_without_changing_request_or_source(self):
        candidate, obligation = numeric(subject="Maple"), owner("Maple division")
        program = direct(candidate["candidate_id"])
        program["direct_bindings"][0]["source_interpretation"] = interpreted(candidate)
        before = deepcopy((candidate, obligation, program))
        result = validate_semantic_calculation_program(program=program, obligations=[obligation],
            candidate_catalog=[candidate], query="Return the Maple division quantity.")
        self.assertEqual(result["status"], "ready", result["errors"])
        resolution = result["valid_direct_bindings"][0]["source_interpretation_resolution"]
        self.assertEqual(resolution["validation_scope"], "source_linkage_not_semantic_equivalence")
        self.assertEqual((candidate, obligation, program), before)

    def test_other_cell_or_foreign_filing_axes_cannot_be_borrowed(self):
        candidate, foreign = numeric("local", "Maple"), numeric("foreign", "Maple")
        for key in ("physical_row_id", "physical_cell_id", "source_document_id"):
            changed = deepcopy(candidate)
            changed[key] = "other"
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "evidence_mismatch"):
                validate_source_interpretation(changed, interpreted(candidate), owner=owner("Maple"), query="Maple")
        with self.assertRaisesRegex(ValueError, "evidence_mismatch"):
            validate_source_interpretation(candidate, interpreted(foreign), owner=owner("Maple"), query="Maple")

    def test_invented_request_and_partial_axis_reference_fail(self):
        candidate = numeric(subject="Maple")
        interpretation = interpreted(candidate)
        interpretation["request_unit_ids"] = ["request_002"]
        with self.assertRaisesRegex(ValueError, "request_mismatch"):
            validate_source_interpretation(candidate, interpretation, owner=owner(), query="Maple")
        altered = deepcopy(candidate)
        altered["column_headers"] = altered["column_headers"][-1:]
        with self.assertRaisesRegex(ValueError, "evidence_mismatch"):
            validate_source_interpretation(candidate, interpreted(altered), owner=owner(), query="Maple")

    def test_wrong_semantic_interpretation_is_not_claimed_to_be_code_detectable(self):
        candidate = numeric(subject="Maple Bank")
        result = validate_source_interpretation(candidate, interpreted(candidate, subject="Maple division"),
            owner=owner("Maple division"), query="Maple division")
        self.assertEqual(result["validation_scope"], "source_linkage_not_semantic_equivalence")


if __name__ == "__main__":
    unittest.main()
