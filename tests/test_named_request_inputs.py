"""Named request scalars: authored contract tests, not model accuracy evidence."""
from copy import deepcopy
import json
import socket
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from src.agent.financial_request_units import build_request_units
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.ops.compiler_fixture_transport import project_offline_program_to_wire
from tests.mixed_numeric_source_test_support import canonical, capture_initial, compile_case, execute
from tests.test_request_formula_constants import validate, witness


def named_witness(value=2, variable="factor"):
    case, program = witness(request=f"Scale the calculated rate by {value!r}.", quote=repr(value), value=value)
    expression = program["expressions"][-1]
    old = expression.pop("constants")[0]
    unit = next(unit for unit in build_request_units(case["question"])
                if unit.request_unit_id == old["request_unit_id"])
    expression["request_inputs"] = [{"variable": variable, "value": value,
        "request_unit_id": unit.request_unit_id, "source_text": unit.text,
        "interpretation": old["interpretation"]}]
    expression["formula"] = expression["variable_bindings"][0]["variable"] + " * " + variable
    return case, program


class NamedRequestInputTests(unittest.TestCase):
    def setUp(self):
        for method in ("connect", "connect_ex"):
            blocker = patch.object(socket.socket, method, side_effect=AssertionError("provider forbidden"))
            blocker.start()
            self.addCleanup(blocker.stop)

    def test_production_schema_has_names_not_origin_or_legacy_constants(self):
        case, program = named_witness()
        model, _ = capture_initial(case)
        schema = model.model_json_schema()
        calculation = schema["$defs"]["Calculation_double"]
        self.assertIn("request_inputs", calculation["required"])
        self.assertNotIn("constants", calculation["properties"])
        self.assertNotIn('"origin"', json.dumps(schema))
        raw = project_offline_program_to_wire(program, model)
        model.model_validate(raw)
        result = raw["outputs"]["double"]["result"]
        self.assertEqual(result["formula"], program["expressions"][-1]["formula"])
        self.assertNotIn("source_text", result["request_inputs"][0])
        for field in ("variable", "value", "request_unit_id", "interpretation"):
            bad = deepcopy(raw)
            bad["outputs"]["double"]["result"]["request_inputs"][0].pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                model.model_validate(bad)
        for field, value in (("origin", "query"), ("source_text", "Double")):
            bad = deepcopy(raw)
            bad["outputs"]["double"]["result"]["request_inputs"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                model.model_validate(bad)

    def test_named_scalars_preserve_formula_and_calculated_dependency(self):
        for value, variable in ((2, "factor"), (-3, "multiplier"), (0.5, "fraction"), (2.75, "coefficient")):
            case, program = named_witness(value, variable)
            original = deepcopy((case, program))
            compiled, queue, _ = compile_case(case, [program])
            result = execute(case, compiled)
            with self.subTest(value=value):
                self.assertEqual(result["status"], "ok", result)
                output = result["outputs_by_obligation"]["double"]
                self.assertEqual(output["calculated_value"], 20 * value)
                self.assertEqual(output["formula"], program["expressions"][-1]["formula"])
                proof = output["constant_resolutions"][0]
                self.assertEqual((proof["variable"], proof["value"], proof["origin"]), (variable, value, "query"))
                self.assertEqual(case["question"][slice(*proof["request_span"])], proof["source_text"])
                self.assertEqual(len(output["input_rows"]), 1)
                self.assertEqual(len(queue.wires), 1)
                self.assertEqual((case, program), original)

    def test_equal_values_have_separate_names_and_order_does_not_change_results(self):
        case, program = named_witness()
        expression = program["expressions"][-1]
        expression["request_inputs"].append({**expression["request_inputs"][0], "variable": "divisor"})
        expression["formula"] += " / divisor"
        for inputs in (expression["request_inputs"][:], expression["request_inputs"][::-1]):
            expression["request_inputs"] = inputs
            compiled, _, _ = compile_case(case, [program])
            self.assertEqual(execute(case, compiled)["outputs_by_obligation"]["double"]["calculated_value"], 20)

    def test_missing_unused_colliding_and_invalid_names_fail_without_inference(self):
        for change in ("missing", "unused", "source_collision", "duplicate", "invalid", "literal", "legacy_mix"):
            case, program = named_witness()
            expression = program["expressions"][-1]
            item = expression["request_inputs"][0]
            if change == "missing":
                expression["request_inputs"] = []
            elif change == "unused":
                expression["request_inputs"].append({**item, "variable": "unused"})
            elif change == "source_collision":
                item["variable"] = expression["variable_bindings"][0]["variable"]
            elif change == "duplicate":
                expression["request_inputs"].append(deepcopy(item))
            elif change == "invalid":
                item["variable"] = "not an identifier"
            elif change == "literal":
                expression["formula"] += " * 7"
            else:
                expression["constants"] = [{"value": 7, "origin": "query"}]
            before = deepcopy(program)
            with self.subTest(change=change):
                result = validate(case, program)
                self.assertTrue(any(row["obligation_id"] == "double" for row in result["errors"]), result)
                self.assertEqual(program, before)

    def test_request_proof_must_be_owned_exact_and_explicit(self):
        for field, value in (("request_unit_id", "request_001"), ("source_text", "Double"),
                ("interpretation", " "), ("value", True), ("value", float("nan")),
                ("value", float("inf")), ("value", "2")):
            case, program = named_witness()
            program["expressions"][-1]["request_inputs"][0][field] = value
            with self.subTest(field=field, value=value):
                result = validate(case, program)
                self.assertTrue(any(row["obligation_id"] == "double" for row in result["errors"]), result)

    def test_count_is_computed_from_source_bindings_not_request_inputs(self):
        case, program = named_witness()
        expression = program["expressions"][-1]
        expression["binding_count_variable"] = "input_count"
        expression["formula"] += " / input_count"
        compiled, queue, _ = compile_case(case, [program])
        output = execute(case, compiled)["outputs_by_obligation"]["double"]
        self.assertEqual(output["calculated_value"], 40)
        count = next(row for row in output["constant_resolutions"] if row["origin"] == "deterministic_cardinality")
        self.assertEqual((count["variable"], count["value"], count["binding_count"]), ("input_count", 1, 1))
        wire = queue.wires[0]["outputs"]["double"]["result"]
        self.assertEqual(wire["binding_count_variable"], "input_count")
        self.assertEqual(len(wire["request_inputs"]), 1)

    def test_count_names_cannot_collide_be_unused_or_supply_their_own_value(self):
        for name in ("factor", "unused", "", "not a name"):
            case, program = named_witness()
            program["expressions"][-1]["binding_count_variable"] = name
            with self.subTest(name=name):
                self.assertTrue(any(row["obligation_id"] == "double" for row in validate(case, program)["errors"]))
        model, _ = capture_initial(case)
        raw = project_offline_program_to_wire(named_witness()[1], model)
        raw["outputs"]["double"]["result"]["binding_count_variable"] = {"value": 2}
        with self.assertRaises(ValidationError):
            model.model_validate(raw)

    def test_request_inputs_do_not_satisfy_missing_source_bindings(self):
        case, program = named_witness()
        expression = program["expressions"][-1]
        expression["variable_bindings"] = []
        expression["formula"] = "factor"
        self.assertIn("invalid_variable_binding", {row["code"] for row in validate(case, program)["errors"]})
        case, program = named_witness()
        expression = program["expressions"][0]
        removed = expression["variable_bindings"].pop()
        unit = build_request_units(case["question"])[0]
        expression["request_inputs"] = [{"variable": removed["variable"], "value": 120,
            "request_unit_id": unit.request_unit_id, "source_text": unit.text,
            "interpretation": "An intentionally wrong request interpretation cannot replace evidence."}]
        # A linked request cannot manufacture the missing evidence requirement.
        self.assertIn("missing_required_evidence_binding", {
            row["code"] for row in validate(case, program)["errors"] if row["obligation_id"] == "growth"})

    def test_neutral_literals_need_no_origin_and_legacy_wire_is_rejected(self):
        case, program = named_witness()
        model, _ = capture_initial(case)
        raw = project_offline_program_to_wire(program, model)
        self.assertEqual(raw["outputs"]["growth"]["result"]["request_inputs"], [])
        self.assertIn("100", raw["outputs"]["growth"]["result"]["formula"])
        for value in ([], [{"value": 100, "origin": "deterministic_calculation"}]):
            changed = deepcopy(raw)
            changed["outputs"]["growth"]["result"]["constants"] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                model.model_validate(changed)

    def test_scalar_names_values_and_proofs_are_bound_to_the_execution_envelope(self):
        case, program = named_witness()
        compiled, _, _ = compile_case(case, [program])
        for field, value in (("variable", "other"), ("value", 3), ("request_unit_id", "request_001"),
                ("source_text", "Double"), ("interpretation", "different"), ("proof", 8)):
            changed = deepcopy(compiled)
            if field == "proof":
                envelope = changed["semantic_compilation_envelope"]
                validation = envelope.validation_projection()
                validation["valid_expressions"][-1]["constant_resolutions"][0]["value"] = value
                changed["semantic_compilation_envelope"] = CompilationEnvelopeV2.create(
                    visibility=envelope.visibility, program=changed["semantic_program"], validation=validation,
                    candidate_catalog=case["candidate_catalog"], obligations=case["obligations"], query=case["question"])
            else:
                changed["semantic_program"]["expressions"][-1]["request_inputs"][0][field] = value
            with self.subTest(field=field):
                result = execute(case, changed)
                self.assertEqual(result["outputs"], [])
                self.assertIn(result["validation"]["errors"][0]["code"],
                    {"execution_content_mismatch", "validation_drift"})

    def test_retry_keeps_other_accepted_program_bytes_and_same_source_permissions(self):
        case, good = named_witness()
        clean, _, _ = compile_case(case, [good])
        def missing(raw, attempt, model):
            if attempt == 0:
                raw["outputs"]["double"]["result"]["request_inputs"] = []
        repair = {**deepcopy(good), "expressions": [deepcopy(good["expressions"][-1])], "source_assertions": []}
        compiled, queue, _ = compile_case(case, [good, repair], mutate=missing)
        self.assertEqual((len(queue.wires), compiled["semantic_program_retry_count"]), (2, 1))
        self.assertEqual(canonical(clean["semantic_program"]["expressions"][0]),
                         canonical(compiled["semantic_program"]["expressions"][0]))
        self.assertEqual(canonical(clean["semantic_program"]["source_assertions"]),
                         canonical(compiled["semantic_program"]["source_assertions"]))
        self.assertEqual(clean["semantic_compilation_envelope"].visibility,
                         compiled["semantic_compilation_envelope"].visibility)
        self.assertEqual(execute(case, compiled)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
