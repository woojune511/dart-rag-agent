"""Generation omissions fail early; authored repairs are not model evidence."""
from copy import deepcopy
import json
import socket
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_compiler_wire import lower_compiler_response
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.ops.compiler_fixture_transport import project_offline_program_to_wire
from tests.mixed_numeric_source_test_support import canonical, capture_initial, compile_case, execute
from tests.test_compiler_source_choices import direct, prose
from tests.test_numeric_compiler_grounding import QUERY, output, selection, source, wire
from tests.test_request_formula_constants import witness


class CompilerRequiredEvidenceFieldsTests(unittest.TestCase):
    def setUp(self):
        for method in ("connect", "connect_ex"):
            blocker = patch.object(socket.socket, method, side_effect=AssertionError("provider forbidden"))
            blocker.start()
            self.addCleanup(blocker.stop)

    def assert_wire(self, model, raw, *, valid=True):
        before = deepcopy(raw)
        errors = list(Draft202012Validator(model.model_json_schema()).iter_errors(raw))
        self.assertEqual(not errors, valid, [error.message for error in errors])
        if valid:
            model.model_validate(raw)
        else:
            with self.assertRaises(ValidationError):
                model.model_validate(raw)
        self.assertEqual(raw, before)

    def test_every_calculation_explicitly_declares_its_constant_list(self):
        case, program = witness()
        model, _ = capture_initial(case)
        raw = project_offline_program_to_wire(program, model)
        self.assert_wire(model, raw)
        for owner in ("growth", "double"):
            definition = model.model_json_schema()["$defs"]["Calculation_" + owner]
            self.assertIn("constants", definition["required"])
            for change in ("omit", "null"):
                altered = deepcopy(raw)
                result = altered["outputs"][owner]["result"]
                result.pop("constants") if change == "omit" else result.update(constants=None)
                with self.subTest(owner=owner, change=change):
                    self.assert_wire(model, altered, valid=False)
        self.assertEqual(raw["outputs"]["growth"]["result"]["constants"], [])

    def test_prose_interpretation_quote_is_required_for_direct_input_and_display(self):
        case, program = witness()
        model, _ = capture_initial(case)
        raw = project_offline_program_to_wire(program, model)
        display = raw["outputs"]["growth"]["result"]["source_display"]
        candidate_id = case["fixture_candidate_ids"]["reported"]
        candidate = next(row for row in case["candidate_catalog"] if row["candidate_id"] == candidate_id)
        for kind in ("direct", "input", "display"):
            owner = output() if kind == "direct" else {**output(), "kind": "derived_value"}
            refs, shape, _, _ = wire([candidate], [owner])
            selected = {**deepcopy(display), "source_ref": refs.ref(candidate_id)}
            if kind == "direct":
                payload = direct(selected)
            else:
                payload = {"outputs": {"answer": {"status": "ready", "result": {
                    "inputs": {"own": [{**deepcopy(selected), "variable": "x"}]},
                    "formula": "x", "constants": [], "comparison_request_unit_id": None,
                    "source_display": selected if kind == "display" else None,
                    "source_display_reason": "Authored display choice."}}}}
                if kind == "input":
                    selected = payload["outputs"]["answer"]["result"]["inputs"]["own"][0]
            self.assert_wire(shape, payload)
            for invalid in (None, "", "omit"):
                before = deepcopy(selected["interpretation"])
                if invalid == "omit":
                    selected["interpretation"].pop("source_evidence_text")
                else:
                    selected["interpretation"]["source_evidence_text"] = invalid
                with self.subTest(kind=kind, invalid=invalid):
                    self.assert_wire(shape, payload, valid=False)
                selected["interpretation"] = before

    def test_table_axes_and_narrative_do_not_gain_prose_or_constant_fields(self):
        candidate, owner = source(context=False), output()
        refs, model, _, _ = wire([candidate], [owner])
        selected = selection(refs, candidate)
        self.assert_wire(model, direct(selected))
        self.assertNotIn('"source_evidence_text"', json.dumps(model.model_json_schema()))
        self.assertNotIn('"constants"', json.dumps(model.model_json_schema()))
        selected["interpretation"]["source_evidence_text"] = "23"
        self.assert_wire(model, direct(selected), valid=False)
        _, narrative, _, _ = wire([candidate], [{**owner, "kind": "narrative"}])
        for field in ("source_evidence_text", "constants", "formula"):
            self.assertNotIn('"' + field + '"', json.dumps(narrative.model_json_schema()))

    def test_attached_context_can_explicitly_replace_the_prose_body_quote(self):
        candidate, owner = prose(), output()
        context_source = source()
        for key in ("source_document_sha256", "source_table_locator", "source_contexts"):
            candidate[key] = deepcopy(context_source[key])
        refs, model, visibility, _ = wire([candidate], [owner])
        selected = selection(refs, candidate, context=True)
        selected["evidence_text"] = "23%"
        selected["interpretation"]["source_evidence_text"] = None
        raw = direct(selected)
        self.assert_wire(model, raw)
        def validation(payload):
            program = lower_compiler_response(payload, model=model, refs=refs, obligations=[owner],
                catalog=[candidate], visibility=visibility)
            return validate_semantic_calculation_program(program=program, obligations=[owner],
                candidate_catalog=[candidate], query=QUERY, candidate_visibility=visibility)
        self.assertEqual(validation(raw)["status"], "ready")
        omitted = deepcopy(raw)
        omitted["outputs"]["answer"]["result"]["selection"]["interpretation"].pop("source_evidence_text")
        self.assert_wire(model, omitted, valid=False)
        for replacement, code in (([], "source_interpretation_evidence_mismatch"),
                ([{**selected["context_evidence"][0], "evidence_text": "foreign quote"}], "context_quote_not_exact")):
            changed = deepcopy(raw)
            changed["outputs"]["answer"]["result"]["selection"]["context_evidence"] = replacement
            self.assertIn(code, {e["code"] for e in validation(changed)["errors"]})

    def test_required_list_is_not_permission_for_undeclared_or_wrong_constants(self):
        case, good = witness()
        model, _ = capture_initial(case)
        raw = project_offline_program_to_wire(good, model)
        raw["outputs"]["double"]["result"]["constants"] = []
        self.assert_wire(model, raw)  # JSON schema cannot prove AST semantics.
        program = lower_compiler_response(raw, model=model, refs=model.__compiler_references__,
            obligations=case["obligations"], catalog=case["candidate_catalog"], visibility=model.__compiler_visibility__)
        result = validate_semantic_calculation_program(program=program, obligations=case["obligations"],
            candidate_catalog=case["candidate_catalog"], query=case["question"])
        self.assertIn("undeclared_formula_constant", {e["code"] for e in result["errors"]})

    def test_schema_retry_preserves_an_already_accepted_independent_island(self):
        case, good = witness()
        separate = deepcopy(case["obligations"][0])
        separate["obligation_id"] = "separate"
        # Distinct input owner IDs preserve global owner identity.
        for requirement in separate["evidence_requirements"]:
            requirement["requirement_id"] = "separate_" + requirement["requirement_id"]
        case["obligations"].insert(0, separate)
        first = deepcopy(good)
        first["expressions"] = [deepcopy(good["expressions"][0])]
        first["expressions"][0]["obligation_id"] = "separate"
        for binding in first["expressions"][0]["variable_bindings"]:
            binding["source_requirement_id"] = "separate_" + binding["source_requirement_id"]
        clean, _, _ = compile_case(case, [first, good])
        def omit(raw, attempt, model):
            if attempt == 1:
                raw["outputs"]["double"]["result"].pop("constants")
        compiled, queue, prompts = compile_case(case, [first, good, good], mutate=omit)
        self.assertEqual((len(queue.wires), compiled["semantic_program_retry_count"]), (3, 1))
        self.assertEqual(execute(case, compiled)["status"], "ok")
        for result in (clean, compiled):
            self.assertEqual(result["semantic_program_validation"]["status"], "ready")
        self.assertEqual(canonical(clean["semantic_program"]["expressions"][0]),
                         canonical(compiled["semantic_program"]["expressions"][0]))
        self.assertEqual(clean["semantic_compilation_envelope"].visibility,
                         compiled["semantic_compilation_envelope"].visibility)
        self.assertNotIn("separate", queue.wires[-1]["outputs"])
        self.assertEqual(json.loads(prompts[-1]["retry_feedback"])["read_only_dependency_outputs"], {})

    def test_offline_transport_preserves_missing_prose_evidence_and_invalid_cell_quotes(self):
        case, good = witness()
        model, _ = capture_initial(case)
        normalized = SemanticCalculationProgram.model_validate(good).model_dump()
        self.assert_wire(model, project_offline_program_to_wire(normalized, model))
        missing = deepcopy(good)
        missing["expressions"][0]["source_display_interpretation"].pop("source_evidence_text")
        projected = project_offline_program_to_wire(missing, model)
        self.assertNotIn("source_evidence_text", projected["outputs"]["growth"]["result"]["source_display"]["interpretation"])
        self.assert_wire(model, projected, valid=False)
        invalid = deepcopy(normalized)
        invalid["expressions"][0]["variable_bindings"][0]["source_interpretation"]["source_evidence_text"] = "foreign quote"
        self.assert_wire(model, project_offline_program_to_wire(invalid, model), valid=False)


if __name__ == "__main__":
    unittest.main()
