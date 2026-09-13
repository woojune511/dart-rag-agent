"""Anonymous characterization of binding failures, not model accuracy or fixes.

Passing negative controls document the current semantic boundary; they must not
be interpreted as approval to inherit a subject or silently drop required text.
"""

from copy import deepcopy
import json
import unittest

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program, validate_semantic_calculation_program,
)
from src.agent.financial_graph_calculation import _semantic_candidate_visibility
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM
from tests.test_narrative_claim_grounding import claim, source
from tests.test_narrative_retry_context import prompt_json


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def list_fixture(subject="Pine Workshop"):
    parts = (f"{subject} arranges field visits.", "-Purpose: inspect tools.", "-Schedule: weekly.")
    body = "".join(parts)
    program = {"narrative_bindings": [{"obligation_id": "activity", "claims": [
        claim(subject, "Arranges weekly visits to inspect tools.", "note", "\n".join(parts))]}]}
    fixed = deepcopy(program)
    fixed["narrative_bindings"][0]["claims"][0]["evidence_bindings"][0]["evidence_text"] = body
    return [source("note", body)], program, fixed


def paragraph_fixture(subject="Pine Workshop"):
    sentences = (f"{subject} schedules inspections.", "It checks tools.",
        "It records findings.", "It stores samples.")
    statements = ("Schedules inspections.", "Checks tools.", "Records findings.", "Stores samples.")
    claims = [claim(subject, statement, "note", sentence)
        for statement, sentence in zip(statements, sentences)]
    # Earlier claims explicitly share source support; the last one omits it.
    support = {"candidate_id": "note", "evidence_text": sentences[0]}
    for row in claims[1:-1]:
        row["evidence_bindings"].append(deepcopy(support))
    program = {"narrative_bindings": [{"obligation_id": "activity", "claims": claims}]}
    fixed = deepcopy(program)
    fixed["narrative_bindings"][0]["claims"][-1]["evidence_bindings"].append(support)
    return [source("note", " ".join(sentences))], program, fixed


class NarrativeBindingBoundaryTests(unittest.TestCase):
    query = "Describe the inspection schedule, tool checks, finding records, and sample storage."

    def validate(self, catalog, program):
        owners = [_obligation("activity", "narrative", self.query)]
        ids = [c["candidate_id"] for c in catalog]
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=ids,
            candidate_ids_by_owner={"activity": ids})
        validation = validate_semantic_calculation_program(program=program, candidate_catalog=catalog,
            obligations=owners, query=self.query, candidate_visibility=visibility, require_narrative_claims=True)
        envelope = CompilationEnvelopeV2.create(program=program, validation=validation, visibility=visibility,
            candidate_catalog=catalog, obligations=owners, query=self.query)
        execution = execute_semantic_calculation_program(program=program, candidate_catalog=catalog,
            obligations=owners, query=self.query, compilation_envelope=envelope, require_compilation_envelope=True)
        return validation, execution

    def compile_retry(self, catalog, bad, replacement):
        accepted = SemanticCalculationProgram(direct_bindings=[{
            "obligation_id": "size", "candidate_id": "size-cell"}])
        llm = _StructuredQueueLLM(accepted, SemanticCalculationProgram.model_validate(bad),
            SemanticCalculationProgram.model_validate(replacement))
        state = _case_state({"question": self.query, "obligations": [
            _obligation("size", "direct_value", "Size"), _obligation("activity", "narrative", self.query)]},
            [_candidate("size-cell", 12), *catalog])
        state["include_debug_bundle"] = True
        before = deepcopy(state)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(state, before)
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(canonical(compiled["semantic_program"]["direct_bindings"]),
            canonical(accepted.model_dump()["direct_bindings"]))
        marker = "Source bundles, candidate cohorts, and candidates_by_id:"
        self.assertEqual(prompt_json(llm.prompts[1], marker), prompt_json(llm.prompts[2], marker))
        feedback = prompt_json(llm.prompts[2], "재시도 피드백(없으면 -):")
        self.assertEqual(feedback["repair_contract"]["target_obligation_ids"], ["activity"])
        self.assertNotIn("size-cell", canonical(feedback["unvalidated_narrative_drafts"]).decode("utf-8"))
        return compiled, llm, feedback

    def test_inserted_list_newlines_fail_even_when_all_words_are_source_copied(self):
        for subject in ("Pine Workshop", "물결연구소", "みなと工房"):
            with self.subTest(subject=subject):
                catalog, bad, fixed = list_fixture(subject)
                original = deepcopy((catalog, bad))
                fingerprint = semantic_candidate_catalog_fingerprint(catalog)
                validation, execution = self.validate(catalog, bad)
                error = next(e for e in validation["errors"] if e["code"] == "invalid_narrative_claim_quote")
                self.assertEqual(error["location"], "narrative_claims[0]")
                self.assertEqual(error["candidate_id"], "note")
                self.assertEqual(error["repair_action"], "repair_program")
                self.assertFalse(execution["outputs"])
                self.assertEqual(self.validate(catalog, fixed)[1]["status"], "ok")
                self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)
                self.assertEqual((catalog, bad), original)

    def test_original_whitespace_is_authority_not_an_automatic_cleanup_rule(self):
        catalog, bad, _ = list_fixture()
        source_quote = bad["narrative_bindings"][0]["claims"][0]["evidence_bindings"][0]["evidence_text"]
        catalog[0].update(source_text=source_quote, source_bundle_text=source_quote)
        self.assertEqual(self.validate(catalog, bad)[0]["status"], "ready")
        changed = deepcopy(bad)
        changed["narrative_bindings"][0]["claims"][0]["evidence_bindings"][0]["evidence_text"] = source_quote.replace("\n", "")
        codes = {e["code"] for e in self.validate(catalog, changed)[0]["errors"]}
        self.assertIn("invalid_narrative_claim_quote", codes)

    def test_last_elliptical_claim_rejects_the_entire_narrative_binding(self):
        catalog, bad, _ = paragraph_fixture()
        validation, execution = self.validate(catalog, bad)
        errors = validation["errors"]
        self.assertEqual([(e["code"], e["location"]) for e in errors],
            [("ungrounded_narrative_subject", "narrative_claims[3]")])
        self.assertEqual(validation["valid_narrative_bindings"], [])
        self.assertEqual(execution["outputs"], [])
        self.assertEqual(execution["missing_obligation_ids"], ["activity"])
        # The correct earlier claims are not silently published as a complete answer.
        self.assertEqual(execution["execution_errors"], [])

    def test_explicit_reuse_of_subject_support_preserves_all_fact_quotes(self):
        for subject in ("Pine Workshop", "물결연구소"):
            with self.subTest(subject=subject):
                catalog, bad, fixed = paragraph_fixture(subject)
                before = deepcopy((catalog, bad, fixed))
                validation, execution = self.validate(catalog, fixed)
                self.assertEqual(validation["status"], "ready", validation["errors"])
                self.assertEqual(execution["status"], "ok")
                readings = execution["outputs"][0]["claim_readings"]
                self.assertEqual(len(readings), 4)
                for old, reading in zip(bad["narrative_bindings"][0]["claims"], readings):
                    self.assertEqual(reading["evidence"][0]["evidence_text"], old["evidence_bindings"][0]["evidence_text"])
                self.assertEqual(execution["selected_candidate_ids"], ["note"])
                self.assertEqual((catalog, bad, fixed), before)

    def test_unchanged_retry_retains_the_failure_without_losing_another_island(self):
        for fixture, code in ((list_fixture, "invalid_narrative_claim_quote"),
                              (paragraph_fixture, "ungrounded_narrative_subject")):
            with self.subTest(fixture=fixture.__name__):
                catalog, bad, _ = fixture()
                compiled, _, feedback = self.compile_retry(catalog, bad, deepcopy(bad))
                self.assertIn("activity", compiled["semantic_program_validation"]["missing_obligation_ids"])
                self.assertEqual(compiled["semantic_program"]["narrative_bindings"], [])
                attempts = compiled["compiler_attempts"]
                self.assertEqual(len(attempts), 3)
                for attempt in attempts[1:]:
                    self.assertIn(code, {e["code"] for e in attempt["validation_errors"]})
                self.assertEqual(len(feedback["unvalidated_narrative_drafts"][0]["claims"]),
                    len(bad["narrative_bindings"][0]["claims"]))

    def test_authored_binding_repair_succeeds_in_existing_single_retry(self):
        for fixture in (list_fixture, paragraph_fixture):
            with self.subTest(fixture=fixture.__name__):
                catalog, bad, fixed = fixture()
                compiled, _, _ = self.compile_retry(catalog, bad, fixed)
                self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
                self.assertEqual(canonical(compiled["semantic_program"]["narrative_bindings"]),
                    canonical(SemanticCalculationProgram.model_validate(fixed).model_dump()["narrative_bindings"]))

    def test_literal_subject_support_does_not_prove_pronoun_attachment(self):
        # Contrasting subject assignments both satisfy today's lexical checks.
        # This test does not claim a semantic oracle for the pronoun's referent.
        body = "Pine Workshop files reports. Quartz Studio tests tools. It stores samples."
        catalog = [source("note", body)]
        for subject, support in (("Pine Workshop", "Pine Workshop files reports."),
                                 ("Quartz Studio", "Quartz Studio tests tools.")):
            with self.subTest(subject=subject):
                row = claim(subject, "Stores samples.", "note", "It stores samples.")
                row["evidence_bindings"].append({"candidate_id": "note", "evidence_text": support})
                program = {"narrative_bindings": [{"obligation_id": "activity", "claims": [row]}]}
                self.assertEqual(self.validate(catalog, program)[0]["status"], "ready")
        # This is deliberately not an entailment pass or an inheritance mechanism.

    def test_dropping_the_invalid_claim_cannot_certify_requested_coverage(self):
        catalog, bad, _ = paragraph_fixture()
        shortened = deepcopy(bad)
        shortened["narrative_bindings"][0]["claims"].pop()
        compiled, _, _ = self.compile_retry(catalog, bad, shortened)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        text = compiled["semantic_program"]["narrative_bindings"][0]["text"]
        self.assertNotIn("samples", text)
        self.assertIn("sample storage", self.query)
        # Structural success with an omitted requested detail is a negative control,
        # not a reason to delete failed claims automatically or lower a coverage gate.


if __name__ == "__main__":
    unittest.main()
