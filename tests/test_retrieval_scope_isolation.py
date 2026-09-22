"""Synthetic source-boundary regressions, independent of benchmark answers."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.agent.financial_retrieval_pipeline import (
    FinancialRetrievalPipelineMixin,
    _semantic_query_ownership,
)


class _Pipeline(FinancialRetrievalPipelineMixin):
    k = 6

    def _rerank_docs(self, docs, state):
        return docs

def _doc(source_id, **metadata):
    return SimpleNamespace(
        page_content="measurement observations",
        metadata={"chunk_uid": source_id, "block_type": "table", **metadata},
    )


def _state(**overrides):
    return {
        "query": "measurement", "topic": "measurement", "intent": "numeric_fact",
        "query_type": "numeric_fact", "format_preference": "table",
        "companies": ["Example Parent"], "years": [2031],
        "report_scope": {"rcept_no": "filing-A", "report_type": "annual"},
        "answer_obligations": [{"obligation_id": "measure", "kind": "direct"}],
        **overrides,
    }


class RetrievalScopeIsolationTests(unittest.TestCase):
    @staticmethod
    def _select_format(sources, *, preference, limit):
        pipeline = _Pipeline()
        pipeline.k = limit
        state = _state(companies=[], years=[], report_scope={}, format_preference=preference)
        return pipeline._select_evidence(
            state, pipeline._build_plan(state),
            {"docs": sources, "supplemental_docs": [], "retry_queries": []},
        )["docs"]

    def test_format_reservations_fill_from_one_available_source_type(self):
        for preference in ("table", "paragraph"):
            for block_type in ("table", "paragraph"):
                with self.subTest(preference=preference, block_type=block_type):
                    sources = [(_doc(f"source-{index}", block_type=block_type), 1 - index / 10)
                               for index in range(6)]
                    selected = self._select_format(sources, preference=preference, limit=4)
                    self.assertEqual(selected, sources[:4])

    def test_format_reservations_preserve_order_then_fill_mixed_sources(self):
        sources = [(_doc(f"paragraph-{index}", block_type="paragraph"), 1 - index / 10)
                   for index in range(5)]
        sources.append((_doc("table", block_type="table"), 0.1))
        for preference, expected in (
            ("table", ["table", "paragraph-0", "paragraph-1", "paragraph-2", "paragraph-3"]),
            ("paragraph", ["paragraph-0", "paragraph-1", "table", "paragraph-2", "paragraph-3"]),
        ):
            with self.subTest(preference=preference):
                selected = self._select_format(sources, preference=preference, limit=5)
                self.assertEqual([doc.metadata["chunk_uid"] for doc, _ in selected], expected)

    def test_duplicate_sources_do_not_consume_format_reservations_or_fill_slots(self):
        first = (_doc("paragraph-A", block_type="paragraph"), 0.9)
        duplicate = (_doc("paragraph-A", block_type="paragraph"), 0.8)
        second = (_doc("paragraph-B", block_type="paragraph"), 0.7)
        table = (_doc("table", block_type="table"), 0.1)
        for preference, expected in (
            ("table", [table, first, second]),
            ("paragraph", [first, second, table]),
        ):
            with self.subTest(preference=preference):
                selected = self._select_format(
                    [first, duplicate, second, table, table], preference=preference, limit=5,
                )
                self.assertEqual(selected, expected)

    def test_empty_scope_match_does_not_restore_unrelated_sources(self):
        pipeline = _Pipeline()
        state = _state()
        excluded = (_doc("wrong", rcept_no="filing-B", year=2031), 1.0)
        selection = pipeline._select_evidence(
            state, pipeline._build_plan(state),
            {"docs": [excluded], "supplemental_docs": [excluded], "retry_queries": []},
        )
        self.assertEqual(selection["docs"], [])
        self.assertEqual(selection["seed_docs"], [])

    def test_all_evidence_paths_share_receipt_and_report_type_filter(self):
        pipeline = _Pipeline()
        state = _state()
        right = (_doc("right", rcept_no="filing-A", report_type="annual", year=2031), 0.1)
        foreign = (_doc("foreign", rcept_no="filing-B", report_type="annual", year=2031), 0.9)
        wrong_type = (_doc("type", rcept_no="filing-A", report_type="quarterly", year=2031), 0.8)
        absent = (_doc("absent", year=2031), 0.7)
        selection = pipeline._select_evidence(
            state, pipeline._build_plan(state),
            {"docs": [foreign, wrong_type, absent, right],
             "supplemental_docs": [foreign, wrong_type, absent, right], "retry_queries": []},
        )
        self.assertEqual([doc.metadata["chunk_uid"] for doc, _ in selection["docs"]], ["right"])
        self.assertEqual([doc.metadata["chunk_uid"] for doc, _ in selection["seed_docs"]], ["right"])

    def test_explicit_company_scope_survives_missing_planner_company(self):
        plan = _Pipeline()._build_plan(_state(
            companies=[], years=[], report_scope={"company": "Example Parent"},
        ))
        self.assertEqual(plan["where_filter"], {"company": "Example Parent"})

    def test_explicit_company_is_not_widened_by_planner_entities(self):
        plan = _Pipeline()._build_plan(_state(
            companies=["Example Child", "Unrelated Source"], years=[],
            report_scope={"company": "Example Parent"},
        ))
        self.assertEqual(plan["where_filter"], {"company": "Example Parent"})

    def test_multi_source_receipts_remain_the_authority_for_company_aliases(self):
        plan = _Pipeline()._build_plan(_state(
            companies=["Local Subject"], years=[],
            report_scope={"company": "Caller Alias", "source_reports": [
                {"rcept_no": "filing-A"}, {"rcept_no": "filing-B"},
            ]},
        ))
        self.assertEqual(plan["where_filter"], {"rcept_no": {"$in": ["filing-A", "filing-B"]}})

    def test_multi_period_query_does_not_reintroduce_filing_year_filter(self):
        pipeline = _Pipeline()
        state = _state(intent="comparison", years=[2029, 2030], report_scope={})
        source = (_doc("later-report", company="Example Parent", year=2031), 0.1)
        earlier = (_doc("earlier-report", company="Example Parent", year=2030), 0.2)
        selection = pipeline._select_evidence(
            state, pipeline._build_plan(state),
            {"docs": [source, earlier], "supplemental_docs": [], "retry_queries": []},
        )
        self.assertEqual(selection["docs"], [source, earlier])

    def test_supplement_filters_before_bounded_ranking(self):
        pipeline = _Pipeline()
        metadata = [
            {"chunk_uid": f"foreign-{index}", "company": "Example Parent", "year": 2031,
             "rcept_no": "filing-B", "report_type": "annual", "section_path": "Measurements"}
            for index in range(8)
        ]
        metadata.append({**metadata[0], "chunk_uid": "right", "rcept_no": "filing-A"})
        pipeline.vsm = SimpleNamespace(
            bm25_docs=["measurement 42"] * len(metadata), bm25_metadatas=metadata,
        )
        with patch("src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query", return_value=["Measurements"]), \
             patch("src.agent.financial_retrieval_pipeline._active_preferred_sections", return_value=[]), \
             patch("src.agent.financial_retrieval_pipeline._active_preferred_statement_types", return_value=[]):
            selected = pipeline._supplement_section_seed_docs(_state(answer_obligations=[]))
        self.assertEqual([doc.metadata["chunk_uid"] for doc, _ in selected], ["right"])

    def test_narrative_dedupe_does_not_collapse_report_local_chunk_numbers(self):
        pipeline = _Pipeline()
        sources = [
            (_doc("report-A:7", chunk_id=7, rcept_no="filing-A", block_type="paragraph"), 0.9),
            (_doc("report-B:7", chunk_id=7, rcept_no="filing-B", block_type="paragraph"), 0.8),
        ]
        selected = self._select_format(sources, preference="paragraph", limit=2)
        self.assertEqual(selected, sources)

    def test_narrative_dedupe_handles_zero_legacy_chunk_index(self):
        pipeline = _Pipeline()
        first = _doc("", chunk_id=0, rcept_no="filing-A", block_type="paragraph")
        second = _doc("", chunk_id=0, rcept_no="filing-B", block_type="paragraph")
        sources = [(first, 0.9), (first, 0.9), (second, 0.8)]
        selected = self._select_format(sources, preference="paragraph", limit=3)
        self.assertEqual(selected, [sources[0], sources[2]])

    def test_unknown_document_identity_cannot_dedupe_local_chunk_ids(self):
        pipeline = _Pipeline()
        for receipt in (None, "", "unknown"):
            with self.subTest(receipt=receipt):
                sources = [
                    (_doc("", chunk_id=7, company="Example Parent", year=2031,
                          rcept_no=receipt, block_type="paragraph", report_type=kind), score)
                    for kind, score in (("annual", 0.9), ("quarterly", 0.8))
                ]
                selected = self._select_format(sources, preference="paragraph", limit=2)
                self.assertEqual(selected, sources)

    def test_explicit_document_id_dedupes_despite_unknown_receipt(self):
        pipeline = _Pipeline()
        first = _doc("", chunk_id=7, rcept_no="unknown", document_id="document-A", block_type="paragraph")
        second = _doc("", chunk_id=7, rcept_no="unknown", document_id="document-B", block_type="paragraph")
        sources = [(first, 0.9), (first, 0.9), (second, 0.8)]
        selected = self._select_format(sources, preference="paragraph", limit=3)
        self.assertEqual(selected, [sources[0], sources[2]])

    def test_narrative_requirements_keep_narrative_search_enrichment(self):
        for evidence_mode in ("source_defined_group", "declared_inputs"):
            with self.subTest(evidence_mode=evidence_mode):
                pipeline = _Pipeline()
                pipeline.vsm = SimpleNamespace(search=lambda *args, **kwargs: [])
                state = _state(
                    intent="risk", query="describe operational controls",
                    retrieval_queries=["control appendix"],
                    semantic_plan={"program_required": True},
                    answer_obligations=[{
                        "obligation_id": "controls", "kind": "narrative",
                        "label": "operational controls", "evidence_mode": evidence_mode,
                        "evidence_requirements": [{
                            "requirement_id": "source_group", "label": "control appendix",
                            "required": True,
                        }],
                    }],
                )
                for query in (state["query"], "control appendix"):
                    self.assertEqual(_semantic_query_ownership(state, query)["mode"], "narrative")
                with patch("src.agent.financial_retrieval_pipeline.retrieval_hint_from_topic", return_value="") as hints, \
                     patch("src.agent.financial_retrieval_pipeline._active_preferred_sections", return_value=[]), \
                     patch.object(pipeline, "_supplement_section_seed_docs", return_value=[]):
                    pipeline._execute_searches(state, pipeline._build_plan(state))
                self.assertEqual(hints.call_args.args[2], "risk")
                self.assertTrue(hints.call_args.kwargs["include_narrative_policies"])

    def test_numeric_requirements_keep_numeric_ownership(self):
        state = _state(answer_obligations=[{
            "obligation_id": "change", "kind": "derived_value", "label": "change",
            "evidence_requirements": [{"requirement_id": "operand", "label": "input metric"}],
        }])
        ownership = _semantic_query_ownership(state, "input metric")
        self.assertEqual(ownership["mode"], "numeric")
        self.assertEqual(ownership["owner_ids"], ["operand"])


if __name__ == "__main__":
    unittest.main()
