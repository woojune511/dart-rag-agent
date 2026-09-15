"""Authored address-only transport witnesses; not sampled model accuracy."""
from copy import deepcopy
import socket
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from src.agent.financial_compiler_wire import lower_compiler_response
from src.agent.financial_reconciliation_candidates import build_semantic_candidate_catalog
from src.agent.financial_request_units import build_request_units
from src.ops.compiler_fixture_transport import project_offline_program_to_wire
from tests.mixed_numeric_source_test_support import (
    authored_program, capture_initial, compile_case, execute, load_criteria,
    load_sources, materialize,
)
from tests.test_request_formula_constants import validate, witness
from tests.test_numeric_compiler_grounding import output, wire
from tests.test_compiler_source_choices import direct


def addressed_wire(program, model):
    """Explicitly author the new layout; never applied to stored provider replies."""
    raw = project_offline_program_to_wire(program, model)
    for reply in raw["outputs"].values():
        result = reply["result"]
        if result is None:
            continue
        selections = [result.get("selection"), result.get("source_display")]
        selections.extend(item for group in result.get("inputs", {}).values() for item in group)
        for selection in selections:
            if selection is not None:
                selection.pop("evidence_text", None)
        for constant in result.get("constants", []):
            if constant["origin"] == "query":
                constant.pop("source_text", None)
    return raw


def lower(case, raw, model):
    return lower_compiler_response(raw, model=model, refs=model.__compiler_references__,
        obligations=case["obligations"], catalog=case["candidate_catalog"],
        visibility=model.__compiler_visibility__)


class AddressedNumericProofTests(unittest.TestCase):
    def setUp(self):
        for method in ("connect", "connect_ex"):
            blocker = patch.object(socket.socket, method, side_effect=AssertionError("provider forbidden"))
            blocker.start()
            self.addCleanup(blocker.stop)

    def test_selected_prose_address_preserves_signed_unit_inclusive_spans(self):
        case = materialize(load_sources()[2])
        program = authored_program(case, load_criteria()[case["case_id"]])
        model, _ = capture_initial(case)
        raw = addressed_wire(program, model)
        before = deepcopy((case, raw))
        lowered = lower(case, raw, model)
        self.assertEqual(validate(case, lowered)["status"], "ready")
        texts = [row["evidence_text"] for row in lowered["source_assertions"]]
        self.assertEqual(texts, ["(24)원", "6원"])
        self.assertEqual((case, raw), before)

    def test_duplicate_quantity_words_use_the_explicit_whole_request_address(self):
        request = "Return half the calculated rate, not half the source-stated rate."
        case, program = witness(request, "half the calculated rate", 0.5)
        model, _ = capture_initial(case)
        lowered = lower(case, addressed_wire(program, model), model)
        declaration = lowered["expressions"][-1]["constants"][0]
        self.assertEqual(declaration["source_text"], request)
        validation = validate(case, lowered)
        self.assertEqual(validation["status"], "ready", validation["errors"])
        proof = validation["valid_expressions"][-1]["constant_resolutions"][0]
        unit = build_request_units(case["question"])[1]
        self.assertEqual(proof["request_span"], [unit.start, unit.end])
        self.assertEqual(proof["validation_scope"], "request_binding_not_semantic_equivalence")

    def test_old_recopy_fields_are_not_a_production_fallback(self):
        case, program = witness()
        model, _ = capture_initial(case)
        raw = addressed_wire(program, model)
        for location, field, value in (
            ("display", "evidence_text", "21%"),
            ("constant", "source_text", "Double"),
        ):
            changed = deepcopy(raw)
            if location == "display":
                target = changed["outputs"]["growth"]["result"]["source_display"]
            else:
                target = changed["outputs"]["double"]["result"]["constants"][0]
            target[field] = value
            with self.subTest(location=location), self.assertRaises(ValidationError):
                model.model_validate(changed)

    def test_address_selection_still_requires_explicit_semantics_and_constants(self):
        case, program = witness()
        model, _ = capture_initial(case)
        raw = addressed_wire(program, model)
        for field in ("value", "request_unit_id", "interpretation"):
            altered = deepcopy(raw)
            altered["outputs"]["double"]["result"]["constants"][0].pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                model.model_validate(altered)
        altered = deepcopy(raw)
        altered["outputs"]["growth"]["result"]["source_display"]["interpretation"].pop("source_evidence_text")
        with self.assertRaises(ValidationError):
            model.model_validate(altered)
        for ref in ([], {}, 7):
            altered = deepcopy(raw)
            altered["outputs"]["growth"]["result"]["source_display"]["source_ref"] = ref
            with self.subTest(source_ref=ref), self.assertRaises(ValidationError):
                model.model_validate(altered)
        raw["outputs"]["double"]["result"]["constants"] = []
        self.assertIn("undeclared_formula_constant", {
            error["code"] for error in validate(case, lower(case, raw, model))["errors"]})

    def test_foreign_request_addresses_fail_locally_without_affecting_other_output(self):
        case, program = witness()
        model, _ = capture_initial(case)
        for unit_id in ("request_001", "request_999"):
            raw = addressed_wire(program, model)
            raw["outputs"]["double"]["result"]["constants"][0]["request_unit_id"] = unit_id
            errors = []
            lowered = lower_compiler_response(raw, model=model, refs=model.__compiler_references__,
                obligations=case["obligations"], catalog=case["candidate_catalog"],
                visibility=model.__compiler_visibility__, errors=errors)
            self.assertEqual([row["obligation_id"] for row in lowered["expressions"]], ["growth"])
            self.assertEqual([error["code"] for error in errors], ["constant_request_not_owned"])
            self.assertEqual(errors[0]["repair_action"], "repair_program")

    def test_original_internal_proof_violations_are_still_rejected(self):
        case, program = witness("Double or Double the calculated rate.")
        self.assertIn("constant_request_quote_invalid", {e["code"] for e in validate(case, program)["errors"]})
        case, program = witness()
        program["source_assertions"][0]["evidence_text"] = "not in this source"
        self.assertIn("source_assertion_text_mismatch", {e["code"] for e in validate(case, program)["errors"]})

    def test_offline_projection_never_repairs_missing_or_invalid_historical_proof(self):
        case, good = witness()
        model, _ = capture_initial(case)
        for change in ("missing", "foreign_bundle", "inexact", "uncovered", "request"):
            old = deepcopy(good)
            if change == "missing":
                old["source_assertions"] = []
            elif change == "foreign_bundle":
                old["source_assertions"][0]["source_bundle_id"] = "foreign-bundle"
            elif change == "request":
                old["expressions"][-1]["constants"][0]["source_text"] = "not in this request"
            else:
                old["source_assertions"][0]["evidence_text"] = "fiction" if change == "inexact" else "Lyra"
            before = deepcopy(old)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                model.model_validate(project_offline_program_to_wire(old, model))
            self.assertEqual(old, before)

    def test_equal_repeated_values_keep_distinct_candidate_locations_and_order(self):
        for text in ("Left 23%, right 23%.", "Right 17%, left 17%."):
            catalog = [row for row in build_semantic_candidate_catalog([{
                "candidate_id": "source", "candidate_kind": "chunk", "source_anchor": "[anonymous]",
                "text": text, "metadata": {"is_table": False}}]) if row["kind"] == "numeric"]
            self.assertEqual(len(catalog), 2)
            original = deepcopy(catalog)
            self.assertNotEqual(catalog[0]["source_span"], catalog[1]["source_span"])
            results = []
            for rows in (catalog, catalog[::-1]):
                refs, model, visibility, _ = wire(rows, [output()])
                for candidate in catalog:
                    program = lower_compiler_response(direct({"source_ref": refs.ref(candidate["candidate_id"])}),
                        model=model, refs=refs, obligations=[output()], catalog=rows, visibility=visibility)
                    proof = program["source_assertions"][0]
                    self.assertEqual(proof["candidate_ids"], [candidate["candidate_id"]])
                    start, end = candidate["source_bundle_value_span"]
                    self.assertEqual(proof["evidence_text"], candidate["source_bundle_text"][start:end])
                    results.append(proof)
            self.assertEqual(results[:2], results[2:])
            self.assertEqual(catalog, original)

    def test_unlocated_value_cannot_create_an_assertion(self):
        case, program = witness()
        candidate = next(row for row in case["candidate_catalog"] if row["candidate_kind"] == "sentence_value")
        candidate.update(source_text="No value here.", source_bundle_text="No value here.")
        candidate.pop("source_bundle_value_span", None)
        refs, model, visibility, _ = wire([candidate], [output()])
        with self.assertRaisesRegex(ValueError, "source_assertion_value_span_missing"):
            lower_compiler_response(direct({"source_ref": refs.ref(candidate["candidate_id"])}),
                model=model, refs=refs, obligations=[output()], catalog=[candidate], visibility=visibility)

    def test_address_only_initial_and_retry_use_same_permissions_and_accepted_bytes(self):
        case, good = witness()
        clean, _, _ = compile_case(case, [good])
        def bad_reference(raw, attempt, model):
            if attempt == 0:
                raw["outputs"]["double"]["result"]["constants"][0]["request_unit_id"] = "request_001"
        repair = {**deepcopy(good), "expressions": [deepcopy(good["expressions"][-1])], "source_assertions": []}
        compiled, queue, _ = compile_case(case, [good, repair], mutate=bad_reference)
        self.assertEqual((len(queue.wires), compiled["semantic_program_retry_count"]), (2, 1))
        self.assertEqual(clean["semantic_program"]["expressions"][0], compiled["semantic_program"]["expressions"][0])
        self.assertEqual(clean["semantic_program"]["source_assertions"], compiled["semantic_program"]["source_assertions"])
        self.assertEqual(clean["semantic_compilation_envelope"].visibility, compiled["semantic_compilation_envelope"].visibility)
        self.assertEqual(execute(case, compiled)["outputs_by_obligation"]["double"]["calculated_value"], 40)


if __name__ == "__main__":
    unittest.main()
