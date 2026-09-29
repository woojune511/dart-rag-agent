"""Retrieval strength requires a numeric cell, not digits in a column label."""

from copy import deepcopy
from types import SimpleNamespace
import unittest

from src.agent.financial_retrieval_pipeline import (
    FinancialRetrievalPipelineMixin,
    _numeric_atomic_declared_surface_priority,
)


class _Pipeline(FinancialRetrievalPipelineMixin):
    pass


def _state():
    owner = {
        "obligation_id": "output", "kind": "direct_value", "required": True,
        "label": "target measure", "retrieval_hints": ["target measure"],
        "scope": {"company": "Cedar", "period": "2024", "consolidation_scope": "consolidated"},
        "evidence_requirements": [],
    }
    return {
        "query": "Report target measure.", "topic": "target measure",
        "intent": "numeric_fact", "companies": ["Cedar"], "years": [2024],
        "report_scope": {"rcept_no": "filing"},
        "answer_obligations": [owner], "semantic_plan": {"program_required": True},
        "active_subtask": {"preferred_statement_types": ["primary", "supporting"]},
    }


def _metadata(source_id, statement_type, header="", **overrides):
    return {
        "chunk_uid": source_id, "company": "Cedar", "year": 2024,
        "rcept_no": "filing", "section_path": statement_type,
        "statement_type": statement_type, "block_type": "table",
        "consolidation_scope": "consolidated", "table_header_context": header,
        **overrides,
    }


class NumericSupplementValueCellsTests(unittest.TestCase):
    def _select(self, docs, metadatas, state=None):
        pipeline = _Pipeline()
        pipeline.vsm = SimpleNamespace(bm25_docs=docs, bm25_metadatas=metadatas)
        state = state or _state()
        original = deepcopy((state, docs, metadatas))
        selected = pipeline._supplement_section_seed_docs(state)
        self.assertEqual((state, docs, metadatas), original)
        return selected

    def test_numbered_column_names_do_not_displace_requested_statement(self):
        selected = self._select(
            ["target measure | 120", "other measure | 7"],
            [_metadata("primary-row", "primary"),
             _metadata("numbered-columns", "supporting", "| target measure | category_1 | category_2")],
        )
        self.assertEqual([doc.metadata["chunk_uid"] for doc, _ in selected], ["primary-row"])

    def test_real_projected_header_value_retains_locality_priority(self):
        selected = self._select(
            ["target measure | 120", "other measure | 7"],
            [_metadata("primary-row", "primary"),
             _metadata("local-value", "supporting", "target measure | 125")],
        )
        self.assertEqual([doc.metadata["chunk_uid"] for doc, _ in selected], ["local-value"])

    def test_header_lines_cannot_borrow_another_lines_value(self):
        priority = _numeric_atomic_declared_surface_priority(
            {"table_header_context": "target measure | category_1\nother measure | 42"},
            "no numeric row", ["target measure"],
        )
        self.assertEqual(priority, (0, 0, 0, 0))

    def test_body_requires_a_complete_numeric_cell(self):
        for row in (
            "target measure | series_2", "target measure | type 25",
            "target measure (ref 6,7) | unavailable", "target measure | 2024-12-31",
            "target measure | NaN", "target measure | 1e999", "target measure | [12]",
        ):
            with self.subTest(row=row):
                self.assertEqual(_numeric_atomic_declared_surface_priority({}, row, ["target measure"]), (0, 0, 0, 0))

    def test_complete_finite_values_and_existing_inline_units_are_retained(self):
        for value in ("0", "-12", "+12", "(12)", "1,234.50", "-1.25%", "12 USD", "12 items"):
            for origin in ("header", "body"):
                with self.subTest(value=value, origin=origin):
                    row = f"target measure | {value}"
                    metadata = {"table_header_context": row} if origin == "header" else {}
                    body = "" if origin == "header" else row
                    self.assertEqual(_numeric_atomic_declared_surface_priority(metadata, body, ["target measure"])[0], 2 if origin == "header" else 1)

    def test_context_metadata_does_not_supply_the_value_signal(self):
        metadata = {"table_context": "target measure | 900", "table_value_labels_text": "target measure | 900"}
        body = "[table_value_labels: target measure | 900]\ntarget measure | unavailable"
        self.assertEqual(_numeric_atomic_declared_surface_priority(metadata, body, ["target measure"]), (0, 0, 0, 0))

    def test_correct_value_signal_does_not_override_source_scope(self):
        state = _state()
        state["answer_obligations"][0]["source_sections"] = ["primary"]
        selected = self._select(
            ["target measure | 120"] * 4,
            [_metadata("wrong-filing", "primary", "target measure | 125", rcept_no="other"),
             _metadata("wrong-section", "supporting", "target measure | 125"),
             _metadata("wrong-consolidation", "primary", "target measure | 125", consolidation_scope="separate"),
             _metadata("allowed", "primary")], state,
        )
        self.assertEqual([doc.metadata["chunk_uid"] for doc, _ in selected], ["allowed"])

    def test_corrected_supplement_survives_bounded_seed_window(self):
        pipeline = _Pipeline()
        pipeline.k = 1
        state = _state()
        supplemental = self._select(
            ["target measure | 120", "other measure | 7"],
            [_metadata("requested", "primary"), _metadata("noise", "supporting", "target measure | category_2")],
            state,
        )
        high = [(SimpleNamespace(page_content="unrelated | 8", metadata=_metadata(f"high-{i}", "primary")), 1.0) for i in range(5)]
        pipeline._rerank_docs = lambda docs, _state: docs
        plan = {"effective_k": 1, "reflection_count": 0, "active_subtask": {}, "semantic_program_required": True,
                "where_filter": {"rcept_no": "filing"}, "intent": "numeric_fact", "strict_company_scope": False,
                "companies": ["Cedar"], "years": [2024]}
        selected = pipeline._select_evidence(state, plan, {"docs": high + supplemental, "supplemental_docs": supplemental, "retry_queries": []})
        self.assertNotIn("requested", [doc.metadata["chunk_uid"] for doc, _ in selected["docs"]])
        self.assertIn("requested", [doc.metadata["chunk_uid"] for doc, _ in selected["seed_docs"]])


if __name__ == "__main__":
    unittest.main()
