"""Explicit evidence insufficiency is a terminal decision, not a format error."""

from copy import deepcopy
import json
import unittest

from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_graph_calculation import _semantic_retry_target_ids
from src.agent.financial_runtime_contracts import EvidenceBundleConstraintV1, EvidenceBundleOptionV1
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM


def compile_programs(obligations, *programs):
    catalog = [_candidate("source-value", 10)]
    state = _case_state({"question": "Read the requested quantity.", "obligations": obligations}, catalog)
    before = deepcopy(state)
    llm = _StructuredQueueLLM(*[SemanticCalculationProgram.model_validate(item) for item in programs])
    compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
    assert state == before
    return compiled, llm


class SemanticAbstentionRetryTests(unittest.TestCase):
    def test_schema_failure_is_not_an_explicit_abstention(self):
        class SchemaFailureQueue(_StructuredQueueLLM):
            def invoke(self, prompt):
                if not self.prompts:
                    self.prompts.append(prompt)
                    raise ValueError("invalid structured output")
                return super().invoke(prompt)

        repair = SemanticCalculationProgram.model_validate({"status": "incomplete", "missing_obligation_ids": ["value"]})
        llm = SchemaFailureQueue(repair)
        state = _case_state({"question": "Read the quantity.",
            "obligations": [_obligation("value", "direct_value", "quantity")]}, [_candidate("source-value", 10)])
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(compiled["semantic_program_validation"]["errors"], [])

    def test_abstaining_atomic_row_is_not_partially_retried(self):
        owners = ["withheld", "peer", "unrelated"]
        constraint = EvidenceBundleConstraintV1.create(owner_ids=owners[:2], options=[
            EvidenceBundleOptionV1.create(physical_table_id="table", physical_row_id="row",
                candidate_ids_by_owner={owner: [owner + "-cell"] for owner in owners[:2]})])
        targets = _semantic_retry_target_ids(
            program={"status": "incomplete", "missing_obligation_ids": ["withheld"]},
            validation={"missing_obligation_ids": owners,
                "errors": [{"obligation_id": owner} for owner in owners[1:]]},
            obligations=[_obligation(owner, "direct_value", "quantity") for owner in owners],
            invocation_failed=False, bundle_constraints=[constraint])
        self.assertEqual(targets, ["unrelated"])

    def test_explicit_missing_or_ambiguous_is_not_retried(self):
        for status, field in (("incomplete", "missing_obligation_ids"), ("ambiguous", "ambiguous_obligation_ids")):
            with self.subTest(status=status):
                first = {"status": status, field: ["value"], "rationale": "The requested source period is unavailable."}
                wrong_retry = {"status": "ready", "direct_bindings": [{"obligation_id": "value", "candidate_id": "source-value"}]}
                compiled, llm = compile_programs([_obligation("value", "direct_value", "quantity")], first, wrong_retry)
                self.assertEqual(len(llm.prompts), 1)
                self.assertEqual(compiled["semantic_program_retry_count"], 0)
                self.assertEqual(compiled["semantic_program"][field], ["value"])
                self.assertEqual(compiled["semantic_program"]["rationale"], first["rationale"])
                self.assertEqual(compiled["semantic_program_validation"]["errors"], [])
                self.assertEqual(compiled["semantic_program_validation"]["selected_candidate_ids"], [])

    def test_undeclared_missing_output_still_retries(self):
        for first in ({"status": "incomplete"}, {"status": "ready", "missing_obligation_ids": ["value"]}):
            with self.subTest(first=first):
                repair = {"status": "ready", "direct_bindings": [{"obligation_id": "value", "candidate_id": "source-value"}]}
                compiled, llm = compile_programs([_obligation("value", "direct_value", "quantity")], first, repair)
                self.assertEqual(len(llm.prompts), 2)
                self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")

    def test_abstention_with_conflicting_output_still_repairs(self):
        first = {"status": "incomplete", "missing_obligation_ids": ["value"],
            "direct_bindings": [{"obligation_id": "value", "candidate_id": "hidden"}]}
        repair = {"status": "incomplete", "missing_obligation_ids": ["value"]}
        compiled, llm = compile_programs([_obligation("value", "direct_value", "quantity")], first, repair)
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(compiled["semantic_program_validation"]["errors"], [])
        self.assertEqual(compiled["semantic_program_validation"]["selected_candidate_ids"], [])

    def test_retry_of_same_island_peer_preserves_abstention(self):
        obligations = [_obligation(owner, "direct_value", "quantity", coupling_key="shared") for owner in ("withheld", "repair")]
        for field in ("missing_obligation_ids", "ambiguous_obligation_ids"):
            with self.subTest(field=field):
                first = {"status": "incomplete", field: ["withheld"],
                    "direct_bindings": [{"obligation_id": "repair", "candidate_id": "hidden"}]}
                retry = {"status": "ready", "direct_bindings": [
                    {"obligation_id": owner, "candidate_id": "source-value"} for owner in ("withheld", "repair")]}
                compiled, llm = compile_programs(obligations, first, retry)
                self.assertEqual(len(llm.prompts), 2)
                program = compiled["semantic_program"]
                self.assertEqual(program[field], ["withheld"])
                self.assertEqual([row["obligation_id"] for row in program["direct_bindings"]], ["repair"])
                attempts = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]["attempts"]
                self.assertEqual(attempts[1]["target_obligation_ids"], ["repair"])

    def test_independent_accepted_output_bytes_are_preserved(self):
        obligations = [_obligation(owner, "direct_value", "quantity") for owner in ("accepted", "withheld")]
        accepted = {"status": "ready", "direct_bindings": [{"obligation_id": "accepted", "candidate_id": "source-value"}]}
        compiled, llm = compile_programs(obligations, accepted,
            {"status": "incomplete", "missing_obligation_ids": ["withheld"]})
        self.assertEqual(len(llm.prompts), 2)
        expected = SemanticCalculationProgram.model_validate(accepted).model_dump()["direct_bindings"]
        self.assertEqual(json.dumps(compiled["semantic_program"]["direct_bindings"], sort_keys=True), json.dumps(expected, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
