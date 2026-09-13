"""Reading relevance is not literal issuer identity or a correctness oracle."""
from copy import deepcopy
import unittest

from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from tests.test_narrative_candidate_selection import candidate
from tests.test_narrative_reading_admission import target, select, row


def sources(name="Elm"):
    return [candidate(f"intro-{i}", text=f"{name} provides general background.",
        section=f"Chapter > Introduction {i}") for i in range(10)]


def required(label="continuity management approach", hint="continuity", name="Elm"):
    row = target(name, label)
    row["retrieval_hints"] = [hint]
    return row


class NarrativeReadingRelevanceTests(unittest.TestCase):
    def test_literal_issuer_overviews_cannot_starve_scoped_subject_implicit_topic(self):
        for name in ("Q", "Elm", "별빛팀"):
            with self.subTest(name=name):
                text = candidate("z-topic", text="The network reach expands through local partners.")
                selected, _, matches, _ = select([*sources(name), text], target(name))
                self.assertEqual(selected[0]["candidate_id"], "z-topic")
                self.assertEqual(matches["z-topic"]["scope_state"], "compatible")
                self.assertEqual(matches["z-topic"]["reading_state"], "compatible")
                self.assertEqual(matches["z-topic"]["subject_state"], "unknown")

    def test_owner_search_hint_connects_short_source_topic_without_new_keywords(self):
        for label, hint, text in (
            ("continuity management approach", "continuity", "Continuity is maintained through rotating partners."),
            ("transport coordination method", "transport", "Transport follows scheduled regional routes."),
            ("협력체계 운영 방식", "협력체계", "협력체계는 각 지역의 담당자가 유지합니다."),
        ):
            with self.subTest(label=label):
                catalog = [*sources(), candidate("z-topic", text=text)]
                selected, _, matches, _ = select(catalog, required(label, hint))
                self.assertEqual(selected[0]["candidate_id"], "z-topic")
                self.assertEqual(matches["z-topic"]["metric_state"], "unknown")
                self.assertNotEqual(matches["z-topic"]["reading_hint_state"], "unknown")

    def test_mention_does_not_change_scope_tier_or_override_declared_scope(self):
        owner = required()
        owner["scope"]["basis"] = "separate perimeter"
        scoped = {**sources()[0], "basis": "separate perimeter"}
        unscoped = candidate("z-topic", text="Continuity is maintained through rotating partners.")
        selected, _, matches, _ = select([unscoped, scoped], owner)
        self.assertEqual(selected[0]["candidate_id"], scoped["candidate_id"])
        self.assertEqual(matches["z-topic"]["reading_state"], "unknown_only")
        foreign = {**unscoped, "candidate_id": "foreign", "company": "Another issuer"}
        selected, _, matches, _ = select([scoped, foreign], owner)
        self.assertNotIn("foreign", [row["candidate_id"] for row in selected])
        self.assertEqual(matches["foreign"]["reading_state"], "explicit_conflict")

    def test_hint_is_exposure_only_not_new_identity_or_numeric_matching_authority(self):
        owner = required()
        catalog = [candidate("topic", text="Continuity is maintained through rotating partners.")]
        without = deepcopy(owner)
        without["retrieval_hints"] = []
        _, _, before, _ = select(catalog, without)
        _, _, after, _ = select(catalog, owner)
        for field in ("state", "scope_state", "subject_state", "metric_state", "unit_state"):
            self.assertEqual(before["topic"][field], after["topic"][field])
        from src.agent.financial_compiler_presentation import project_prompt_match
        self.assertNotIn("reading_hint_state", project_prompt_match(after["topic"]))
        owner["kind"] = without["kind"] = "direct_value"
        catalog = [{**row(), "source_text": "Continuity | 1", "source_bundle_text": "Continuity | 1"}]
        _, _, before, _ = select(catalog, without)
        _, _, after, _ = select(catalog, owner)
        self.assertEqual(before, after)

    def test_hints_read_visible_body_and_attached_context_not_metadata_or_hidden_tail(self):
        hidden = candidate("hidden", text="General background.")
        hidden.update(source_text="General background. Continuity is maintained.", local_heading="Continuity")
        for relation in ("ancestor_heading", "source_continuation"):
            with self.subTest(relation=relation):
                visible = candidate("visible", text="General background.")
                visible["source_contexts"] = [{"relation": relation, "source_text": "Continuity"}]
                _, _, matches, _ = select([hidden, visible], required())
                self.assertEqual(matches["hidden"]["reading_hint_state"], "unknown")
                self.assertNotEqual(matches["visible"]["reading_hint_state"], "unknown")

    def test_scope_only_hints_and_another_owners_hints_do_not_create_topic_evidence(self):
        owner = required()
        owner["retrieval_hints"] = ["Elm", owner["scope"]["company"], owner["scope"]["period"]]
        _, _, matches, _ = select(sources(), owner)
        self.assertTrue(all(row["reading_hint_state"] == "unknown" for row in matches.values()))
        parent = required()
        child = {"requirement_id": "delivery", "label": "delivery management approach",
            "scope": parent["scope"], "semantic_target": {"local_subjects": ["Elm"],
                "metric_surfaces": ["delivery management approach"], "concept_keys": []}}
        parent["evidence_requirements"] = [child]
        catalog = [candidate("topic", text="Continuity is maintained through rotating partners.")]
        cohorts = _semantic_candidate_cohorts(catalog, [parent])
        matches = cohorts["candidate_match_by_id"]["topic"]
        self.assertNotEqual(matches["overview"]["reading_hint_state"], "unknown")
        self.assertEqual(matches["delivery"]["reading_hint_state"], "unknown")

    def test_repetition_and_input_order_do_not_accumulate_a_hint_bonus(self):
        owner = required()
        catalog = [*sources(), candidate("z-topic", text="Continuity is maintained through rotating partners.")]
        selected, _, matches, _ = select(catalog, owner)
        repeated = deepcopy(owner)
        repeated["retrieval_hints"] *= 8
        reverse, _, again, _ = select(list(reversed(catalog)), repeated)
        self.assertEqual(selected, reverse)
        self.assertEqual(matches, again)

    def test_independent_topics_get_their_own_leading_reading_without_target_mutation(self):
        owners = [required(), required("delivery management approach", "delivery")]
        owners[1]["obligation_id"] = "delivery"
        for row in owners:
            row["evidence_requirements"] = [{"requirement_id": row["obligation_id"] + ":input",
                "label": row["label"], "retrieval_hints": row["retrieval_hints"],
                "scope": row["scope"], "semantic_target": row["semantic_target"]}]
        catalog = [*sources(), candidate("continuity", text="Continuity is maintained through rotating partners."),
            candidate("delivery", text="Delivery follows scheduled regional routes.")]
        original = deepcopy((catalog, owners))
        plan = _semantic_candidate_cohorts(catalog, owners)
        for owner_id, candidate_id in (("overview", "continuity"), ("delivery", "delivery")):
            for key in (owner_id, owner_id + ":input"):
                self.assertEqual(plan["candidate_ids_by_owner"][key][0], candidate_id)
                self.assertEqual(len(plan["candidate_ids_by_owner"][key]), 6)
        self.assertEqual((catalog, owners), original)


if __name__ == "__main__":
    unittest.main()
