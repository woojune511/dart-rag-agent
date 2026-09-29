"""Targeted repair can read accepted dependencies without reopening their owners."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tests.request_unit_fixture_support import bind_fixture_request

from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_langchain_loaders import chat_prompt_template_from_template
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state, _materialize_catalog
from tests.semantic_program_test_support import (
    _binding, _obligation, _source_display_program_fixture, _StructuredQueueLLM,
    execute_semantic_calculation_program,
)


def _reviewed_case():
    path = Path(__file__).parent / "fixtures" / "reviewed_runtime_replay_corpus_v2.json"
    case = bind_fixture_request(json.loads(path.read_text(encoding="utf-8"))["cases"][0])
    case["candidate_catalog"], _ = _materialize_catalog(case["candidate_catalog"])
    return case


def _compile(case, first, retry):
    from tests.source_interpretation_fixture_support import authored_source_program
    captured = []

    def prompt_factory(template):
        prompt = chat_prompt_template_from_template(template)

        def invoke(values):
            captured.append(deepcopy(values))
            return prompt.invoke(values)

        return SimpleNamespace(invoke=invoke)

    llm = _StructuredQueueLLM(*[
        SemanticCalculationProgram.model_validate(authored_source_program(program, case["obligations"], case["candidate_catalog"], case["question"]))
        for program in (first, retry)
    ])
    state = _case_state(case, case["candidate_catalog"])
    before = deepcopy(state)
    with patch("src.agent.financial_graph_calculation.chat_prompt_template_from_template", side_effect=prompt_factory):
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
    assert state == before, "compilation must not mutate its inputs"
    # Tests compare canonical provenance; provider prompts retain short refs.
    for values, model in zip(captured, llm.model_instances):
        for key in ("candidate_catalog", "retry_feedback"):
            if values.get(key) and values[key] != "-":
                values[key] = json.dumps(model.__compiler_references__.project(json.loads(values[key]), reverse=True))
    return compiled, captured


def _execute(case, compiled):
    return execute_semantic_calculation_program(
        program=compiled["semantic_program"], obligations=case["obligations"],
        candidate_catalog=case["candidate_catalog"], query=case["question"],
        compilation_envelope=compiled["semantic_compilation_envelope"], require_compilation_envelope=True,
    )


def _dependent_expression(owner, source, formula="X + X"):
    return {
        "obligation_id": owner, "formula": formula,
        "variable_bindings": [_binding("X", source)],
        "source_display_candidate_id": None,
        "source_display_reason": "Only the dependency reports a source display.",
    }


class SemanticRetryDependencyTests(unittest.TestCase):
    def test_reviewed_period_pair_survives_targeted_retry_as_read_only_inputs(self):
        case = _reviewed_case()
        first = deepcopy(case["program"])
        first["expressions"][0]["formula"] = "UNBOUND"
        retry = {"status": "ready", "expressions": deepcopy(case["program"]["expressions"])}
        compiled, prompts = _compile(case, first, retry)
        self.assertEqual(len(prompts), 2)
        feedback = json.loads(prompts[1]["retry_feedback"])
        inputs = feedback["read_only_dependency_outputs"]
        self.assertEqual(list(inputs), ["nim_2023", "nim_2022"])
        self.assertEqual(inputs["nim_2023"]["normalized_value"], 1.83)
        self.assertEqual(inputs["nim_2022"]["normalized_value"], 1.73)
        self.assertEqual(inputs["nim_2022"]["normalized_unit"], "PERCENT")
        self.assertEqual(inputs["nim_2022"]["scope"]["period"], "2022")
        self.assertEqual(inputs["nim_2022"]["candidate_ids"], ["reviewed_kbf_nim_2022"])
        self.assertTrue(inputs["nim_2022"]["source_anchors"])
        self.assertEqual(feedback["declared_obligation_ids"], ["nim_2023", "nim_2022", "nim_change"])
        self.assertEqual(feedback["repair_contract"]["target_obligation_ids"], ["nim_change"])
        self.assertEqual(feedback["repair_contract"]["dependency_ids_by_obligation"], {"nim_change": ["nim_2023", "nim_2022"]})
        self.assertEqual([row["obligation_id"] for row in json.loads(prompts[1]["obligations"])], ["nim_change"])
        payload = json.loads(prompts[1]["candidate_catalog"])
        self.assertNotIn("reviewed_kbf_nim_2022", payload["candidates_by_id"])
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        execution = _execute(case, compiled)
        self.assertEqual(execution["status"], "ok")
        self.assertEqual(execution["outputs_by_obligation"]["nim_change"]["rendered_value"], "0.10%p")
        attempts = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]["attempts"]
        self.assertEqual(attempts[0]["read_only_dependency_ids"], [])
        self.assertEqual(attempts[1]["read_only_dependency_ids"], list(inputs))

    def test_retry_cannot_overwrite_accepted_dependency_bindings(self):
        case = _reviewed_case()
        first = deepcopy(case["program"])
        first["expressions"][0]["formula"] = "UNBOUND"
        repaired = {"status": "ready", "expressions": deepcopy(case["program"]["expressions"])}
        clean, clean_prompts = _compile(case, first, repaired)
        malicious = deepcopy(repaired)
        malicious["direct_bindings"] = [{"obligation_id": "nim_2022", "candidate_id": "reviewed_kbf_nim_2023"}]
        malicious["missing_obligation_ids"] = ["nim_2023", "nim_2022"]
        compiled, prompts = _compile(case, first, malicious)
        self.assertIn("read_only_dependency_outputs", json.loads(prompts[1]["retry_feedback"]))
        self.assertEqual(prompts[1]["retry_feedback"].encode(), clean_prompts[1]["retry_feedback"].encode())
        # Extra output keys are rejected by the new schema; accepted owners
        # still survive, but an invalid retry cannot claim the target succeeded.
        self.assertEqual(compiled["semantic_program_validation"]["status"], "partial")
        self.assertEqual(
            json.dumps(compiled["semantic_program"]["direct_bindings"], ensure_ascii=False).encode(),
            json.dumps(clean["semantic_program"]["direct_bindings"], ensure_ascii=False).encode(),
        )
        self.assertEqual(_execute(case, compiled)["outputs_by_obligation"]["nim_2022"]["normalized_value"], 1.73)

    def test_dependency_provenance_does_not_grant_candidate_selection_authority(self):
        case = _reviewed_case()
        first = deepcopy(case["program"])
        first["expressions"][0]["formula"] = "UNBOUND"
        for hidden in ("reviewed_kbf_nim_2022", "invented_candidate"):
            with self.subTest(hidden=hidden):
                retry = {"status": "ready", "expressions": deepcopy(case["program"]["expressions"])}
                retry["expressions"][0]["variable_bindings"][1]["source_id"] = hidden
                compiled, prompts = _compile(case, first, retry)
                self.assertIn("nim_2022", json.loads(prompts[1]["retry_feedback"])["read_only_dependency_outputs"])
                self.assertNotEqual(compiled["semantic_program_validation"]["status"], "ready")
                self.assertNotIn("nim_change", _execute(case, compiled)["outputs_by_obligation"])
                history = compiled["resolved_calculation_trace"]["calculation_plan"]["program_validation_history"]
                expected = "candidate_not_authorized_for_output_input" if hidden.startswith("reviewed_") else "unknown_compiler_reference"
                self.assertIn(expected, {error["code"] for error in history[1]["errors"]})

    def test_failed_dependency_stays_editable_not_read_only(self):
        case = _reviewed_case()
        first = deepcopy(case["program"])
        first["direct_bindings"][1]["candidate_id"] = "invented_candidate"
        # This tests an unknown source_ref, not a legacy axis ID copied from a
        # different cell. V2 has no model-written axes; foreign-axis migration
        # is independently rejected in test_numeric_compiler_grounding.
        first["direct_bindings"][1].pop("source_interpretation", None)
        retry = {
            "status": "ready", "direct_bindings": [deepcopy(case["program"]["direct_bindings"][1])],
            "expressions": deepcopy(case["program"]["expressions"]),
        }
        compiled, prompts = _compile(case, first, retry)
        feedback = json.loads(prompts[1]["retry_feedback"])
        self.assertEqual(list(feedback["read_only_dependency_outputs"]), ["nim_2023"])
        self.assertEqual(feedback["repair_contract"]["target_obligation_ids"], ["nim_2022", "nim_change"])
        self.assertEqual(_execute(case, compiled)["status"], "ok")

    def _derived_chain(self):
        fixture = _source_display_program_fixture()
        fixture["question"] = fixture.pop("query")
        fixture["obligations"].extend([
            _obligation("middle", "derived_value", "twice calculated change", display_unit="%", depends_on=["ob_change"]),
            _obligation("last", "derived_value", "twice the intermediate result", display_unit="%", depends_on=["middle"]),
        ])
        fixture["program"]["expressions"].extend([
            _dependent_expression("middle", "ob_change"),
            _dependent_expression("last", "middle", "UNBOUND"),
        ])
        return fixture

    def test_transitive_dependency_uses_calculation_not_source_display(self):
        case = self._derived_chain()
        retry = {"status": "ready", "expressions": [_dependent_expression("last", "middle")]}
        compiled, prompts = _compile(case, case["program"], retry)
        inputs = json.loads(prompts[1]["retry_feedback"])["read_only_dependency_outputs"]
        self.assertEqual(list(inputs), ["middle"])
        self.assertEqual(inputs["middle"]["normalized_value"], 20)
        self.assertEqual(inputs["middle"]["normalized_unit"], "PERCENT")
        self.assertIn("cand-opening", inputs["middle"]["candidate_ids"])
        execution = _execute(case, compiled)
        self.assertEqual(execution["status"], "ok")
        self.assertEqual(execution["outputs_by_obligation"]["ob_change"]["display_value"], 10.2)
        self.assertEqual(execution["outputs_by_obligation"]["last"]["normalized_value"], 40)
        last = execution["outputs_by_obligation"]["last"]
        self.assertEqual(last["input_rows"][0]["source_id"], "middle")
        self.assertEqual(last["input_rows"][0]["normalized_value"], 20)
        self.assertEqual(last["calculated_provenance"]["input_candidate_ids"], ["cand-opening", "cand-closing"])
        self.assertNotIn("cand-stated", last["calculated_provenance"]["source_row_ids"])

    def test_structurally_valid_but_unexecutable_dependency_is_not_exposed(self):
        case = self._derived_chain()
        case["program"]["expressions"][0]["formula"] = "OPEN / (CLOSE - CLOSE) * 100"
        retry = {"status": "ready", "expressions": [_dependent_expression("last", "middle")]}
        compiled, prompts = _compile(case, case["program"], retry)
        feedback = json.loads(prompts[1]["retry_feedback"])
        self.assertEqual(feedback["read_only_dependency_outputs"], {})
        self.assertNotIn("middle", feedback["declared_obligation_ids"])
        self.assertNotIn("last", _execute(case, compiled)["outputs_by_obligation"])


if __name__ == "__main__":
    unittest.main()
