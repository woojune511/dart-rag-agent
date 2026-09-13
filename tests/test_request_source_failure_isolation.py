"""Anonymous current-boundary characterizations, not repaired-output oracles.

These tests retain identity/quote limitations as explicit contrasts; reading
exposure now separates the short-name diagnostic from shortlist allocation.
No saved questions, candidate IDs, stores, APIs or external model outputs enter them.
"""
from copy import deepcopy
from tests.narrative_address_test_support import address_program, model_program
import unittest

from langchain_core.documents import Document

from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_candidate_matching import structured_subject_evidence
from src.agent.financial_graph_calculation import _rank_applicable_owner_candidates, _semantic_candidate_visibility
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_source_scope import source_section_allowed_for_query
from src.storage.bm25_index import metadata_matches_filter
from src.storage.search_merge import merge_rrf_results
from tests.semantic_program_test_support import _obligation, _requirement
from tests.test_narrative_candidate_selection import candidate, owner
from tests.test_narrative_claim_grounding import claim, source
from tests.test_planner_subject_projection import authored_owner, cell, plan
from tests.test_retrieval_scope_isolation import _Pipeline, _state


class RequestSourceFailureIsolationTests(unittest.TestCase):
    def test_planner_instruction_does_not_rewrite_a_descriptive_subject_response(self):
        for name, wrapper in (("Elm", "division"), ("Birch", "unit"), ("별빛", "부문")):
            with self.subTest(name=name):
                declared = f"{name} {wrapper}"
                query = f"Return the 2042 quantity for {declared}."
                projection, llm = plan(query, [authored_owner([declared])])
                target = projection["answer_obligations"][0]["semantic_target"]["local_subjects"]
                self.assertEqual(target, [declared])
                self.assertEqual(len(llm.prompts), 1)
                self.assertEqual(structured_subject_evidence(cell(name), target)["state"], "unknown")
                self.assertEqual(structured_subject_evidence(cell(name), [name])["state"], "match")

    def test_adding_context_cannot_replace_complete_cell_identity(self):
        row = cell("Elm", source_contexts=[{"source_text": "The Elm division uses partner delivery."}])
        before = deepcopy(row)
        self.assertEqual(structured_subject_evidence(row, ["Elm division"])["state"], "unknown")
        self.assertEqual(structured_subject_evidence(row, ["Elm"])["state"], "match")
        for different in ("Elm East", "Elm and other units"):
            self.assertEqual(structured_subject_evidence(cell(different), ["Elm"])["state"], "unknown")
        self.assertEqual(row, before)

    def test_another_claims_subject_quote_cannot_ground_a_subjectless_claim(self):
        catalog = [source("passage", "Elm Systems uses partner delivery. The platform handles secure workloads.")]
        obligations = [_obligation("summary", "narrative", "Describe the platform.")]
        program = {"narrative_bindings": [{"obligation_id": "summary", "claims": [
            claim("Elm Systems", "Uses partner delivery.", "passage", "Elm Systems uses partner delivery."),
            claim("Elm Systems", "The platform handles secure workloads.", "passage", "The platform handles secure workloads."),
        ]}]}
        def validate(raw):
            return validate_semantic_calculation_program(program=address_program(raw, catalog), candidate_catalog=catalog,
                obligations=obligations, query="Describe the platform.", require_narrative_claims=True)
        failed = validate(program)
        self.assertTrue(any(e["code"] == "ungrounded_narrative_subject" and e["location"] == "subject_bindings[1]"
                            for e in failed["errors"]))
        repaired = deepcopy(program)
        repaired["narrative_bindings"][0]["claims"][1]["evidence_bindings"].append(
            {"candidate_id": "passage", "evidence_text": "Elm Systems uses partner delivery."})
        self.assertEqual(validate(repaired)["status"], "ready")
        self.assertEqual(len(program["narrative_bindings"][0]["claims"][1]["evidence_bindings"]), 1)

    def test_visible_source_is_not_selectable_for_every_required_input(self):
        catalog = [source("intro", "Elm expanded its partner network."), source("detail", "Elm uses local delivery.")]
        obligations = [_obligation("summary", "narrative", "Describe network and delivery.", evidence_requirements=[
            _requirement("summary:network", "Network"), _requirement("summary:delivery", "Delivery")])]
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=["intro", "detail"],
            candidate_ids_by_owner={"summary": ["intro", "detail"], "summary:network": ["intro"], "summary:delivery": ["detail"]})
        program = {"narrative_bindings": [{"obligation_id": "summary", "claims": [
            claim("Elm", "Expanded its partner network.", "intro", "Elm expanded its partner network.", source_requirement_id="summary:network"),
            claim("Elm", "Uses local delivery.", "detail", "Elm uses local delivery.", source_requirement_id="summary:delivery"),
        ]}]}
        def validate(raw):
            return validate_semantic_calculation_program(program=address_program(raw, catalog), obligations=obligations, candidate_catalog=catalog,
                candidate_visibility=visibility, query="Describe network and delivery.", require_narrative_claims=True)
        self.assertEqual(validate(program)["status"], "ready")
        swapped = deepcopy(program)
        swapped["narrative_bindings"][0]["claims"][1] = claim("Elm", "Expanded its partner network.", "intro",
            "Elm expanded its partner network.", source_requirement_id="summary:delivery")
        # The renderer owns flat text/IDs: rebuild from claims instead of
        # retaining the old, deliberately inconsistent derived projection.
        swapped = model_program({"narrative_bindings": [{
            "obligation_id": "summary", "claims": swapped["narrative_bindings"][0]["claims"],
        }]}, catalog).model_dump()
        rejected = validate(swapped)
        self.assertIn("intro", visibility.visible_candidate_ids)
        self.assertIn("candidate_not_exposed_to_compiler", {e["code"] for e in rejected["errors"]})
        self.assertIn("missing_required_evidence_binding", {e["code"] for e in rejected["errors"]})

    def test_short_name_identity_stays_unknown_without_starving_reading_exposure(self):
        for name in ("Elm", "Oak", "별빛팀"):
            with self.subTest(name=name):
                target = owner("relationship explanation")
                target["semantic_target"]["local_subjects"] = [name]
                rows = [candidate(f"row-{i}", table=f"table-{i}", row=f"row-{i}", text="Observed volume | 1") for i in range(6)]
                for row in rows:
                    row.update(row_label=name, row_headers=[name], column_headers=["Count"])
                prose = candidate("explanation", text=f"After joining the network, {name} reached additional customers.")
                selected, _, matches, _ = _rank_applicable_owner_candidates([*rows, prose], owner=target,
                    candidate_kind="evidence", limit=6)
                self.assertEqual(matches["explanation"]["subject_state"], "unknown")
                self.assertTrue(all(matches[r["candidate_id"]]["subject_state"] == "match" for r in rows))
                self.assertEqual(matches["explanation"]["reading_subject_state"], "local_literal")
                self.assertIn("explanation", [r["candidate_id"] for r in selected])
                selected_reverse, _, _, _ = _rank_applicable_owner_candidates([prose, *reversed(rows)],
                    owner=target, candidate_kind="evidence", limit=6)
                self.assertEqual(selected, selected_reverse)

    def test_longer_prose_name_contrast_documents_the_literal_threshold_not_semantics(self):
        for name in ("Aster", "Birch"):
            target = owner("relationship explanation")
            target["semantic_target"]["local_subjects"] = [name]
            prose = candidate("explanation", text=f"After joining the network, {name} reached additional customers.")
            _, _, matches, _ = _rank_applicable_owner_candidates([prose], owner=target, candidate_kind="evidence", limit=6)
            self.assertEqual(matches["explanation"]["subject_state"], "match")
            self.assertEqual(matches["explanation"]["metric_state"], "unknown")

    def test_source_section_filter_after_top_k_can_empty_an_authorized_window(self):
        outside = Document(page_content="Other note", metadata={"chunk_uid": "outside", "section_path": "Other notes", "rcept_no": "filing-A"})
        inside = Document(page_content="Requested note", metadata={"chunk_uid": "inside", "section_path": "Selected notes", "rcept_no": "filing-A"})
        foreign = Document(page_content="Different filing", metadata={"chunk_uid": "foreign", "section_path": "Selected notes", "rcept_no": "filing-B"})
        obligations = [_obligation("summary", "narrative", "Describe policies", source_sections=["Selected notes"])]
        where = {"rcept_no": "filing-A"}
        def permitted(doc):
            return metadata_matches_filter(doc.metadata, where) and source_section_allowed_for_query(doc.metadata, obligations)
        vector = [(outside, 3), (inside, 2)]
        lexical = [(outside, 3), (foreign, 2), (inside, 1)]
        current = merge_rrf_results(vector, lexical, k=1, k_rrf=60)
        self.assertEqual([d.metadata["chunk_uid"] for d, _ in current], ["outside"])
        self.assertEqual([item for item in current if permitted(item[0])], [])
        early = merge_rrf_results([p for p in vector if permitted(p[0])], [p for p in lexical if permitted(p[0])], k=1, k_rrf=60)
        self.assertEqual([d.metadata["chunk_uid"] for d, _ in early], ["inside"])
        pipeline = _Pipeline()
        pipeline.k = 1
        state = _state(query="Describe policies in Selected notes.", topic="policies", companies=[], years=[],
            report_scope=where, format_preference="paragraph", answer_obligations=obligations)
        plan = pipeline._build_plan(state)
        for incoming, expected in ((current, []), (early, ["inside"])):
            result = pipeline._select_evidence(state, plan, {"docs": incoming, "supplemental_docs": [], "retry_queries": []})
            self.assertEqual([d.metadata["chunk_uid"] for d, _ in result["docs"]], expected)

    def test_unrestricted_sibling_keeps_shared_retrieval_open_without_widening_owner(self):
        metadata = {"section_path": "Other notes", "rcept_no": "filing-A"}
        restricted = _obligation("notes", "narrative", "Policies", source_sections=["Selected notes"])
        unrestricted = _obligation("overview", "narrative", "Overview")
        self.assertFalse(source_section_allowed_for_query(metadata, [restricted]))
        self.assertTrue(source_section_allowed_for_query(metadata, [restricted, unrestricted]))
        self.assertFalse(source_section_allowed_for_query(metadata, [restricted]))


if __name__ == "__main__":
    unittest.main()
