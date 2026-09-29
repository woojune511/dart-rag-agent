"""Literal request co-occurrence is exposure evidence, never entity equivalence."""
from copy import deepcopy
import json
import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint
from tests.test_narrative_candidate_selection import candidate
from tests.test_narrative_reading_admission import select, target


def request():
    owner = target("Northwind (Boreal) rollout", "effects")
    owner["semantic_target"]["metric_surfaces"] = ["effects", "outcomes"]
    owner["retrieval_hints"] = ["Northwind rollout effects", "Boreal deployment outcomes"]
    return owner


def relevant(cid="z-related"):
    return candidate(cid, text="Boreal completed rollout through partner hubs.", section="Chapter > Z reading")


def distractions():
    return [candidate(f"a-{i}", text="General effects and outcomes are discussed.",
        section=f"Chapter > Introduction {i}") for i in range(10)]


class NarrativeJointHintExposureTests(unittest.TestCase):
    def test_compound_subject_and_separate_hints_retain_a_related_reading(self):
        for name, hints, text in (
            ("Northwind (Boreal) rollout", ["Northwind rollout effects", "Boreal deployment outcomes"],
             "Boreal completed rollout through partner hubs."),
            ("별빛팀(Starlight) 배치", ["별빛팀 배치 영향", "Starlight rollout outcome"],
             "Starlight의 배치로 각 지역의 연결 경로를 확장했습니다."),
        ):
            with self.subTest(name=name):
                owner = request()
                owner["semantic_target"]["local_subjects"] = [name]
                owner["retrieval_hints"] = hints
                catalog = [*distractions(), candidate("z-related", text=text)]
                original = deepcopy((catalog, owner))
                fingerprint = semantic_candidate_catalog_fingerprint(catalog)
                selected, _, matches, _ = select(catalog, owner)
                self.assertEqual(selected[0]["candidate_id"], "z-related")
                match = matches["z-related"]
                self.assertEqual(match["reading_joint_hint_state"], "reading:joint_terms")
                self.assertEqual(match["reading_subject_state"], "unknown")
                self.assertEqual(match["subject_state"], "unknown")
                self.assertEqual(match["state"], "unknown_only")
                self.assertEqual(match["target_local_subjects"], [name])
                self.assertEqual(len(selected), 6)
                reverse, _, repeated, _ = select(list(reversed(catalog)), owner)
                self.assertEqual(selected, reverse)
                self.assertEqual(matches, repeated)
                self.assertEqual((catalog, owner), original)
                self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)

    def test_single_or_overlapping_occurrence_is_not_two_request_terms(self):
        owner = request()
        owner["semantic_target"]["local_subjects"] = ["Boreal (Other) request"]
        owner["retrieval_hints"] = ["Boreal oreal effects"]
        for text in ("Boreal " * 20, "effects " * 20, "Boreal has effects"):
            with self.subTest(text=text):
                # A distinct additional term is needed; an overlap inside the
                # same name is not two observed occurrences. The last source
                # has a real additional occurrence and therefore may rank.
                _, _, matches, _ = select([candidate("source", text=text)], owner)
                expected = "reading:joint_terms" if text == "Boreal has effects" else "unknown"
                self.assertEqual(matches["source"]["reading_joint_hint_state"], expected)

    def test_repeated_words_and_hints_do_not_add_rank(self):
        owner = request()
        catalog = [relevant()]
        _, _, before, _ = select(catalog, owner)
        owner["retrieval_hints"] *= 10
        source = relevant()
        source["source_text"] *= 20
        source["source_bundle_text"] = source["source_text"]
        _, _, after, _ = select([source], owner)
        self.assertEqual(before["z-related"]["rank_vector"], after["z-related"]["rank_vector"])

    def test_body_contexts_and_cells_do_not_join_to_make_a_joint_hint(self):
        split = candidate("split", text="Boreal", heading="rollout")
        cells = candidate("cells", text="Boreal rollout")
        cells["source_context_provenance"] = {"source_text": "Boreal rollout",
            "source_segments": [{"text_span": [0, 6]}, {"text_span": [7, 14]}]}
        context_cells = candidate("context-cells")
        context_cells["source_contexts"] = [{"relation": "preceding_block", "source_text": "Boreal rollout",
            "source_segments": [{"text_span": [0, 6]}, {"text_span": [7, 14]}]}]
        _, _, matches, _ = select([split, cells, context_cells], request())
        self.assertTrue(all(m["reading_joint_hint_state"] == "unknown" for m in matches.values()))

    def test_hidden_tails_metadata_and_unattached_context_do_not_supply_terms(self):
        hidden = candidate("hidden", text="General background.")
        hidden.update(source_text=relevant()["source_text"], local_entity_surfaces=["Boreal"],
            local_heading="Boreal rollout", section_path="Boreal rollout")
        hidden["source_contexts"] = [{"relation": "following_block", "source_text": "Boreal rollout"}]
        _, _, matches, _ = select([hidden], request())
        self.assertEqual(matches["hidden"]["reading_joint_hint_state"], "unknown")

    def test_retained_continuation_or_attached_context_can_supply_joint_terms(self):
        for relation, expected in (("source_continuation", "reading:joint_terms"),
                ("ancestor_heading", "context:joint_terms"), ("intermediate_heading", "context:joint_terms"),
                ("caption", "context:joint_terms"), ("preceding_block", "context:joint_terms")):
            with self.subTest(relation=relation):
                source = candidate("source")
                source["source_contexts"] = [{"relation": relation, "source_text": relevant()["source_text"]}]
                _, _, matches, _ = select([source], request())
                self.assertEqual(matches["source"]["reading_joint_hint_state"], expected)

    def test_whole_subject_mention_keeps_its_state_and_independent_topic_hint(self):
        owner = request()
        owner["semantic_target"]["local_subjects"] = ["Boreal"]
        _, _, matches, _ = select([relevant()], owner)
        match = matches["z-related"]
        self.assertEqual(match["reading_subject_state"], "local_literal")
        self.assertEqual(match["reading_joint_hint_state"], "reading:joint_terms")
        self.assertEqual(match["rank_vector"][1], 1)

    def test_scope_and_metric_words_cannot_be_partial_subject_anchors(self):
        owner = request()
        owner["semantic_target"]["local_subjects"] = ["Example issuer effects", "2042 outcomes"]
        source = candidate("source", text="Example issuer 2042 effects rollout outcomes.")
        _, _, matches, _ = select([source], owner)
        self.assertEqual(matches["source"]["reading_joint_hint_state"], "unknown")
        owner["semantic_target"]["local_subjects"] = ["Northwind (Boreal) rollout"]
        owner["retrieval_hints"] = ["Example issuer 2042"]
        _, _, matches, _ = select([relevant()], owner)
        self.assertEqual(matches["z-related"]["reading_joint_hint_state"], "unknown")

    def test_subject_words_removed_from_a_metric_do_not_become_new_anchors(self):
        owner = target("partner handling method", "continuity partner handling method")
        owner["retrieval_hints"] = ["continuity", "partner handling method"]
        source = candidate("source", text="The handling method supports continuity.")
        _, _, matches, _ = select([source], owner)
        self.assertEqual(matches["source"]["reading_subject_state"], "unknown")
        self.assertNotEqual(matches["source"]["reading_hint_state"], "unknown")
        self.assertEqual(matches["source"]["reading_joint_hint_state"], "unknown")

    def test_unpartitioned_structured_rendering_cannot_invent_same_cell_cooccurrence(self):
        source = candidate("source", table="table", text="Boreal | rollout | 1")
        _, _, matches, _ = select([source], request())
        self.assertEqual(matches["source"]["reading_joint_hint_state"], "unknown")
        source.update(source_text="Boreal rollout", source_bundle_text="Boreal rollout",
            source_context_provenance={"source_text": "Boreal rollout", "source_segments": [
                {"text_span": [0, 14], "cell_locator": "one-cell"}]})
        _, _, matches, _ = select([source], request())
        self.assertEqual(matches["source"]["reading_joint_hint_state"], "reading:joint_terms")

    def test_request_terms_do_not_inherit_another_owners_search_hints(self):
        parent = request()
        child = {"requirement_id": "child", "label": "effects", "scope": parent["scope"],
            "semantic_target": deepcopy(parent["semantic_target"])}
        parent["evidence_requirements"] = [child]
        projection = _semantic_candidate_cohorts([relevant()], [parent])
        matches = projection["candidate_match_by_id"]["z-related"]
        self.assertEqual(matches["overview"]["reading_joint_hint_state"], "reading:joint_terms")
        self.assertEqual(matches["child"]["reading_joint_hint_state"], "unknown")

    def test_explicit_scope_conditions_and_retry_exclusion_remain_hard(self):
        owner = request()
        owner["scope"]["consolidation_scope"] = "consolidated"
        owner["source_sections"] = ["Allowed"]
        good = relevant("good")
        good.update(section_path="Allowed", consolidation_scope="consolidated")
        foreign = {**good, "candidate_id": "foreign", "company": "Other", "document_company": "Other"}
        period = {**good, "candidate_id": "period", "period": "2041"}
        separate = {**good, "candidate_id": "separate", "consolidation_scope": "separate"}
        section = {**good, "candidate_id": "section", "section_path": "Elsewhere"}
        selected, _, _, _ = select([good, foreign, period, separate, section], owner)
        self.assertEqual([c["candidate_id"] for c in selected], ["good"])
        selected, _, _, _ = select([good], owner, excluded_candidate_ids=["good"])
        self.assertEqual(selected, [])
        owner["display_unit"] = "USD"
        good.update(normalized_unit="PERCENT")
        selected, _, matches, _ = select([good], owner)
        self.assertEqual(selected, [])
        self.assertEqual(matches["good"]["unit_state"], "conflict")

    def test_joint_hint_is_absent_from_compiler_and_numeric_matching(self):
        owner = request()
        source = relevant()
        projection = _semantic_candidate_cohorts([source], [owner])
        payload = FinancialAgent._semantic_program_prompt_payload([source], projection)
        self.assertNotIn("reading_joint_hint_state", json.dumps(payload))
        owner["kind"] = "direct_value"
        without = deepcopy(owner)
        without["retrieval_hints"] = []
        _, _, before, _ = select([source], without)
        _, _, after, _ = select([source], owner)
        self.assertEqual(before, after)
        self.assertNotIn("reading_joint_hint_state", after["z-related"])

    def test_newly_visible_reading_still_needs_source_grounded_compiler_claims(self):
        from src.agent.financial_calculation_execution import validate_semantic_calculation_program
        from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
        from tests.narrative_address_test_support import address_program, model_program
        from tests.semantic_program_test_support import _StructuredQueueLLM
        from tests.test_narrative_claim_grounding import claim

        owner = request()
        owner["request_unit_ids"] = ["request_001"]
        catalog = [*distractions(), relevant()]
        body = relevant()["source_text"]
        authored = {"narrative_bindings": [{"obligation_id": "overview",
            "claims": [claim("Boreal", body, "z-related", body)]}]}
        llm = _StructuredQueueLLM(model_program(authored, catalog))
        query = "Describe the effects of Northwind (Boreal) rollout."
        state = _case_state({"question": query, "obligations": [owner]}, catalog)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 1)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        # Lexical relevance cannot turn a partial request spelling into a
        # source-supported full name. The authored mock is not model evidence.
        authored["narrative_bindings"][0]["claims"][0]["subject"] = "Northwind Holdings"
        rejected = validate_semantic_calculation_program(program=address_program(authored, catalog),
            obligations=[owner], candidate_catalog=catalog, query=query, require_narrative_claims=True)
        self.assertIn("ungrounded_narrative_subject", {error["code"] for error in rejected["errors"]})


if __name__ == '__main__':
    unittest.main()
