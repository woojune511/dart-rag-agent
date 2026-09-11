from __future__ import annotations

import unittest
from copy import deepcopy

from src.agent.financial_calculation_execution import (
    validate_semantic_calculation_program,
)
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_candidate_matching import (
    _best_metric_state,
    project_candidate_fact,
    resolve_owner_target,
)
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

    def test_filing_company_row_cannot_mask_source_matched_metric_bundles(self) -> None:
        owner = _obligation()
        owner.update(label="Support credit", concept_hints=[], retrieval_hints=[])
        owner["display_unit"] = "USD"
        owner["semantic_target"] = {
            "local_subjects": [], "concept_keys": [], "metric_surfaces": ["support credit"],
        }
        catalog = []
        for candidate_id, entity, column, context in (
            ("balance-a", "filing company", "assets", ""),
            ("balance-b", "filing company", "liabilities", ""),
            ("credit-a", "adjustments", "disclosed amount", "Support credit for production."),
            ("credit-b", "adjustments", "disclosed amount", "Support credit recognized this period."),
        ):
            candidate = _candidate(candidate_id, entity=entity, row_id=candidate_id,
                cell_id=candidate_id, column=column, value="125", unit="USD",
                normalized_unit="USD", table_id=candidate_id)
            candidate.update(period="", source_text=context or entity, row_context_text=context)
            catalog.append(candidate)
        before = deepcopy(catalog)
        for rows in (catalog, list(reversed(catalog))):
            plan = _semantic_candidate_cohorts(rows, [owner])
            self.assertEqual(set(plan["candidate_ids_by_owner"]["ob_amount"]), {"credit-a", "credit-b"})
            for candidate_id in ("credit-a", "credit-b"):
                match = plan["candidate_match_by_id"][candidate_id]["ob_amount"]
                self.assertEqual(match["state"], "unknown_only")
                self.assertEqual(match["metric_state"], "surface_text")
        self.assertEqual(catalog, before)

    def test_filing_company_still_enforces_scope_without_ranking_bonus(self) -> None:
        candidate = {**self.target_amount, "company": "unrelated filing", "document_company": "unrelated filing"}
        plan = _semantic_candidate_cohorts([candidate], [_obligation()])
        self.assertNotIn(candidate["candidate_id"], plan["visible_candidate_ids"])
        self.assertEqual(plan["candidate_match_by_id"][candidate["candidate_id"]]["ob_amount"]["state"], "explicit_conflict")

    def test_metric_fragment_is_not_inferred_as_a_local_subject(self) -> None:
        owner = _obligation()
        owner.update(label="전체 연구개발비용", retrieval_hints=[], concept_hints=[], display_unit="KRW")
        owner["semantic_target"] = {
            "local_subjects": [], "concept_keys": ["research_and_development_expense"],
            "metric_surfaces": ["전체 연구개발비용"],
        }
        total = _candidate("total", entity="연구개발비용 계", row_id="total", cell_id="total:1",
            column="2024", value="120", unit="원", normalized_unit="KRW")
        unrelated = _candidate("balance", entity="개발비", row_id="balance", cell_id="balance:1",
            column="carrying amount", value="600", unit="원", normalized_unit="KRW", table_id="other")
        unrelated.update(period="", value_year=None)
        plan = _semantic_candidate_cohorts([unrelated, total], [owner])
        match = plan["candidate_match_by_id"]["total"]["ob_amount"]
        self.assertEqual(match["target_local_subjects"], [])
        self.assertEqual(match["state"], "compatible")
        self.assertEqual(plan["candidate_ids_by_owner"]["ob_amount"][0], "total")

    def test_explicit_metric_surface_fragment_is_not_a_subject_without_ontology(self) -> None:
        owner = _obligation()
        owner.update(label="combined service fee", retrieval_hints=[], concept_hints=[], display_unit="USD")
        owner["semantic_target"] = {
            "local_subjects": [], "concept_keys": [], "metric_surfaces": ["combined service fee"],
        }
        total = _candidate("total", entity="combined service fee", row_id="total", cell_id="total:1",
            column="2024", value="120", unit="USD", normalized_unit="USD")
        unrelated = _candidate("balance", entity="service fee", row_id="balance", cell_id="balance:1",
            column="amount", value="600", unit="USD", normalized_unit="USD", table_id="other")
        plan = _semantic_candidate_cohorts([unrelated, total], [owner])
        self.assertEqual(plan["candidate_match_by_id"]["total"]["ob_amount"]["target_local_subjects"], [])

    def test_exact_metric_axes_precede_substring_matches_without_trimming_bundles(self) -> None:
        owner = _obligation()
        owner.update(label="무형자산(개발비)으로 자본화된 금액", retrieval_hints=[], concept_hints=[], display_unit="KRW")
        owner["semantic_target"] = {
            "local_subjects": [], "concept_keys": ["capitalized_development_cost"],
            "metric_surfaces": ["무형자산(개발비)으로 자본화된 금액"],
        }
        catalog = []
        for candidate_id, label in (("a", "연구개발비용 계"), ("b", "정부보조금 차감후 연구개발비용 계"),
                                    ("z1", "개발비(무형자산)"), ("z2", "개발비(무형자산)")):
            catalog.append(_candidate(candidate_id, entity=label, row_id=candidate_id, cell_id=candidate_id + ":1",
                column="2024", value="120", unit="원", normalized_unit="KRW", table_id=candidate_id))
        before = deepcopy(catalog)
        for rows in (catalog, list(reversed(catalog))):
            plan = _semantic_candidate_cohorts(rows, [owner])
            self.assertEqual(set(plan["candidate_ids_by_owner"]["ob_amount"]), {"z1", "z2"})
        self.assertEqual(catalog, before)

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

    def test_footnoted_metric_rows_reach_the_owner_without_changing_source_identity(self) -> None:
        for label, metric, other_labels in (
            ("영업수익 (주35)", "영업수익", ("기타수익 (주26)", "이자수익")),
            ("매출액 (주28,36,37)", "매출액", ("매출원가 (주28,32,37)", "매출총이익")),
        ):
            with self.subTest(label=label):
                owner = _obligation()
                owner.update(label=metric, display_unit="KRW", retrieval_hints=[], concept_hints=[])
                owner["semantic_target"] = {
                    "local_subjects": [], "concept_keys": ["revenue"], "metric_surfaces": [metric],
                }
                sources = [{
                    "candidate_id": f"source-{index}",
                    "candidate_kind": "structured_value",
                    "source_anchor": "[sample]",
                    "text": f"{row_label} | 2024 | 125",
                    "metadata": {
                        "row_label": row_label, "row_headers": [row_label],
                        "company": "filing company", "year": 2024,
                        "table_source_id": "sample-table", "physical_table_id": "sample-table",
                        "physical_row_id": f"row-{index}",
                        "structured_cells": [{
                            "cell_id": f"row-{index}:1", "column_headers": ["2024"],
                            "value_text": "125", "unit_hint": "원",
                        }],
                    },
                } for index, row_label in enumerate((*other_labels, label))]
                catalog = build_semantic_candidate_catalog(sources)
                before = deepcopy(catalog)
                fingerprint = semantic_candidate_catalog_fingerprint(catalog)
                target = next(row for row in catalog if row["row_label"] == label)
                for rows in (catalog, list(reversed(catalog))):
                    plan = _semantic_candidate_cohorts(rows, [owner])
                    self.assertIn(target["candidate_id"], plan["candidate_ids_by_owner"]["ob_amount"])
                    state, rank = _best_metric_state(project_candidate_fact(target), resolve_owner_target(owner))
                    self.assertEqual((state, rank), ("concept_row", 1000))
                self.assertEqual(target["normalized_value"], 125)
                self.assertIn(label, target["source_text"])
                self.assertEqual(catalog, before)
                self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)

    def test_metric_annotation_normalization_keeps_semantic_qualifiers_and_empty_keys(self) -> None:
        owner = _obligation()
        owner["semantic_target"] = {
            "local_subjects": [], "concept_keys": [], "metric_surfaces": ["service fee (*1,5)"],
        }
        target = resolve_owner_target(owner)
        for label, expected_rank in (("service fee", 900), ("service fee (net)", 0), ("(*)", 0)):
            with self.subTest(label=label):
                fact = project_candidate_fact({"row_label": label})
                self.assertEqual(_best_metric_state(fact, target)[1], expected_rank)
        empty_target = resolve_owner_target({
            "semantic_target": {"local_subjects": [], "concept_keys": [], "metric_surfaces": ["(*)"]},
        })
        self.assertEqual(_best_metric_state(project_candidate_fact({"row_label": "(*)"}), empty_target)[1], 0)

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
        ranking = output["ranking_diagnostics"]
        self.assertEqual(ranking["population"], "eligible_catalog")
        self.assertEqual(ranking["eligible_candidate_count"], 2)
        self.assertEqual(ranking["top_tier_candidate_count"], 1)
        self.assertEqual(ranking["top_two_relation"], "separated")
        self.assertEqual(
            ranking["first_differing_factor"],
            "applicability_state",
        )
        self.assertEqual(ranking["unknown_only_share"], 0.5)

    def test_ranking_diagnostics_preserve_factor_ties(self) -> None:
        left = {**self.target_amount, "candidate_id": "left"}
        right = {**self.target_amount, "candidate_id": "right"}

        plan = _semantic_candidate_cohorts([right, left], [_obligation()])
        output = next(
            row
            for row in plan["cohorts"]
            if row["cohort_id"] == "ob_amount:output"
        )
        ranking = output["ranking_diagnostics"]

        self.assertEqual(ranking["top_two_relation"], "tie")
        self.assertEqual(ranking["top_tier_candidate_count"], 2)
        self.assertEqual(ranking["first_differing_factor"], "")
        self.assertEqual(ranking["first_differing_delta"], 0)

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

    def test_structured_prompt_references_one_physical_row_bundle(self) -> None:
        plan = _semantic_candidate_cohorts([self.target_amount], [_obligation()])
        payload = FinancialAgent._semantic_program_prompt_payload(
            [self.target_amount], plan
        )
        row = payload["candidates_by_id"]["amount-target"]
        self.assertNotIn("source_text", row)
        bundle = payload["source_bundles_by_id"][row["source_bundle_id"]]
        from tests.compiler_presentation_test_support import bundle_text
        self.assertIn("700,691", bundle_text(payload, bundle["source_bundle_id"]))
        self.assertIn("investment carrying amount", bundle_text(payload, bundle["source_bundle_id"]))
        self.assertNotIn("ranking_diagnostics", payload["cohorts"][0])
        self.assertIn("26%", bundle_text(payload, bundle["source_bundle_id"]))
        self.assertEqual(payload["schema"], "semantic_program_candidate_payload_v7")

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
