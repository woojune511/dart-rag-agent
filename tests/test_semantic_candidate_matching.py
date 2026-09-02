from __future__ import annotations

import unittest

from src.agent.financial_calculation_execution import (
    validate_semantic_calculation_program,
)
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from src.config import get_financial_ontology


def _candidate(
    candidate_id: str,
    *,
    entity: str,
    row_id: str,
    cell_id: str,
    column: str,
    value: str,
    unit: str,
    normalized_unit: str,
    table_id: str = "investments",
) -> dict:
    return {
        "candidate_id": candidate_id,
        "kind": "numeric",
        "candidate_kind": "structured_value",
        "source_candidate_id": f"source-{candidate_id}",
        "evidence_id": f"evidence-{candidate_id}",
        "source_anchor": "[sample]",
        "source_row_id": row_id,
        "table_source_id": table_id,
        "physical_table_id": table_id,
        "physical_row_id": row_id,
        "physical_cell_id": cell_id,
        "row_label": entity,
        "row_headers": ["region", entity],
        "local_entity_surfaces": [entity],
        "column_headers": [column],
        "raw_value": value,
        "raw_unit": unit,
        "normalized_value": float(value.replace(",", "")),
        "normalized_unit": normalized_unit,
        "company": "filing company",
        "document_company": "filing company",
        "consolidation_scope": "unknown",
        "segment": "",
        "basis": "",
        "period": "2024",
        "context_fingerprint": table_id,
        "source_text": (
            f"{entity} | ownership share 26% | investment carrying amount "
            f"700,691 million"
        ),
    }


def _obligation() -> dict:
    return {
        "obligation_id": "ob_amount",
        "kind": "direct_value",
        "label": "Motional investment carrying amount",
        "required": True,
        "display_unit": "million",
        "display_format": "",
        "scope": {
            "company": "filing company",
            "period": "2024",
            "consolidation_scope": "unknown",
            "segment": "",
            "basis": "",
        },
        "retrieval_hints": ["Motional carrying amount"],
        "concept_hints": [],
        "semantic_target": {
            "local_subjects": ["Motional"],
            "concept_keys": ["investment_carrying_amount"],
            "metric_surfaces": ["investment carrying amount"],
        },
        "evidence_requirements": [],
        "depends_on": [],
        "coupling_key": "",
    }


class SemanticCandidateMatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.target_amount = _candidate(
            "amount-target",
            entity="Motional",
            row_id="row-motional",
            cell_id="cell-motional-amount",
            column="investment carrying amount",
            value="700691",
            unit="million",
            normalized_unit="KRW",
        )
        self.same_row_share = _candidate(
            "share-target",
            entity="Motional",
            row_id="row-motional",
            cell_id="cell-motional-share",
            column="ownership share",
            value="26",
            unit="%",
            normalized_unit="PERCENT",
        )
        self.other_entity_amount = _candidate(
            "amount-other",
            entity="BHAF",
            row_id="row-bhaf",
            cell_id="cell-bhaf-amount",
            column="investment carrying amount",
            value="53",
            unit="million",
            normalized_unit="KRW",
        )

    def test_factorized_cohort_selects_subject_concept_and_unit(self) -> None:
        catalog = [
            self.same_row_share,
            self.other_entity_amount,
            self.target_amount,
        ]
        plan = _semantic_candidate_cohorts(catalog, [_obligation()])
        output = next(
            row for row in plan["cohorts"] if row["cohort_id"] == "ob_amount:output"
        )

        self.assertEqual(output["candidate_ids"], ["amount-target"])
        self.assertEqual(
            output["match_counts"],
            {"compatible": 1, "unknown_only": 0, "explicit_conflict": 2},
        )
        amount_match = plan["candidate_match_by_id"]["amount-target"]["ob_amount"]
        self.assertEqual(amount_match["subject_state"], "match")
        self.assertEqual(amount_match["metric_state"], "concept_cell")
        self.assertEqual(amount_match["unit_state"], "match")

    def test_catalog_order_does_not_change_cohort_or_payload(self) -> None:
        catalog = [
            self.same_row_share,
            self.other_entity_amount,
            self.target_amount,
        ]
        forward = _semantic_candidate_cohorts(catalog, [_obligation()])
        reverse = _semantic_candidate_cohorts(list(reversed(catalog)), [_obligation()])
        self.assertEqual(forward["visible_candidate_ids"], reverse["visible_candidate_ids"])
        self.assertEqual(
            FinancialAgent._semantic_program_prompt_payload(catalog, forward),
            FinancialAgent._semantic_program_prompt_payload(
                list(reversed(catalog)), reverse
            ),
        )

    def test_compatible_candidate_precedes_stronger_unknown_metric_match(self) -> None:
        compatible = {
            **self.target_amount,
            "candidate_id": "compatible",
            "column_headers": ["other metric"],
            "semantic_label": "investment carrying amount",
            "physical_cell_id": "cell-compatible",
        }
        unknown = {
            **self.target_amount,
            "candidate_id": "unknown",
            "period": "",
            "year": None,
            "value_year": None,
            "physical_cell_id": "cell-unknown",
        }

        plan = _semantic_candidate_cohorts([unknown, compatible], [_obligation()])
        output = next(
            row for row in plan["cohorts"] if row["cohort_id"] == "ob_amount:output"
        )

        self.assertEqual(output["candidate_ids"][:2], ["compatible", "unknown"])
        matches = plan["candidate_match_by_id"]
        self.assertEqual(matches["compatible"]["ob_amount"]["state"], "compatible")
        self.assertEqual(matches["unknown"]["ob_amount"]["state"], "unknown_only")

    def test_repeated_text_terms_do_not_outscore_an_exact_cell_match(self) -> None:
        repeated_text = {
            **self.target_amount,
            "candidate_id": "a-repeated-text",
            "candidate_kind": "sentence_value",
            "physical_table_id": "",
            "physical_row_id": "",
            "physical_cell_id": "",
            "column_headers": [],
            "source_text": " ".join(
                ["Motional investment carrying amount"] * 20
            ),
        }
        exact_cell = {
            **self.target_amount,
            "candidate_id": "z-exact-cell",
        }

        plan = _semantic_candidate_cohorts(
            [repeated_text, exact_cell],
            [_obligation()],
        )
        output = next(
            row for row in plan["cohorts"] if row["cohort_id"] == "ob_amount:output"
        )

        self.assertEqual(output["candidate_ids"][:2], ["z-exact-cell", "a-repeated-text"])

    def test_legacy_owner_grounds_local_subject_from_catalog_identity(self) -> None:
        legacy_owner = _obligation()
        legacy_owner["semantic_target"] = {
            "local_subjects": [],
            "concept_keys": [],
            "metric_surfaces": [],
        }
        plan = _semantic_candidate_cohorts(
            [self.other_entity_amount, self.target_amount],
            [legacy_owner],
        )
        output = next(
            row for row in plan["cohorts"] if row["cohort_id"] == "ob_amount:output"
        )
        self.assertEqual(output["candidate_ids"], ["amount-target"])
        match = plan["candidate_match_by_id"]["amount-target"]["ob_amount"]
        self.assertEqual(match["target_local_subjects"], ["Motional"])
        self.assertEqual(
            match["target_concept_keys"], ["investment_carrying_amount"]
        )

    def test_structured_prompt_uses_cell_local_text(self) -> None:
        plan = _semantic_candidate_cohorts([self.target_amount], [_obligation()])
        payload = FinancialAgent._semantic_program_prompt_payload(
            [self.target_amount], plan
        )
        row = payload["candidates_by_id"]["amount-target"]
        self.assertIn("700691", row["source_text"])
        self.assertIn("investment carrying amount", row["source_text"])
        self.assertNotIn("26%", row["source_text"])
        self.assertEqual(payload["schema"], "semantic_program_candidate_payload_v2")

    def test_validator_rejects_visible_but_conflicting_row(self) -> None:
        obligation = _obligation()
        result = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_amount",
                        "candidate_id": "amount-other",
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=[self.target_amount, self.other_entity_amount],
            query="Motional investment carrying amount",
            selectable_candidate_ids_by_owner={
                "ob_amount": ["amount-target", "amount-other"]
            },
        )
        self.assertEqual(result["status"], "invalid")
        self.assertIn(
            "candidate_semantic_target_mismatch",
            {error["code"] for error in result["errors"]},
        )

    def test_ontology_declares_the_two_independent_table_metrics(self) -> None:
        ontology = get_financial_ontology()
        specs = {
            item["concept"]: item for item in ontology.all_concept_specs()
        }
        self.assertEqual(specs["ownership_interest"]["unit_family"], "PERCENT")
        self.assertEqual(
            specs["investment_carrying_amount"]["unit_family"], "KRW"
        )


if __name__ == "__main__":
    unittest.main()
