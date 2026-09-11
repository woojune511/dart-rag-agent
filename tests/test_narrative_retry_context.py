"""Retry carries the failed draft, not a new source or a semantic correctness oracle."""

from copy import deepcopy
import json
import unittest

from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_narrative_claims import project_narrative_retry_drafts
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM
from tests.test_narrative_claim_grounding import claim, source


def prompt_json(prompt, marker):
    text = prompt.to_messages()[0].content.split(marker + "\n", 1)[1]
    return json.JSONDecoder().raw_decode(text.lstrip())[0]


class NarrativeRetryContextTests(unittest.TestCase):
    def setUp(self):
        self.body = "We serve through distributors."
        self.catalog = [source("note", self.body, source_contexts=[{
            "context_id": "heading", "relation": "ancestor_heading",
            "source_text": "Larch", "source_span": [10, 15],
        }])]
        self.owners = [_obligation("activity", "narrative", "Describe activity.")]
        self.question = "Describe activity, its local subject, and any unresolved attribution."
        self.bad = {"narrative_bindings": [{"obligation_id": "activity", "claims": [
            claim("We", self.body, "note", self.body),
            claim("Larch", "In this section, We refers to Larch.", "note", self.body),
        ]}]}
        self.good = deepcopy(self.bad)
        self.good["narrative_bindings"][0]["claims"][1]["evidence_bindings"].append({
            "candidate_id": "note", "context_id": "heading", "evidence_text": "Larch"})

    def test_retry_carries_failed_claim_locations_without_replaying_accepted_island(self):
        accepted = SemanticCalculationProgram(direct_bindings=[{
            "obligation_id": "size", "candidate_id": "size-cell"}])
        bad = SemanticCalculationProgram.model_validate(self.bad)
        good = SemanticCalculationProgram.model_validate(self.good)
        llm = _StructuredQueueLLM(accepted, bad, good)
        state = _case_state({"question": self.question, "obligations": [
            _obligation("size", "direct_value", "Size"), *self.owners]},
            [_candidate("size-cell", 12), *self.catalog])
        before = deepcopy(state)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(json.dumps(compiled["semantic_program"]["direct_bindings"], sort_keys=True),
            json.dumps(accepted.model_dump()["direct_bindings"], sort_keys=True))
        feedback = prompt_json(llm.prompts[2], "재시도 피드백(없으면 -):")
        self.assertIn("unvalidated_narrative_drafts", feedback)
        drafts = feedback["unvalidated_narrative_drafts"]
        self.assertEqual([draft["obligation_id"] for draft in drafts], ["activity"])
        self.assertEqual([row["location"] for row in drafts[0]["claims"]],
            ["narrative_claims[0]", "narrative_claims[1]"])
        for original, draft in zip(bad.model_dump()["narrative_bindings"][0]["claims"], drafts[0]["claims"]):
            for key in ("subject", "text", "evidence_bindings"):
                self.assertEqual(draft[key], original[key])
        self.assertNotIn("size-cell", json.dumps(drafts))
        marker = "Source bundles, candidate cohorts, and candidates_by_id:"
        self.assertEqual(prompt_json(llm.prompts[1], marker), prompt_json(llm.prompts[2], marker))
        self.assertIn(self.question, llm.prompts[2].to_messages()[0].content)
        self.assertEqual(state, before)

    def test_projection_removes_hidden_foreign_and_wrong_requirement_links_without_losing_claims(self):
        owners = [_obligation("activity", "narrative", "Activity", evidence_requirements=[
            {"requirement_id": "activity:a"}, {"requirement_id": "activity:b"}])]
        links = [
            {"candidate_id": "a", "evidence_text": "Still an invalid draft quote."},
            {"candidate_id": "a", "source_requirement_id": "activity:a", "evidence_text": "Larch"},
            {"candidate_id": "b", "source_requirement_id": "activity:a", "evidence_text": "Mismatch"},
            {"candidate_id": "a", "source_requirement_id": "other:r", "evidence_text": "Foreign owner"},
            {"candidate_id": "req-only", "source_requirement_id": "activity:a", "evidence_text": "Not owner visible"},
            {"candidate_id": "excluded", "evidence_text": "Previously selected, now excluded"},
            {"candidate_id": "invented", "evidence_text": "Never visible"},
        ]
        program = {"narrative_bindings": [{"obligation_id": "activity", "claims": [
            {"subject": "Larch", "text": "Needs repair.", "evidence_bindings": links},
            claim("みどり", "追加説明。", "excluded", "Unavailable"),
        ], "scope_applicability_fields": ["segment"]}]}
        selectable = {"activity": ["a", "b"], "activity:a": ["a", "req-only"],
            "activity:b": ["b"], "other:r": ["a"]}
        before = deepcopy((program, owners, selectable))
        drafts = project_narrative_retry_drafts(program, obligations=owners,
            target_obligation_ids=["activity"], candidate_ids_by_owner=selectable)
        rows = drafts[0]["claims"]
        self.assertEqual(rows[0]["evidence_bindings"], links[:2])
        self.assertEqual(rows[0]["omitted_evidence_binding_count"], 5)
        self.assertEqual(rows[1], {"location": "narrative_claims[1]", "subject": "みどり",
            "text": "追加説明。", "evidence_bindings": [], "omitted_evidence_binding_count": 1})
        self.assertEqual(drafts, project_narrative_retry_drafts(program, obligations=owners,
            target_obligation_ids=["activity"], candidate_ids_by_owner=selectable))
        rows[0]["evidence_bindings"][0]["evidence_text"] = "Edited draft"
        drafts[0]["scope_applicability_fields"].append("basis")
        self.assertEqual((program, owners, selectable), before)

    def test_projection_uses_obligation_order_and_omits_accepted_or_empty_drafts(self):
        owners = [_obligation(key, "narrative", key) for key in ("first", "second", "accepted", "missing")]
        owners.append(_obligation("numeric", "direct_value", "Size"))
        bindings = [{"obligation_id": key, "claims": [claim("Larch", "Unchanged.", "a", "Larch")]}
            for key in ("accepted", "second", "numeric", "first")]
        program = {"narrative_bindings": bindings}
        drafts = project_narrative_retry_drafts(program, obligations=owners,
            target_obligation_ids=["second", "numeric", "missing", "first"],
            candidate_ids_by_owner={row["obligation_id"]: ["a"] for row in owners})
        self.assertEqual([row["obligation_id"] for row in drafts], ["first", "second"])
        self.assertEqual(project_narrative_retry_drafts({}, obligations=owners,
            target_obligation_ids=["first"], candidate_ids_by_owner={}), [])

    def test_numeric_retry_does_not_add_narrative_draft_payload(self):
        llm = _StructuredQueueLLM(*[SemanticCalculationProgram(direct_bindings=[{
            "obligation_id": "size", "candidate_id": key}]) for key in ("invented", "cell")])
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(_case_state({
            "question": "Size?", "obligations": [_obligation("size", "direct_value", "Size")]},
            [_candidate("cell", 12)]))
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertNotIn("unvalidated_narrative_drafts", prompt_json(llm.prompts[1], "재시도 피드백(없으면 -):"))

    def test_targeted_retry_does_not_replay_or_edit_an_accepted_narrative_in_same_island(self):
        accepted = {"obligation_id": "reference", "claims": [
            claim("Cedar", "Cedar uses direct delivery.", "reference-note", "Cedar uses direct delivery.")]}
        initial = SemanticCalculationProgram.model_validate({"narrative_bindings": [
            accepted, *self.bad["narrative_bindings"]]})
        llm = _StructuredQueueLLM(initial, SemanticCalculationProgram.model_validate(self.good))
        owners = [_obligation("reference", "narrative", "Reference", coupling_key="shared-reading"),
            {**self.owners[0], "coupling_key": "shared-reading"}]
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(_case_state({
            "question": self.question, "obligations": owners},
            [source("reference-note", "Cedar uses direct delivery."), *self.catalog]))
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(json.dumps(compiled["semantic_program"]["narrative_bindings"][0], sort_keys=True),
            json.dumps(initial.model_dump()["narrative_bindings"][0], sort_keys=True))
        feedback = prompt_json(llm.prompts[1], "재시도 피드백(없으면 -):")
        self.assertEqual(feedback["repair_contract"]["target_obligation_ids"], ["activity"])
        self.assertEqual([row["obligation_id"] for row in feedback["unvalidated_narrative_drafts"]], ["activity"])
        self.assertNotIn("reference-note", json.dumps(feedback["unvalidated_narrative_drafts"]))

    def test_retry_can_remove_unsupported_optional_claim_or_abstain(self):
        # A draft is not a required answer or a claim-count lock. These are
        # authored responses testing repair mechanics, not model interpretation.
        shorter = {"narrative_bindings": [{"obligation_id": "activity", "claims": [
            self.bad["narrative_bindings"][0]["claims"][0]]}]}
        abstention = {"status": "incomplete", "missing_obligation_ids": ["activity"]}
        for replacement, expected in ((shorter, "ready"), (abstention, "incomplete")):
            with self.subTest(expected=expected):
                llm = _StructuredQueueLLM(SemanticCalculationProgram.model_validate(self.bad),
                    SemanticCalculationProgram.model_validate(replacement))
                compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(_case_state({
                    "question": "Describe activity.", "obligations": self.owners}, self.catalog))
                self.assertEqual(len(llm.prompts), 2)
                if expected == "ready":
                    self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
                else:
                    self.assertNotEqual(compiled["semantic_program_validation"]["status"], "ready")
                    self.assertIn("activity", compiled["semantic_program_validation"]["missing_obligation_ids"])
                self.assertEqual(len(compiled["semantic_program"]["narrative_bindings"]),
                    1 if expected == "ready" else 0)
                if expected == "ready":
                    self.assertEqual(len(compiled["semantic_program"]["narrative_bindings"][0]["claims"]), 1)


if __name__ == "__main__":
    unittest.main()
