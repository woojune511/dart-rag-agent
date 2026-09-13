"""Authored quote-construction controls, not model attribution/entailment scores."""

from copy import deepcopy
import json
import unittest

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program, validate_semantic_calculation_program,
)
from src.agent.financial_graph_calculation import _semantic_candidate_visibility
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.config.retrieval_policy import CALCULATION_PROMPT_POLICY
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM
from tests.test_narrative_claim_grounding import claim, source
from tests.test_narrative_retry_context import prompt_json


class NarrativeQuoteConstructionTests(unittest.TestCase):
    def setUp(self):
        self.query = "Describe the local operation."
        self.body = "We use local partners."
        self.catalog = [source("note", self.body, source_contexts=[{
            "context_id": "heading", "relation": "ancestor_heading",
            "source_text": "Birch", "source_span": [20, 25],
        }])]
        self.owners = [_obligation("activity", "narrative", self.query)]
        self.program = {"narrative_bindings": [{"obligation_id": "activity", "claims": [
            claim("Birch", "Uses local partners.", "note", self.body),
        ]}]}
        self.program["narrative_bindings"][0]["claims"][0]["evidence_bindings"].append({
            "candidate_id": "note", "context_id": "heading", "evidence_text": "Birch"})

    def validate(self, program=None, catalog=None, owners=None, permissions=None):
        program = self.program if program is None else program
        catalog = self.catalog if catalog is None else catalog
        owners = self.owners if owners is None else owners
        ids = [row["candidate_id"] for row in catalog]
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=ids,
            candidate_ids_by_owner={"activity": ids} if permissions is None else permissions)
        result = validate_semantic_calculation_program(program=program, candidate_catalog=catalog,
            obligations=owners, query=self.query, candidate_visibility=visibility,
            require_narrative_claims=True)
        return result, visibility

    def test_initial_narrative_and_mixed_prompts_carry_an_executable_separate_quote_example(self):
        for mixed in (False, True):
            with self.subTest(mixed=mixed):
                program, owners, catalog = deepcopy((self.program, self.owners, self.catalog))
                if mixed:
                    owners[0]["depends_on"] = ["size"]
                    owners.insert(0, _obligation("size", "direct_value", "Size"))
                    catalog.append(_candidate("cell", 12))
                    program["direct_bindings"] = [{"obligation_id": "size", "candidate_id": "cell"}]
                llm = _StructuredQueueLLM(SemanticCalculationProgram.model_validate(program))
                state = _case_state({"question": self.query, "obligations": owners}, catalog)
                before = deepcopy(state)
                compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
                self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
                self.assertEqual(len(llm.prompts), 1)
                self.assertEqual(llm.models, ["SemanticCalculationProgram"])
                prompt = llm.prompts[0].to_messages()[0].content
                marker = "분리 인용 claim 예시:\n"
                self.assertTrue(marker in prompt, "Missing separate-quote construction example")
                example = json.JSONDecoder().raw_decode(prompt.split(marker, 1)[1])[0]
                links = example["evidence_bindings"]
                self.assertEqual(len(links), 2)
                # Instruction IDs are not members of the live candidate payload.
                payload = prompt_json(llm.prompts[0], "Source bundles, candidate cohorts, and candidates_by_id:")
                self.assertTrue(all(link["candidate_id"] not in payload["candidates_by_id"] for link in links))
                unbound = {"narrative_bindings": [{"obligation_id": "activity", "claims": [example]}]}
                self.assertIn("unknown_narrative_candidate", {e["code"] for e in self.validate(unbound)[0]["errors"]})
                for link in links:
                    link["candidate_id"] = "note"
                    link["context_id"] = "heading" if link["context_id"] else ""
                rebound = {"narrative_bindings": [{"obligation_id": "activity", "claims": [example]}]}
                self.assertEqual(self.validate(rebound)[0]["status"], "ready")
                self.assertEqual(state, before)

    def test_exact_separate_quotes_preserve_context_body_spans_and_display(self):
        for subject, heading, relation in (
            ("Birch", "Birch", "ancestor_heading"),
            ("별빛팀", "[별빛팀]\n", "intermediate_heading"),
            ("みどり", "This passage describes みどり.", "preceding_block"),
        ):
            with self.subTest(subject=subject):
                program, catalog = deepcopy((self.program, self.catalog))
                row = program["narrative_bindings"][0]["claims"][0]
                row["subject"] = subject
                row["evidence_bindings"][1]["evidence_text"] = heading
                catalog[0]["source_contexts"][0].update(source_text=heading, relation=relation,
                    source_span=[20, 20 + len(heading)])
                before = deepcopy((program, catalog))
                validation, visibility = self.validate(program, catalog)
                self.assertEqual(validation["status"], "ready", validation["errors"])
                envelope = CompilationEnvelopeV2.create(program=program, validation=validation,
                    visibility=visibility, candidate_catalog=catalog, obligations=self.owners, query=self.query)
                execution = execute_semantic_calculation_program(program=program, candidate_catalog=catalog,
                    obligations=self.owners, query=self.query, compilation_envelope=envelope,
                    require_compilation_envelope=True)
                self.assertEqual(execution["status"], "ok")
                output = execution["outputs"][0]
                self.assertEqual(output["text"], f"{subject}: Uses local partners.")
                evidence = output["claim_readings"][0]["evidence"]
                self.assertEqual([e["evidence_text"] for e in evidence], [self.body, heading])
                self.assertEqual([e["source_span"] for e in evidence], [[0, len(self.body)], [0, len(heading)]])
                self.assertEqual(evidence[1]["container_source_span"], [20, 20 + len(heading)])
                self.assertEqual((program, catalog), before)

    def test_prefix_replacement_or_missing_subject_retry_keeps_cohort_and_accepted_bytes(self):
        accepted = SemanticCalculationProgram(direct_bindings=[{
            "obligation_id": "size", "candidate_id": "size-cell"}])
        for quote in (self.body, "Birch: " + self.body, self.body.replace("We", "Birch")):
            with self.subTest(quote=quote):
                bad = deepcopy(self.program)
                row = bad["narrative_bindings"][0]["claims"][0]
                row["evidence_bindings"] = [{"candidate_id": "note", "evidence_text": quote}]
                modeled = SemanticCalculationProgram.model_validate(bad)
                llm = _StructuredQueueLLM(accepted, modeled, SemanticCalculationProgram.model_validate(self.program))
                state = _case_state({"question": self.query, "obligations": [
                    _obligation("size", "direct_value", "Size"), *self.owners]},
                    [_candidate("size-cell", 12), *self.catalog])
                compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
                self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
                self.assertEqual(len(llm.prompts), 3)
                self.assertEqual(json.dumps(compiled["semantic_program"]["direct_bindings"], sort_keys=True),
                    json.dumps(accepted.model_dump()["direct_bindings"], sort_keys=True))
                feedback = prompt_json(llm.prompts[2], "재시도 피드백(없으면 -):")
                contract = feedback["repair_contract"]
                self.assertEqual(contract["target_obligation_ids"], ["activity"])
                self.assertIn("separate evidence_bindings", contract["narrative_claim_invariant"])
                self.assertIn("Do not insert", contract["narrative_claim_invariant"])
                self.assertEqual(contract["narrative_claim_invariant"],
                    CALCULATION_PROMPT_POLICY["semantic_program_narrative_repair_invariant"])
                drafts = feedback["unvalidated_narrative_drafts"]
                self.assertEqual(drafts[0]["claims"][0]["evidence_bindings"],
                    modeled.model_dump()["narrative_bindings"][0]["claims"][0]["evidence_bindings"])
                self.assertNotIn("size-cell", json.dumps(drafts))
                for error in feedback["validation_errors"]:
                    self.assertEqual(error["location"], "narrative_claims[0]")
                    self.assertEqual(error["repair_action"], "repair_program")
                    if error["code"] in {"ungrounded_narrative_subject", "invalid_narrative_claim_quote"}:
                        self.assertIn("separate", error["detail"])
                marker = "Source bundles, candidate cohorts, and candidates_by_id:"
                self.assertEqual(prompt_json(llm.prompts[1], marker), prompt_json(llm.prompts[2], marker))

    def test_subject_evidence_may_be_another_visible_candidate_without_claiming_a_requirement(self):
        catalog = [source("note", self.body), source("intro", "This passage describes Birch.")]
        program = deepcopy(self.program)
        links = program["narrative_bindings"][0]["claims"][0]["evidence_bindings"]
        links[0]["source_requirement_id"] = "activity:fact"
        links[1] = {"candidate_id": "intro", "evidence_text": catalog[1]["source_text"]}
        owners = [_obligation("activity", "narrative", self.query, evidence_requirements=[{
            "requirement_id": "activity:fact", "label": "Operation", "required": True}])]
        permissions = {"activity": ["note", "intro"], "activity:fact": ["note"]}
        self.assertEqual(self.validate(program, catalog, owners, permissions)[0]["status"], "ready")
        links[1]["source_requirement_id"] = "activity:fact"
        invalid = self.validate(program, catalog, owners, permissions)[0]
        self.assertIn("candidate_not_exposed_to_compiler", {e["code"] for e in invalid["errors"]})

    def test_separate_subject_quote_cannot_borrow_unattached_or_foreign_owner_source(self):
        catalog = [*self.catalog, source("foreign", "Birch", source_contexts=[{
            "context_id": "foreign-heading", "source_text": "Birch", "relation": "ancestor_heading"}])]
        for change, expected in (
            ({"context_id": "foreign-heading"}, "invalid_narrative_claim_context"),
            ({"candidate_id": "foreign", "context_id": ""}, "candidate_not_exposed_to_compiler"),
            ({"candidate_id": "invented", "context_id": ""}, "unknown_narrative_candidate"),
            ({"context_id": "", "evidence_text": "Birch " + self.body}, "invalid_narrative_claim_quote"),
        ):
            with self.subTest(change=change):
                program = deepcopy(self.program)
                program["narrative_bindings"][0]["claims"][0]["evidence_bindings"][1].update(change)
                validation = self.validate(program, catalog, permissions={"activity": ["note"]})[0]
                self.assertIn(expected, {e["code"] for e in validation["errors"]})
                self.assertNotEqual(validation["status"], "ready")

    def test_another_claims_heading_does_not_implicitly_ground_this_claim(self):
        program = deepcopy(self.program)
        claims = program["narrative_bindings"][0]["claims"]
        claims.append(deepcopy(claims[0]))
        claims[1]["evidence_bindings"].pop()
        validation = self.validate(program)[0]
        error = next(e for e in validation["errors"] if e["code"] == "ungrounded_narrative_subject")
        self.assertEqual(error["location"], "narrative_claims[1]")

    def test_exact_subject_and_fact_quotes_are_not_a_semantic_relationship_oracle(self):
        # Deliberately unfaithful controls: exact bindings cannot prove attribution
        # or negation. No post-hoc rewrite, keyword classifier or semantic PASS.
        for text in ("Birch never uses local partners.", "Cedar uses local partners."):
            program = deepcopy(self.program)
            program["narrative_bindings"][0]["claims"][0]["text"] = text
            validation = self.validate(program)[0]
            self.assertEqual(validation["status"], "ready")
            self.assertEqual(validation["valid_narrative_bindings"][0]["claims"][0]["text"], text)


if __name__ == "__main__":
    unittest.main()
