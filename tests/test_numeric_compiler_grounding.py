"""Model-transport/source contracts; authored choices are not semantic accuracy."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from src.agent.financial_calculation_execution import execute_semantic_calculation_program, validate_semantic_calculation_program
from src.agent.financial_compiler_wire import CompilerReferencesV1, compiler_response_model, lower_compiler_response
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts, _semantic_candidate_visibility
from src.agent.financial_source_interpretation import interpretation_axis_sources
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from tests.compiler_wire_test_support import wire_fixture
from tests.semantic_program_test_support import _candidate, _obligation, _requirement, _scope


QUERY = "Return the quantity for the named division."


def source(identifier="cell", *, context=True, period="2045"):
    row = _candidate(identifier, 23, period=period)
    year = period or "2045"
    row.update(row_headers=["Divisions", "Cedar"], column_headers=[year, "quantity"],
        physical_table_id="table", physical_row_id=identifier, physical_cell_id=identifier,
        source_document_sha256="doc", source_table_locator="/section[1]/table[1]")
    if context:
        row["source_contexts"] = [{"context_id": "heading-" + identifier, "document_sha256": "doc",
            "relation": "ancestor_heading", "parent_locator": "/section[1]",
            "source_locator": "/section[1]/title[1]", "source_text": "Cedar division " + year,
            "source_span": [0, 19]}]
    return row


def output(identifier="answer", **overrides):
    return _obligation(identifier, "direct_value", "quantity", **overrides)


def wire(catalog, owners):
    plan = _semantic_candidate_cohorts(catalog, owners)
    payload = FinancialAgent._semantic_program_prompt_payload(catalog, plan)
    refs = CompilerReferencesV1.build(catalog, owners, QUERY, payload)
    visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=plan["visible_candidate_ids"],
        candidate_ids_by_owner=plan["candidate_ids_by_owner"])
    model = compiler_response_model(owners, refs)
    return refs, model, visibility, payload


def selection(refs, candidate, *, context=False):
    result = {"source_ref": refs.ref(candidate["candidate_id"]), "interpretation": {
        "request_unit_ids": ["request_001"], "subject": "Cedar division", "metric": "quantity"}}
    if context:
        result["context_evidence"] = [{"context_ref": refs.ref(candidate["source_contexts"][0]["context_id"]),
            "evidence_text": "Cedar division 2045", "supports_interpretation": True,
            "resolves": [{"field": "period", "value": "2045"}]}]
    return result


def lower(selected, catalog, owners, setup):
    refs, model, visibility, _ = setup
    raw = {"outputs": {owners[0]["obligation_id"]: {"status": "ready", "result": {"selection": selected}}}}
    return lower_compiler_response(raw, model=model, refs=refs, obligations=owners,
        catalog=catalog, visibility=visibility)


class NumericCompilerGroundingTests(unittest.TestCase):
    def test_axis_only_schema_omits_duplicate_and_unavailable_fields(self):
        catalog, owners = [source(context=False)], [output()]
        setup = wire(catalog, owners)
        schema = json.dumps(setup[1].model_json_schema())
        for field in ("axis_refs", "context_bindings", "context_evidence", "context_ref"):
            self.assertNotIn('"' + field + '"', schema)
        selected = selection(setup[0], catalog[0])
        before = deepcopy((catalog, owners, selected))
        program = lower(selected, catalog, owners, setup)
        self.assertEqual(program["direct_bindings"][0]["source_interpretation"]["axis_refs"],
            list(interpretation_axis_sources(catalog[0])))
        validation = validate_semantic_calculation_program(program=program, obligations=owners,
            candidate_catalog=catalog, query=QUERY, candidate_visibility=setup[2])
        self.assertEqual(validation["status"], "ready", validation["errors"])
        self.assertEqual((catalog, owners, selected), before)
        for key, value in (("context_bindings", [{"context_id": "ctx_0", "evidence_text": "2045", "field": "period", "value": "2045"}]),
                           ("context_evidence", [])):
            with self.subTest(key=key), self.assertRaises(ValueError):
                lower({**selected, key: value}, catalog, owners, setup)

    def test_one_exact_context_quote_supplies_both_internal_proofs(self):
        catalog, owners = [source(period="")], [output(scope=_scope(period="2045"))]
        setup = wire(catalog, owners)
        selected = selection(setup[0], catalog[0], context=True)
        self.assertEqual(json.dumps(selected).count("Cedar division 2045"), 1)
        program = lower(selected, catalog, owners, setup)
        binding = program["direct_bindings"][0]
        self.assertEqual(binding["source_interpretation"]["context_evidence"],
            [{"context_id": "heading-cell", "evidence_text": "Cedar division 2045"}])
        self.assertEqual(binding["context_bindings"], [{"context_id": "heading-cell", "evidence_text": "Cedar division 2045",
            "field": "period", "value": "2045"}])
        validation = validate_semantic_calculation_program(program=program, obligations=owners,
            candidate_catalog=catalog, query=QUERY, candidate_visibility=setup[2])
        self.assertEqual(validation["status"], "ready", validation["errors"])

    def test_invented_and_wrong_reference_kinds_fail_before_lowering(self):
        catalog, owners = [source()], [output()]
        setup = wire(catalog, owners)
        for address in ("ctx_0", catalog[0]["context_fingerprint"], setup[0].ref("cell"),
                        setup[0].ref(next(iter(interpretation_axis_sources(catalog[0]))))):
            selected = selection(setup[0], catalog[0], context=True)
            selected["context_evidence"][0]["context_ref"] = address
            with self.subTest(address=address), self.assertRaises(ValueError):
                lower(selected, catalog, owners, setup)

    def test_foreign_attachment_and_changed_quote_still_fail_validation(self):
        catalog, owners = [source(), source("other")], [output()]
        setup = wire(catalog, owners)
        for change, expected in (({"context_ref": setup[0].ref("heading-other")}, "context_not_attached_to_candidate"),
                                 ({"evidence_text": "Cedar Division 2045"}, "context_quote_not_exact")):
            selected = selection(setup[0], catalog[0], context=True)
            selected["context_evidence"][0].update(change)
            program = lower(selected, catalog, owners, setup)
            validation = validate_semantic_calculation_program(program=program, obligations=owners,
                candidate_catalog=catalog, query=QUERY, candidate_visibility=setup[2])
            self.assertIn(expected, [error["code"] for error in validation["errors"]])

    def test_owner_without_context_does_not_inherit_other_owner_schema(self):
        catalog = [source("plain", context=False), source("contextual", period="2044")]
        owners = [output("current", scope=_scope(period="2045")), output("prior", scope=_scope(period="2044"))]
        refs, model, _, _ = wire(catalog, owners)
        schemas = model.model_json_schema()["$defs"]
        def result_schema(key):
            return schemas[schemas["Direct_" + key]["properties"]["selection"]["$ref"].split("/")[-1]]
        self.assertNotIn("context_evidence", result_schema("current")["properties"])
        self.assertIn("context_evidence", result_schema("prior")["properties"])
        # The hidden source is still known to the code, never offered as context.
        hidden = source("hidden", period="2043")
        expanded = wire([*catalog, hidden], owners)
        self.assertNotIn(expanded[0].ref("heading-hidden"), json.dumps(expanded[1].model_json_schema()))
        reversed_setup = wire(catalog[::-1], owners)
        self.assertEqual(refs, reversed_setup[0])
        self.assertEqual(model.model_json_schema(), reversed_setup[1].model_json_schema())

    def test_schema_preparation_error_is_reported_not_masked(self):
        catalog, owners = [source(context=False)], [output()]
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {"query": QUERY, "answer_obligations": owners, "semantic_candidate_catalog_prebuilt": True,
            "semantic_source_candidates": catalog, "semantic_candidate_catalog": catalog, "include_debug_bundle": True}
        with patch("src.agent.financial_graph_calculation.compiler_response_model", side_effect=ValueError("bad schema")):
            result = agent._compile_semantic_calculation_program(state)
        attempts = result["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]["attempts"]
        self.assertEqual(len(attempts), 2)
        self.assertTrue(all(row["serialized_schema_bytes"] is None for row in attempts))
        self.assertNotEqual(result["semantic_program_validation"]["status"], "ready")

    def test_required_inputs_display_and_dependency_have_separate_context_spaces(self):
        catalog = [source("current", context=False), source("prior", period="2044")]
        owners = [_obligation("calc", "derived_value", "quantity", depends_on=["accepted"],
            scope=_scope(period="2045"), evidence_requirements=[
                _requirement("now", "quantity", period="2045"), _requirement("then", "quantity", period="2044")])]
        refs, model, _, _ = wire(catalog, owners)
        schemas = model.model_json_schema()["$defs"]
        inputs = schemas["Inputs_calc"]["properties"]
        def properties(key):
            return schemas[inputs[key]["items"]["$ref"].split("/")[-1]]["properties"]
        self.assertNotIn("context_evidence", properties("now"))
        self.assertIn("context_evidence", properties("then"))
        self.assertNotIn("context_evidence", properties("dependencies"))
        display = schemas["Calculation_calc"]["properties"]["source_display"]["anyOf"][0]["$ref"]
        self.assertNotIn("context_evidence", schemas[display.split("/")[-1]]["properties"])
        # Scope-widening at one input cannot widen another input's model schema.
        self.assertIn(refs.ref("heading-prior"), json.dumps(schemas))

    def test_scope_only_context_does_not_become_subject_support(self):
        candidate = source(period="")
        candidate["source_contexts"][0].update(relation="table_text_row",
            parent_locator="/section[1]/table[1]", source_locator="/section[1]/table[1]/row[1]")
        catalog, owners = [candidate], [output(scope=_scope(period="2045"))]
        setup = wire(catalog, owners)
        selected = selection(setup[0], candidate, context=True)
        selected["context_evidence"][0]["supports_interpretation"] = False
        program = lower(selected, catalog, owners, setup)
        self.assertEqual(program["direct_bindings"][0]["source_interpretation"]["context_evidence"], [])
        validation = validate_semantic_calculation_program(program=program, obligations=owners,
            candidate_catalog=catalog, query=QUERY, candidate_visibility=setup[2])
        self.assertEqual(validation["status"], "ready", validation["errors"])
        selected["context_evidence"][0]["supports_interpretation"] = True
        program = lower(selected, catalog, owners, setup)
        validation = validate_semantic_calculation_program(program=program, obligations=owners,
            candidate_catalog=catalog, query=QUERY, candidate_visibility=setup[2])
        self.assertIn("context_not_attached_to_candidate", [error["code"] for error in validation["errors"]])

    def test_unused_context_and_interpretation_without_target_are_not_guessed(self):
        catalog, owners = [source()], [output()]
        setup = wire(catalog, owners)
        for supports, interpretation in ((False, True), (True, False)):
            selected = selection(setup[0], catalog[0], context=True)
            selected["context_evidence"][0].update(supports_interpretation=supports, resolves=[])
            if not interpretation:
                selected["interpretation"] = None
            with self.subTest(supports=supports), self.assertRaises(ValueError):
                lower(selected, catalog, owners, setup)

    def test_offline_projection_does_not_discard_invalid_old_proofs(self):
        catalog, owners = [source(context=False)], [output()]
        setup = wire(catalog, owners)
        program = {"direct_bindings": [{"obligation_id": "answer", "candidate_id": "cell",
            "source_interpretation": {**selection(setup[0], catalog[0])["interpretation"], "axis_refs": ["foreign-axis"]}}]}
        with self.assertRaisesRegex(ValueError, "offline_fixture_has_foreign_axis"):
            wire_fixture(program, setup[1])
        program["direct_bindings"][0]["source_interpretation"].update(axis_refs=[],
            context_evidence=[{"context_id": "hidden", "evidence_text": "Cedar"}])
        projected = wire_fixture(program, setup[1])
        with self.assertRaises(ValueError):
            setup[1].model_validate(projected)

    def test_lowered_context_and_axes_are_bound_by_execution_envelope(self):
        catalog, owners = [source(period="")], [output(scope=_scope(period="2045"))]
        setup = wire(catalog, owners)
        program = lower(selection(setup[0], catalog[0], context=True), catalog, owners, setup)
        inputs = dict(program=program, obligations=owners, candidate_catalog=catalog, query=QUERY)
        validation = validate_semantic_calculation_program(**inputs, candidate_visibility=setup[2])
        envelope = CompilationEnvelopeV2.create(**inputs, visibility=setup[2], validation=validation)
        result = execute_semantic_calculation_program(**inputs, compilation_envelope=envelope,
            require_compilation_envelope=True)
        self.assertEqual(len(result["outputs"]), 1, result["validation"])
        for field, changed in (("context_bindings", []), ("source_interpretation", None)):
            altered = deepcopy(program)
            altered["direct_bindings"][0][field] = changed
            result = execute_semantic_calculation_program(**{**inputs, "program": altered}, compilation_envelope=envelope,
                require_compilation_envelope=True)
            self.assertEqual(result["outputs"], [])
            self.assertIn("validation_drift", [error["code"] for error in result["validation"]["errors"]])


if __name__ == "__main__":
    unittest.main()
