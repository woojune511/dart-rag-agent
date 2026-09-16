"""A literal subject mention cannot disable an independent lexical topic hint."""
from copy import deepcopy
import json
import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint
from tests.test_narrative_candidate_selection import candidate
from tests.test_narrative_joint_hint_exposure import distractions, request
from tests.test_narrative_reading_admission import select


class NarrativeHintMonotonicityTests(unittest.TestCase):
    def test_independent_topic_and_literal_mention_precede_a_weak_lexical_pair(self):
        owner = request()
        owner["semantic_target"]["local_subjects"] = ["Boreal"]
        weak = [candidate(f"a-{i}", text="Boreal completed rollout.",
            section=f"Chapter > A {i}") for i in range(10)]
        direct = candidate("z-direct", text="Boreal described rollout effects and outcomes.",
            section="Chapter > Z evidence")
        selected, _, matches, _ = select([*weak, direct], owner)
        self.assertEqual(selected[0]["candidate_id"], "z-direct")
        self.assertGreater(matches["z-direct"]["rank_vector"], matches["a-0"]["rank_vector"])
        # A topic-only overview cannot displace a same-surface request pair.
        pair = candidate("z-pair", text=weak[0]["source_text"])
        selected, _, _, _ = select([*distractions(), pair], owner)
        self.assertEqual(selected[0]["candidate_id"], "z-pair")

    def test_declaring_an_already_visible_subject_does_not_remove_topic_exposure(self):
        for compound, literal, hints, text in (
            ("Northwind (Boreal) rollout", "Boreal", ["Northwind rollout effects", "Boreal deployment outcomes"],
             "Boreal completed rollout through partner hubs."),
            ("별빛팀(Starlight) 배치", "Starlight", ["별빛팀 배치 영향", "Starlight rollout outcome"],
             "Starlight의 배치로 각 지역의 연결 경로를 확장했습니다."),
            ("Silver Birch regional launch", "Silver Birch", ["Silver Birch rollout effects"],
             "Silver Birch completed rollout through partner hubs."),
        ):
            with self.subTest(literal=literal):
                owner = request()
                owner["semantic_target"]["local_subjects"] = [compound]
                owner["retrieval_hints"] = hints
                catalog = [*distractions(), candidate("z-related", text=text)]
                before = deepcopy((catalog, owner))
                fingerprint = semantic_candidate_catalog_fingerprint(catalog)
                selected, _, matches, _ = select(catalog, owner)
                self.assertEqual(selected[0]["candidate_id"], "z-related")
                whole = deepcopy(owner)
                whole["semantic_target"]["local_subjects"].append(literal)
                after, _, observed, _ = select(catalog, whole)
                self.assertEqual(after, selected)
                self.assertEqual(observed["z-related"]["rank_vector"], matches["z-related"]["rank_vector"])
                self.assertEqual(observed["z-related"]["reading_subject_state"], "local_literal")
                self.assertEqual(observed["z-related"]["reading_joint_hint_state"], "reading:joint_terms")
                self.assertEqual((catalog, owner), before)
                self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)

    def test_bare_full_subject_is_not_itself_a_topic_hint(self):
        owner = request()
        owner["semantic_target"]["local_subjects"] = ["Boreal"]
        for text in ("Boreal " * 30, "Boreal performs unrelated work.", "rollout " * 30):
            with self.subTest(text=text):
                _, _, matches, _ = select([candidate("source", text=text)], owner)
                self.assertEqual(matches["source"]["reading_joint_hint_state"], "unknown")
                self.assertEqual(matches["source"]["rank_vector"][1], 0)

    def test_full_mention_keeps_partition_and_hidden_source_boundaries(self):
        owner = request()
        owner["semantic_target"]["local_subjects"] = ["Boreal"]
        split = candidate("split", text="Boreal", heading="rollout")
        cells = candidate("cells", text="Boreal rollout")
        cells["source_context_provenance"] = {"source_text": "Boreal rollout",
            "source_segments": [{"text_span": [0, 6]}, {"text_span": [7, 14]}]}
        structured = candidate("unpartitioned", table="observed-table", text="Boreal rollout")
        hidden = candidate("hidden", text="Boreal")
        hidden["source_text"] = "Boreal rollout"
        hidden["source_contexts"] = [{"relation": "following_block", "source_text": "Boreal rollout"}]
        for source in (split, cells, structured, hidden):
            with self.subTest(source=source["candidate_id"]):
                _, _, matches, _ = select([source], owner)
                self.assertEqual(matches[source["candidate_id"]]["reading_joint_hint_state"], "unknown")

    def test_full_mention_can_use_one_retained_context_partition(self):
        owner = request()
        owner["semantic_target"]["local_subjects"] = ["Boreal"]
        for relation, expected in (("source_continuation", "reading:joint_terms"),
                ("ancestor_heading", "context:joint_terms"), ("caption", "context:joint_terms")):
            with self.subTest(relation=relation):
                source = candidate("source")
                source["source_contexts"] = [{"relation": relation, "source_text": "Boreal rollout"}]
                _, _, matches, _ = select([source], owner)
                self.assertEqual(matches["source"]["reading_joint_hint_state"], expected)

    def test_full_mention_does_not_join_overlapping_terms_or_borrow_owner_hints(self):
        owner = request()
        owner["semantic_target"]["local_subjects"] = ["Boreal"]
        owner["retrieval_hints"] = ["Boreal oreal effects"]
        _, _, matches, _ = select([candidate("source", text="Boreal")], owner)
        self.assertEqual(matches["source"]["reading_joint_hint_state"], "unknown")
        owner["retrieval_hints"] = ["Boreal rollout effects"]
        owner["evidence_requirements"] = [{"requirement_id": "child", "label": "effects",
            "scope": deepcopy(owner["scope"]), "semantic_target": deepcopy(owner["semantic_target"])}]
        catalog = [candidate("source", text="Boreal rollout")]
        projection = _semantic_candidate_cohorts(catalog, [owner])
        matches = projection["candidate_match_by_id"]["source"]
        self.assertEqual(matches["overview"]["reading_joint_hint_state"], "reading:joint_terms")
        self.assertEqual(matches["child"]["reading_joint_hint_state"], "unknown")

    def test_hint_cannot_change_source_conditions_authority_or_numeric_ranking(self):
        owner = request()
        owner["semantic_target"]["local_subjects"] = ["Boreal"]
        good = candidate("good", text="Boreal rollout", section="Allowed")
        owner["source_sections"] = ["Allowed"]
        foreign = {**good, "candidate_id": "foreign", "document_company": "Other", "company": "Other"}
        wrong_period = {**good, "candidate_id": "wrong-period", "period": "2041"}
        wrong_section = {**good, "candidate_id": "wrong-section", "section_path": "Elsewhere"}
        catalog = [good, foreign, wrong_period, wrong_section]
        selected, _, matches, _ = select(catalog, owner)
        self.assertEqual([c["candidate_id"] for c in selected], ["good"])
        without = deepcopy(owner)
        without["retrieval_hints"] = []
        _, _, unchanged, _ = select(catalog, without)
        for cid in matches:
            for key in ("state", "scope_state", "subject_state", "unit_state", "reading_subject_state"):
                self.assertEqual(matches[cid][key], unchanged[cid][key])
        excluded, _, _, _ = select(catalog, owner, excluded_candidate_ids=["good"])
        self.assertEqual(excluded, [])
        payload = FinancialAgent._semantic_program_prompt_payload(catalog, _semantic_candidate_cohorts(catalog, [owner]))
        self.assertNotIn("reading_joint_hint_state", json.dumps(payload))
        owner["kind"] = without["kind"] = "direct_value"
        self.assertEqual(select(catalog, owner), select(catalog, without))


if __name__ == "__main__":
    unittest.main()
