"""Authored request/constant witnesses, not sampled-model semantic accuracy."""
from copy import deepcopy
import json
import socket
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from tests.mixed_numeric_source_test_support import (
    authored_program, canonical, capture_initial, compile_case, execute,
    load_criteria, load_sources, materialize,
)
from tests.semantic_program_test_support import execute_compiled_fixture


def witness(request="Double the calculated rate.", quote="Double", value=2):
    # Explicit successor witness; the previous source/criteria files stay unchanged.
    source = deepcopy(load_sources()[3])
    source["question"] = (
        "Report Lyra's source-stated percentage change alongside the rate calculated "
        "from the table's previous and current quantities. " + request)
    source["obligations"][1]["request_unit_ids"] = ["request_002"]
    case = materialize(source)
    program = authored_program(case, load_criteria()[case["case_id"]])
    expression = program["expressions"][-1]
    variable = expression["variable_bindings"][0]["variable"]
    expression["formula"] = f"{variable} * {value!r}"
    expression["constants"] = [{"value": value, "origin": "query",
        "request_unit_id": "request_002", "source_text": quote,
        "interpretation": f"The requested transformation uses the scalar {value!r}."}]
    return case, program


def validate(case, program):
    return validate_semantic_calculation_program(program=program, obligations=case["obligations"],
        candidate_catalog=case["candidate_catalog"], query=case["question"])


class RequestFormulaConstantTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.object(socket.socket, "connect", side_effect=AssertionError("provider forbidden")).start()
        patch.object(socket.socket, "connect_ex", side_effect=AssertionError("provider forbidden")).start()

    def test_natural_language_constants_execute_with_exact_owned_request_provenance(self):
        cases = [("Double the calculated rate.", "Double", 2),
                 ("계산한 비율의 세 배를 표시하세요.", "세 배", 3),
                 ("Return half the calculated rate.", "half", 0.5),
                 ("Multiply the calculated rate by negative two.", "negative two", -2),
                 ("Multiply the calculated rate by 2.5.", "2.5", 2.5)]
        for request, quote, multiplier in cases:
            with self.subTest(request=request):
                case, program = witness(request, quote, multiplier)
                before = deepcopy((case, program))
                validation = validate(case, program)
                self.assertEqual(validation["status"], "ready", validation["errors"])
                compiled, queue, _ = compile_case(case, [program])
                result = execute(case, compiled)
                self.assertEqual(result["status"], "ok", result)
                output = result["outputs_by_obligation"]["double"]
                self.assertEqual(output["calculated_value"], 20 * multiplier)
                self.assertEqual(result["outputs_by_obligation"]["growth"]["answer_slot"]["normalized_value"], 21)
                proof = output["constant_resolutions"][0]
                self.assertEqual(proof["value"], multiplier)
                self.assertEqual(proof["source_text"], request)
                self.assertEqual(proof["request_unit_id"], "request_002")
                start, end = proof["request_span"]
                self.assertEqual(case["question"][start:end], request)
                self.assertEqual(proof["validation_scope"], "request_binding_not_semantic_equivalence")
                self.assertEqual((case, program), before)
                self.assertEqual(len(queue.wires), 1)
                self.assertEqual(compiled["semantic_program_retry_count"], 0)

    def test_missing_declaration_is_not_inferred_from_request_or_formula(self):
        case, program = witness()
        program["expressions"][-1]["constants"] = []
        before = deepcopy(program)
        validation = validate(case, program)
        errors = [e for e in validation["errors"] if e["obligation_id"] == "double"]
        self.assertEqual([e["code"] for e in errors], ["undeclared_formula_constant"])
        self.assertEqual(errors[0]["location"], "expression.constants")
        self.assertEqual(errors[0]["repair_action"], "repair_program")
        self.assertEqual(errors[0]["candidate_id"], "")
        self.assertEqual(program, before)

    def test_unowned_hidden_inexact_and_ambiguous_request_quotes_fail_closed(self):
        mutations = [({"request_unit_id": "request_001", "source_text": "Report"}, "constant_request_not_owned"),
                     ({"request_unit_id": "request_999"}, "constant_request_not_owned"),
                     ({"request_unit_id": None}, "constant_request_not_owned"),
                     ({"source_text": "double"}, "constant_request_quote_invalid"),
                     ({"source_text": ""}, "constant_request_quote_invalid"),
                     ({"source_text": "21%"}, "constant_request_quote_invalid"),
                     ({"interpretation": " "}, "constant_interpretation_missing")]
        for changed, code in mutations:
            with self.subTest(changed=changed):
                case, program = witness()
                program["expressions"][-1]["constants"][0].update(changed)
                errors = validate(case, program)["errors"]
                self.assertIn(code, {e["code"] for e in errors})
                self.assertTrue(all(e["repair_action"] == "repair_program" and not e["candidate_id"] for e in errors))
        case, program = witness("Double or Double the calculated rate.")
        self.assertIn("constant_request_quote_invalid", {e["code"] for e in validate(case, program)["errors"]})

    def test_declarations_are_finite_exact_unique_and_used(self):
        case, good = witness()
        declaration = good["expressions"][-1]["constants"][0]
        for declarations, code in (
            ([{**declaration, "value": bad}], "invalid_formula_constant") for bad in (True, "2", float("nan"), float("inf"))
        ):
            with self.subTest(declarations=declarations):
                program = deepcopy(good)
                program["expressions"][-1]["constants"] = declarations
                self.assertIn(code, {e["code"] for e in validate(case, program)["errors"]})
        for changed, code in (([{**declaration, "value": 2.0000000000001}], "unused_formula_constant"),
                              ([declaration, declaration], "duplicate_formula_constant"),
                              ([{**declaration, "origin": "source"}], "invalid_formula_constant_origin")):
            program = deepcopy(good)
            program["expressions"][-1]["constants"] = changed
            self.assertIn(code, {e["code"] for e in validate(case, program)["errors"]})

    def test_cardinality_remains_structural_and_cannot_copy_dependency_values(self):
        case, program = witness()
        program["expressions"][-1]["constants"] = [{"value": 2, "origin": "deterministic_cardinality"}]
        self.assertIn("constant_cardinality_mismatch", {e["code"] for e in validate(case, program)["errors"]})
        expression = program["expressions"][-1]
        variable = expression["variable_bindings"][0]["variable"]
        expression["formula"] = variable + " / 1"
        expression["constants"][0]["value"] = 1
        compiled, _, _ = compile_case(case, [program])
        output = execute(case, compiled)["outputs_by_obligation"]["double"]
        self.assertEqual(output["calculated_value"], 20)
        self.assertEqual(output["constant_resolutions"][0]["binding_count"], 1)

    def test_schema_requires_request_evidence_and_exposes_only_owned_addresses(self):
        case, program = witness()
        model, _ = capture_initial(case)
        schema = model.model_json_schema()
        constant = schema["$defs"]["RequestInput_double"]
        self.assertEqual(set(constant["required"]), {"variable", "value", "request_unit_id", "interpretation"})
        self.assertNotIn("source_text", constant["properties"])
        self.assertEqual(constant["properties"]["request_unit_id"]["enum"], ["request_002"])
        _, queue, _ = compile_case(case, [program])
        Draft202012Validator(schema).validate(queue.wires[0])
        for field in ("request_unit_id", "interpretation"):
            raw = deepcopy(queue.wires[0])
            raw["outputs"]["double"]["result"]["request_inputs"][0].pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                model.model_validate(raw)

    def test_internal_cardinality_defaults_do_not_leak_into_offline_wire(self):
        case, program = witness()
        expression = program["expressions"][-1]
        expression["formula"] = expression["variable_bindings"][0]["variable"] + " / 1"
        expression["constants"] = [{"value": 1, "origin": "deterministic_cardinality"}]
        parsed = SemanticCalculationProgram.model_validate(program).model_dump()
        compiled, queue, _ = compile_case(case, [parsed])
        self.assertEqual(execute(case, compiled)["status"], "ok")
        self.assertEqual(queue.wires[0]["outputs"]["double"]["result"]["request_inputs"], [])
        self.assertIsNotNone(queue.wires[0]["outputs"]["double"]["result"]["binding_count_variable"])

    def test_retry_repairs_only_failed_output_with_same_sources_and_calculated_dependency(self):
        case, good = witness()
        clean, _, _ = compile_case(case, [good])
        first = deepcopy(good)
        first["expressions"][-1]["constants"] = []
        repair = {**deepcopy(good), "expressions": [deepcopy(good["expressions"][-1])], "source_assertions": []}
        compiled, queue, prompts = compile_case(case, [first, repair])
        self.assertEqual(len(queue.wires), 2)
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        feedback = json.loads(prompts[1]["retry_feedback"])
        self.assertEqual(feedback["read_only_dependency_outputs"]["growth"]["normalized_value"], 20)
        self.assertEqual(set(queue.wires[1]["outputs"]), {"double"})
        self.assertEqual(canonical(clean["semantic_program"]["expressions"][0]),
                         canonical(compiled["semantic_program"]["expressions"][0]))
        self.assertEqual(canonical(clean["semantic_program"]["source_assertions"]),
                         canonical(compiled["semantic_program"]["source_assertions"]))
        self.assertEqual(clean["semantic_compilation_envelope"].visibility,
                         compiled["semantic_compilation_envelope"].visibility)
        for prompt in queue.messages:
            self.assertIn("request_inputs", canonical(prompt).decode())
            self.assertIn("request_unit_id", canonical(prompt).decode())
        self.assertEqual(execute(case, compiled)["outputs_by_obligation"]["double"]["calculated_value"], 40)

    def test_query_declaration_and_resolved_proof_tampering_remain_blocked(self):
        case, program = witness()
        compiled, _, _ = compile_case(case, [program])
        for target in ("query", "declaration", "proof"):
            changed_case, changed = deepcopy(case), deepcopy(compiled)
            if target == "query":
                changed_case["question"] += " "
            elif target == "declaration":
                changed["semantic_program"]["expressions"][-1]["request_inputs"][0]["source_text"] = "wrong"
            else:
                envelope = changed["semantic_compilation_envelope"]
                validation = envelope.validation_projection()
                validation["valid_expressions"][-1]["constant_resolutions"][0]["request_span"] = [0, 1]
                changed["semantic_compilation_envelope"] = CompilationEnvelopeV2.create(
                    visibility=envelope.visibility, program=changed["semantic_program"], validation=validation,
                    candidate_catalog=case["candidate_catalog"], obligations=case["obligations"], query=case["question"])
            with self.subTest(target=target):
                result = execute(changed_case, changed)
                self.assertEqual(result["outputs"], [])
                self.assertIn(result["validation"]["errors"][0]["code"], {"execution_content_mismatch", "validation_drift"})

    def test_structurally_grounded_wrong_interpretation_remains_a_semantic_negative(self):
        # No digit/word dictionary can certify this model interpretation.
        case, program = witness(value=3)
        compiled, _, _ = compile_case(case, [program])
        output = execute(case, compiled)["outputs_by_obligation"]["double"]
        self.assertEqual(output["calculated_value"], 60)
        self.assertNotEqual(output["calculated_value"], 40)  # The fixed semantic expectation.
        self.assertEqual(output["constant_resolutions"][0]["validation_scope"], "request_binding_not_semantic_equivalence")

    def test_final_answer_and_ledger_preserve_request_constant_provenance(self):
        case, program = witness()
        compiled, _, _ = compile_case(case, [program])
        agent = object.__new__(FinancialAgent)
        final = execute_compiled_fixture(agent, {**compiled, "query": case["question"],
            "answer_obligations": case["obligations"]}, case["candidate_catalog"])
        self.assertEqual(final["structured_result"]["status"], "ok")
        self.assertEqual(final["task_artifact_trace"]["integrity_status"], "ok")
        aggregate = next(a for a in final["artifacts"] if a["kind"] == "aggregated_answer")["payload"]
        self.assertEqual(canonical(aggregate["resolved_calculation_trace"]), canonical(final["resolved_calculation_trace"]))
        self.assertIn("constant_resolutions", canonical(final["resolved_calculation_trace"]).decode())
        for text in ("21%", "20%", "40%"):
            self.assertIn(text, final["answer"])


if __name__ == "__main__":
    unittest.main()
