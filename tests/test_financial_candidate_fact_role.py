from __future__ import annotations

import unittest

from src.agent.financial_candidate_fact_role import (
    CandidateFactRoleV1,
    CandidateSemanticRoleV1,
)


class CandidateFactRoleTests(unittest.TestCase):
    def test_structured_roles_preserve_row_statement_and_polarity(self) -> None:
        expense = CandidateFactRoleV1.create(
            {
                "candidate_id": "expense",
                "candidate_kind": "structured_value",
                "row_label": "loss allowance expense",
                "row_headers": ["loss allowance expense"],
                "column_headers": ["current period"],
                "raw_value": "(3,146)",
                "normalized_value": -3146.0,
                "statement_type": "income_statement",
                "value_role": "reported_value",
                "period": "2023",
                "physical_table_id": "statement-table",
                "physical_row_id": "expense-row",
                "physical_cell_id": "expense-cell",
            }
        )
        adjustment = CandidateFactRoleV1.create(
            {
                "candidate_id": "adjustment",
                "candidate_kind": "structured_value",
                "row_label": "loss allowance adjustment",
                "row_headers": ["loss allowance adjustment"],
                "column_headers": ["current period"],
                "raw_value": "3,146",
                "normalized_value": 3146.0,
                "statement_type": "cash_flow_statement",
                "value_role": "noncash_adjustment",
                "period": "2023",
                "physical_table_id": "cash-flow-table",
                "physical_row_id": "adjustment-row",
                "physical_cell_id": "adjustment-cell",
            }
        )

        self.assertEqual(expense.source_kind, "structured_table")
        self.assertEqual(expense.polarity, "negative")
        self.assertEqual(expense.statement_type, "income_statement")
        self.assertIn("loss allowance expense", expense.relation_surfaces)
        self.assertEqual(expense.grounding_state, "structured_grounded")
        self.assertEqual(adjustment.polarity, "positive")
        self.assertEqual(adjustment.value_role, "noncash_adjustment")
        self.assertNotEqual(
            expense.semantic_fingerprint,
            adjustment.semantic_fingerprint,
        )

    def test_grounded_prose_role_distinguishes_component_from_total(self) -> None:
        source_text = (
            "A 676 credit benefit was recognized, raising operating profit "
            "to 2,163."
        )
        component = {
            "candidate_id": "credit-benefit",
            "candidate_kind": "sentence_value",
            "raw_value": "676",
            "normalized_value": 676.0,
            "source_span": [2, 5],
            "local_entity_surfaces": ["raising operating profit"],
        }
        total_start = source_text.index("2,163")
        total = {
            "candidate_id": "operating-profit",
            "candidate_kind": "sentence_value",
            "raw_value": "2,163",
            "normalized_value": 2163.0,
            "source_span": [total_start, total_start + len("2,163")],
        }
        component_role = CandidateSemanticRoleV1.create(
            candidate_id="credit-benefit",
            source_text=source_text,
            subject_surfaces=["credit benefit"],
            relation_surfaces=["676 credit benefit was recognized"],
            value_role="component",
        )
        total_role = CandidateSemanticRoleV1.create(
            candidate_id="operating-profit",
            source_text=source_text,
            subject_surfaces=["operating profit"],
            relation_surfaces=["operating profit to 2,163"],
            value_role="reported_total",
        )

        component_projection = CandidateFactRoleV1.create(
            component,
            source_text=source_text,
            semantic_role=component_role,
        )
        total_projection = CandidateFactRoleV1.create(
            total,
            source_text=source_text,
            semantic_role=total_role,
        )

        self.assertEqual(
            component_projection.value_role,
            "component",
        )
        self.assertEqual(total_projection.value_role, "reported_total")
        self.assertEqual(
            component_projection.grounding_state,
            "semantic_grounded",
        )
        self.assertEqual(component_projection.source_span, (2, 5))
        self.assertEqual(
            component_projection.subject_surfaces,
            ("credit benefit",),
        )
        self.assertNotEqual(
            component_projection.semantic_fingerprint,
            total_projection.semantic_fingerprint,
        )
        self.assertIn(
            "Candidate relations: 676 credit benefit was recognized",
            component_projection.render_context(),
        )

    def test_semantic_role_rejects_an_ungrounded_surface(self) -> None:
        with self.assertRaisesRegex(ValueError, "ungrounded surfaces"):
            CandidateSemanticRoleV1.create(
                candidate_id="candidate-a",
                source_text="The reported total was 100.",
                relation_surfaces=["unreported adjustment"],
                value_role="component",
            )

    def test_semantic_role_rejects_task_relative_operand_use(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be source-local"):
            CandidateSemanticRoleV1.create(
                candidate_id="candidate-a",
                source_text="A 20 credit raised total profit to 100.",
                subject_surfaces=["credit"],
                relation_surfaces=["20 credit"],
                value_role="adjustment_component",
            )

    def test_semantic_role_cannot_be_attached_to_another_candidate(self) -> None:
        semantic_role = CandidateSemanticRoleV1.create(
            candidate_id="candidate-a",
            source_text="The reported total was 100.",
            relation_surfaces=["reported total"],
            value_role="reported_total",
        )

        with self.assertRaisesRegex(ValueError, "id mismatch"):
            CandidateFactRoleV1.create(
                {
                    "candidate_id": "candidate-b",
                    "candidate_kind": "sentence_value",
                    "raw_value": "100",
                },
                source_text="The reported total was 100.",
                semantic_role=semantic_role,
            )


if __name__ == "__main__":
    unittest.main()
