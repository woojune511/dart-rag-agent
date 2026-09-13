"""A located row description is not permission to use its scalar cell."""

from copy import deepcopy
import json
import unittest

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program, validate_semantic_calculation_program,
)
from src.agent.financial_graph_calculation import _semantic_candidate_visibility, FinancialAgentCalculationMixin
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.semantic_program_test_support import _candidate, _obligation, _requirement, _scope, _StructuredQueueLLM, _with_narrative_claims


class NarrativeRowDescriptionTests(unittest.TestCase):
    def setUp(self):
        self.scope = _scope(company="Example issuer", period="2034")
        self.catalog = [{**_candidate("cell", 23.4, raw_unit="%", row_label="Partners"),
            "company": "Example issuer", "document_company": "Example issuer", "year": 2034,
            "source_document_id": "document-alpha", "candidate_kind": "structured_row",
            "source_anchor": "[Example issuer | 2034 | Chapter > Routes]",
            "physical_table_id": "table-alpha", "physical_row_id": "row-alpha",
            "physical_cell_id": "cell-alpha", "row_headers": ["Partners", "Regional outlets"],
            "column_headers": ["share"], "period_label_scope": "unbound_table",
            "source_period_surface": "share", "period_source": "source_surface_unresolved",
            "source_text": "Partners | Regional outlets | share 23.4%"}]
        self.owners = [_obligation("routes", "narrative", "Describe routes.", scope=self.scope,
            evidence_requirements=[{**_requirement("routes-input", "Routes"), "scope": self.scope}])]
        self.program = {"narrative_bindings": [{"obligation_id": "routes",
            "evidence_bindings": [{"candidate_id": "cell", "source_requirement_id": "routes-input",
                "row_description_quote": "Regional outlets"}],
            "text": "Partners distribute through regional outlets."}]}

    def validate(self, program=None, catalog=None, owners=None, *, visible=True):
        catalog = self.catalog if catalog is None else catalog
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=["cell"] if visible else [],
            candidate_ids_by_owner={"routes": ["cell"] if visible else [], "routes-input": ["cell"] if visible else []})
        return validate_semantic_calculation_program(program=program or self.program,
            obligations=owners or self.owners, candidate_catalog=catalog, query="Describe routes.",
            candidate_visibility=visibility)

    def test_exact_description_uses_document_scope_without_changing_value_period(self):
        before = deepcopy((self.catalog, self.program))
        fingerprint = semantic_candidate_catalog_fingerprint(self.catalog)
        result = self.validate()
        self.assertEqual(result["status"], "ready", result["errors"])
        reading = result["valid_narrative_bindings"][0]["description_readings"][0]
        self.assertEqual(reading["source_document_id"], "document-alpha")
        self.assertEqual(reading["physical_row_id"], "row-alpha")
        self.assertEqual(reading["document_year"], 2034)
        start, end = reading["quote_span"]
        self.assertEqual(self.catalog[0]["source_text"][start:end], "Regional outlets")
        self.assertEqual((self.catalog, self.program), before)
        self.assertEqual(semantic_candidate_catalog_fingerprint(self.catalog), fingerprint)
        self.assertEqual(self.catalog[0]["period"], "")

    def test_legacy_binding_does_not_silently_acquire_description_authority(self):
        program = deepcopy(self.program)
        program["narrative_bindings"][0]["evidence_bindings"][0].pop("row_description_quote")
        result = self.validate(program)
        self.assertIn("candidate_requirement_scope_mismatch", {error["code"] for error in result["errors"]})

    def test_quote_must_be_exact_local_axis_text_not_cell_context_or_another_source(self):
        for quote in ("regional outlets", "Regional  outlets", "Routes", "23.4%", "Other channels", " "):
            with self.subTest(quote=quote):
                program = deepcopy(self.program)
                program["narrative_bindings"][0]["evidence_bindings"][0]["row_description_quote"] = quote
                result = self.validate(program)
                errors = [error for error in result["errors"] if error["code"] == "invalid_row_description_quote"]
                self.assertTrue(errors, result)
                self.assertEqual(errors[0]["candidate_id"], "cell")
                self.assertEqual(errors[0]["owner_id"], "routes-input")
                self.assertEqual(errors[0]["repair_action"], "repair_program")

    def test_document_and_physical_row_identity_are_required(self):
        for field in ("source_document_id", "physical_table_id", "physical_row_id", "year"):
            with self.subTest(field=field):
                catalog = deepcopy(self.catalog)
                catalog[0].pop(field)
                self.assertNotEqual(self.validate(catalog=catalog)["status"], "ready")

    def test_explicit_scope_conflicts_are_not_bridged_by_description(self):
        for change in ({"year": 2033}, {"period": "2033"}, {"company": "Other issuer"},
                       {"segment": "Other division"}):
            with self.subTest(change=change):
                catalog, owners = deepcopy(self.catalog), deepcopy(self.owners)
                catalog[0].update(change)
                if "segment" in change:
                    owners[0]["scope"]["segment"] = "Requested division"
                self.assertNotEqual(self.validate(catalog=catalog, owners=owners)["status"], "ready")

    def test_reading_does_not_authorize_raw_cell_or_numbers_elsewhere_in_row(self):
        for text in ("Partners account for 23.4%.", "Partners account for 23.4.", "They serve 81 outlets."):
            with self.subTest(text=text):
                self.catalog[0]["source_text"] += " Other measurement 81."
                program = deepcopy(self.program)
                program["narrative_bindings"][0]["text"] = text
                self.assertIn("ungrounded_narrative_number", {error["code"] for error in self.validate(program)["errors"]})

    def test_number_in_exact_descriptor_is_not_a_blanket_numeric_text_ban(self):
        self.catalog[0]["row_headers"] = ["Series 7 outlets"]
        self.catalog[0]["source_text"] = "Series 7 outlets | share 23.4%"
        binding = self.program["narrative_bindings"][0]
        binding["evidence_bindings"][0]["row_description_quote"] = "Series 7 outlets"
        binding["text"] = "Partners use Series 7 outlets."
        self.assertEqual(self.validate()["status"], "ready")

    def test_scalar_token_cannot_be_laundered_through_row_header(self):
        self.catalog[0]["row_headers"] = ["Regional outlets 23.4%"]
        self.catalog[0]["source_text"] = "Regional outlets 23.4% | share 23.4%"
        self.program["narrative_bindings"][0]["evidence_bindings"][0]["row_description_quote"] = "Regional outlets 23.4%"
        self.assertIn("invalid_row_description_quote", {error["code"] for error in self.validate()["errors"]})

    def test_description_cannot_witness_another_numeric_cells_missing_period(self):
        # No input requirements: each ordinary scalar use still needs its own
        # measurement period, even beside a document-scoped reading.
        self.owners[0]["evidence_requirements"] = []
        binding = self.program["narrative_bindings"][0]
        binding["evidence_bindings"][0]["source_requirement_id"] = ""
        other = {**deepcopy(self.catalog[0]), "candidate_id": "other"}
        self.catalog.append(other)
        binding["evidence_bindings"].append({"candidate_id": "other"})
        binding["text"] = "Partners distribute through regional outlets; the share is 23.4%."
        def validate():
            return validate_semantic_calculation_program(program=self.program, obligations=self.owners,
                candidate_catalog=self.catalog, query="Describe routes.")
        result = validate()
        self.assertNotEqual(result["status"], "ready")
        self.assertTrue(any(error["candidate_id"] == "other" and "period" in error["detail"] for error in result["errors"]))
        other.update(period="2034")
        self.assertEqual(validate()["status"], "ready")

    def test_real_parser_scalar_row_description_keeps_catalog_identity(self):
        from tests.test_table_reading_evidence import TableReadingEvidenceTests
        _, _, catalog = TableReadingEvidenceTests().project([("Alpha", "partner locations", "35%")])
        row = next(item for item in catalog if item["kind"] == "numeric")
        before = deepcopy(catalog)
        owners = [_obligation("routes", "narrative", "Describe locations.", scope=_scope(company="Example", period="2041"))]
        program = {"narrative_bindings": [{"obligation_id": "routes", "text": "Alpha uses partner locations.",
            "evidence_bindings": [{"candidate_id": row["candidate_id"], "row_description_quote": "partner locations"}]}]}
        result = validate_semantic_calculation_program(program=program, obligations=owners,
            candidate_catalog=catalog, query="Describe locations.")
        self.assertEqual(result["status"], "ready", result["errors"])
        self.assertEqual(catalog, before)

    def test_owner_and_requirement_visibility_remain_required(self):
        self.assertIn("candidate_not_exposed_to_compiler", {error["code"] for error in self.validate(visible=False)["errors"]})
        program = deepcopy(self.program)
        program["narrative_bindings"][0]["evidence_bindings"][0]["source_requirement_id"] = "invented"
        self.assertIn("unknown_narrative_requirement", {error["code"] for error in self.validate(program)["errors"]})

    def test_same_candidate_has_no_numeric_period_authority(self):
        for unit in ("%", "USD"):
            with self.subTest(unit=unit):
                owners = [_obligation("amount", "direct_value", "Share", scope=self.scope, display_unit=unit)]
                result = validate_semantic_calculation_program(program={"direct_bindings": [
                    {"obligation_id": "amount", "candidate_id": "cell"}]}, obligations=owners,
                    candidate_catalog=self.catalog, query="Return the value.")
                self.assertNotEqual(result["status"], "ready")
                self.assertTrue(any("period" in error["detail"] for error in result["errors"]))
                if unit == "USD":
                    self.assertTrue(any("unit" in error["code"] for error in result["errors"]))

    def test_model_compiler_and_executor_keep_description_out_of_numeric_operands(self):
        program = self.claimed_program(self.program)
        llm = _StructuredQueueLLM(program)
        state = _case_state({"question": "Describe routes.", "obligations": self.owners}, self.catalog)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 1)
        execution = execute_semantic_calculation_program(program=compiled["semantic_program"],
            obligations=self.owners, candidate_catalog=self.catalog, query=state["query"],
            compilation_envelope=compiled["semantic_compilation_envelope"], require_compilation_envelope=True)
        self.assertEqual(execution["status"], "ok", execution)
        self.assertEqual(execution["calculation_operands"], [])
        self.assertEqual(execution["outputs"][0]["description_readings"][0]["quote"], "Regional outlets")
        evidence = FinancialAgentCalculationMixin._semantic_program_evidence_items(self.catalog,
            execution["selected_candidate_ids"], validation=execution["validation"])[0]
        self.assertEqual(evidence["quote_span"], "Regional outlets")
        self.assertEqual(evidence["raw_value"], "")
        self.assertEqual(evidence["raw_unit"], "")
        self.assertTrue(evidence["metadata"]["description_readings"])
        catalog = deepcopy(self.catalog)
        catalog[0]["row_headers"] = ["Different outlets"]
        drift = execute_semantic_calculation_program(program=compiled["semantic_program"],
            obligations=self.owners, candidate_catalog=catalog, query=state["query"],
            compilation_envelope=compiled["semantic_compilation_envelope"], require_compilation_envelope=True)
        self.assertEqual(drift["validation"]["errors"][0]["code"], "execution_content_mismatch")

    def test_same_cell_used_numerically_elsewhere_stays_in_operand_trace(self):
        self.catalog[0]["period"] = "2034"
        self.owners.append(_obligation("share", "direct_value", "Share", scope=self.scope, display_unit="%"))
        self.program["direct_bindings"] = [{"obligation_id": "share", "candidate_id": "cell"}]
        execution = execute_semantic_calculation_program(program=self.program, obligations=self.owners,
            candidate_catalog=self.catalog, query="Describe routes and share.")
        self.assertEqual(execution["status"], "ok", execution)
        self.assertEqual([row["candidate_id"] for row in execution["calculation_operands"]], ["cell"])
        evidence = FinancialAgentCalculationMixin._semantic_program_evidence_items(self.catalog,
            execution["selected_candidate_ids"], validation=execution["validation"])[0]
        self.assertEqual(evidence["raw_value"], "23.4")

    def test_bad_quote_retries_same_cohort_without_touching_other_island(self):
        self.owners.insert(0, _obligation("count", "direct_value", "Count"))
        self.catalog.append(_candidate("count-cell", 9))
        accepted = SemanticCalculationProgram.model_validate({"direct_bindings": [{"obligation_id": "count", "candidate_id": "count-cell"}]})
        bad = deepcopy(self.program)
        bad["narrative_bindings"][0]["evidence_bindings"][0]["row_description_quote"] = "Invented quote"
        llm = _StructuredQueueLLM(accepted, self.claimed_program(bad), self.claimed_program(self.program))
        state = _case_state({"question": "Return count and describe routes.", "obligations": self.owners}, self.catalog)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(json.dumps(compiled["semantic_program"]["direct_bindings"], sort_keys=True),
            json.dumps(accepted.model_dump()["direct_bindings"], sort_keys=True))
        def visible_payload(prompt):
            text = prompt.to_messages()[0].content.split("Source bundles, candidate cohorts, and candidates_by_id:\n", 1)[1]
            return json.JSONDecoder().raw_decode(text.lstrip())[0]
        self.assertEqual(visible_payload(llm.prompts[1]), visible_payload(llm.prompts[2]))

    def claimed_program(self, program):
        return SemanticCalculationProgram.model_validate(_with_narrative_claims(program,
            subject="Partners", quotes={"cell": "Partners | Regional outlets"}, catalog=self.catalog))


if __name__ == "__main__":
    unittest.main()
