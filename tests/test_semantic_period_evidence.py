"""Value-period evidence is distinct from filing year and unbound table hints."""

from copy import deepcopy

from tests.semantic_program_test_support import *
from src.processing.financial_parser import _infer_period_focus


def period_source(*, labels=(), period_text="", header="Reported amount"):
    return {
        "candidate_id": "period-evidence-row",
        "candidate_kind": "structured_row",
        "source_anchor": "[sample | 2024 | note]",
        "text": "quantity | 10%",
        "metadata": {
            "company": "sample", "year": 2024, "table_source_id": "period-table",
            "row_label": "quantity", "period_labels": list(labels),
            "period_focus": _infer_period_focus(list(labels)),
            "structured_cells": [{"column_headers": [header],
                                  "period_text": period_text, "value_text": "10%"}],
        },
    }


def numeric(source):
    return next(c for c in build_semantic_candidate_catalog([source]) if c["kind"] == "numeric")


class ValuePeriodEvidenceTests(unittest.TestCase):
    def test_filing_year_is_not_an_unknown_numeric_values_period(self):
        for period in ("", "Reported amount", "Organization / business description"):
            for kind in ("structured_value", "sentence_value"):
                candidate = {**_candidate("unknown", 10, period=period), "candidate_kind": kind}
                for year in (2024, 2023, 2022):
                    owner = _obligation("value", "direct_value", "quantity", scope=_scope(period=str(year)))
                    with self.subTest(period=period, kind=kind, year=year):
                        result = semantic_candidate_applicability(candidate, owner)
                        self.assertEqual(result["state"], "unknown_only")

    def test_unlocated_table_labels_and_parser_focus_are_hints_not_cell_evidence(self):
        for labels in ((), ("당기",), ("전기",), ("전기", "2023"), ("2023",),
                       ("당기", "당기말", "2024"), ("당기", "전기"), ("2024", "2023")):
            with self.subTest(labels=labels):
                source = period_source(labels=labels)
                before = deepcopy(source)
                candidate = numeric(source)
                self.assertEqual(candidate["period"], "")
                self.assertIsNone(candidate["value_year"])
                self.assertEqual(candidate["period_role"], "")
                self.assertEqual(candidate["source_period_surface"], "Reported amount")
                self.assertEqual(candidate["column_headers"], ["Reported amount"])
                self.assertEqual(candidate["period_label_surfaces"], list(labels))
                self.assertEqual(candidate["period_label_scope"], "unbound_table")
                self.assertEqual(candidate["candidate_id"], "cand_808be8548f5a7e9d67f1")
                for year in (2023, 2024):
                    owner = _obligation("value", "direct_value", "quantity", scope=_scope(period=str(year)))
                    self.assertEqual(semantic_candidate_applicability(candidate, owner)["state"], "unknown_only")
                self.assertEqual(source, before)

    def test_located_period_text_resolves_equivalent_labels_once(self):
        for text, year in (("당기 / 당기말 / 2024", 2024), ("전기 / 2023", 2023),
                           ("전기 / 전기말", 2023), ("2021 전기", 2021)):
            for location in ("cell", "source"):
                with self.subTest(text=text, location=location):
                    source = period_source(labels=("2020", "당기", "전기"))
                    target = (source["metadata"]["structured_cells"][0]
                              if location == "cell" else source["metadata"])
                    target["period_text"] = text
                    candidate = numeric(source)
                    self.assertEqual(candidate["value_year"], year)
                    owner = _obligation("value", "direct_value", "quantity", scope=_scope(period=str(year)))
                    self.assertEqual(semantic_candidate_applicability(candidate, owner)["state"], "compatible")

    def test_ambiguous_cell_years_do_not_match_either_year(self):
        for text in ("2024 / 2023", "당기 / 전기"):
            candidate = numeric(period_source(period_text=text))
            self.assertIsNone(candidate["value_year"])
            for year in (2024, 2023):
                owner = _obligation("value", "direct_value", "quantity", scope=_scope(period=str(year)))
                self.assertEqual(semantic_candidate_applicability(candidate, owner)["state"], "unknown_only")

    def test_unbound_dates_in_body_cannot_override_a_cell_period(self):
        source = period_source(labels=("당기", "2020", "2024"), period_text="전기")
        source["text"] += " The rule became effective in 2020."
        candidate = numeric(source)
        self.assertEqual(candidate["value_year"], 2023)

    def test_explicit_cell_period_precedes_source_period_and_survives_execution(self):
        from src.agent.financial_runtime_contracts import CompilationEnvelopeV2

        source = period_source(period_text="2023")
        source["metadata"]["period_text"] = "2024"
        candidate = numeric(source)
        self.assertEqual(candidate["value_year"], 2023)
        self.assertEqual(candidate["period_source"], "explicit_period")
        owner = _obligation("value", "direct_value", "quantity", scope=_scope(period="2023"))
        catalog = [candidate]
        cohort = _semantic_candidate_cohorts(catalog, [owner])
        payload = FinancialAgent._semantic_program_prompt_payload(catalog, cohort)
        visible = _semantic_candidate_visibility(catalog,
            visible_candidate_ids=cohort["visible_candidate_ids"],
            candidate_ids_by_owner=cohort["candidate_ids_by_owner"])
        program = {"status": "ready", "direct_bindings": [
            {"obligation_id": "value", "candidate_id": candidate["candidate_id"]}]}
        inputs = dict(program=program, obligations=[owner], candidate_catalog=catalog, query="Return the 2023 value.")
        validation = validate_semantic_calculation_program(**inputs, candidate_visibility=visible)
        envelope = CompilationEnvelopeV2.create(visibility=visible, validation=validation, **inputs)
        execution = execute_semantic_calculation_program(**inputs,
            compilation_envelope=envelope, require_compilation_envelope=True)
        self.assertEqual(execution["status"], "ok", validation["errors"])
        operand = execution["calculation_operands"][0]
        prompt_row = payload["candidates_by_id"][candidate["candidate_id"]]
        for field in ("period", "value_year", "source_period_surface", "period_label_scope", "period_label_surfaces"):
            self.assertEqual(operand[field], candidate[field])
            self.assertEqual(prompt_row[field], candidate[field])

    def test_explicit_source_year_does_not_require_a_filing_year_anchor(self):
        source = period_source()
        source["metadata"].update(year=None, period_text="2021")
        candidate = numeric(source)
        self.assertEqual(candidate["value_year"], 2021)
        self.assertEqual(candidate["period_label_scope"], "source_period")

    def test_role_word_prefixes_are_not_temporal_labels(self):
        for header in ("currentness", "closing remarks", "prioritization", "begin analysis", "전기차"):
            with self.subTest(header=header):
                self.assertIsNone(numeric(period_source(header=header))["value_year"])

    def test_calendar_column_overrides_relative_text_from_row_axis(self):
        source = period_source(period_text="당기")
        source["metadata"]["structured_cells"][0]["column_headers"] = ["제24기", "(2022년 12월말)"]
        candidate = numeric(source)
        self.assertEqual(candidate["period"], "2022")
        self.assertEqual(candidate["value_year"], 2022)
        self.assertEqual(candidate["period_source"], "explicit_period")
        self.assertEqual(candidate["source_period_surface"], "당기")
        self.assertIn("(2022년 12월말)", candidate["period_label_surfaces"])
        current = _obligation("current", "direct_value", "quantity", scope=_scope(period="당기"))
        self.assertEqual(semantic_candidate_applicability(candidate, current)["state"], "explicit_conflict")

    def test_header_title_is_not_an_executable_period(self):
        for header in ("공시금액", "Organization / business description"):
            candidate = numeric(period_source(header=header))
            self.assertEqual(candidate["period"], "")
            self.assertEqual(candidate["source_period_surface"], header)

    def test_explicit_period_precedes_unknown_regardless_of_filing_year(self):
        unknown = {**_candidate("unknown", 10), "year": 2023}
        known = {**_candidate("known", 10, period="2024"), "year": 2025}
        owner = _obligation("value", "direct_value", "quantity", scope=_scope(period="2024"))
        cohort = _semantic_candidate_cohorts([unknown, known], [owner])["cohorts"][0]
        self.assertEqual(cohort["candidate_ids"], ["known", "unknown"])

    def test_unknown_period_rejects_execution_without_replacing_candidate(self):
        candidate = numeric(period_source())
        owner = _obligation("value", "direct_value", "quantity", scope=_scope(period="2024"))
        program = {"status": "ready", "direct_bindings": [
            {"obligation_id": "value", "candidate_id": candidate["candidate_id"]}]}
        result = execute_semantic_calculation_program(program=program, obligations=[owner],
            candidate_catalog=[candidate], query="Return the 2024 quantity.")
        self.assertNotIn("value", result["outputs_by_obligation"])
        errors = [e for e in result["validation"]["errors"] if e["code"] == "candidate_scope_mismatch"]
        self.assertTrue(errors)
        self.assertTrue(all(e["repair_action"] == "repair_program" for e in errors))

    def test_filing_only_narrative_cannot_launder_numeric_period(self):
        catalog = _catalog_from_document("The reported proportion is 20%.",
                                         {"company": "sample", "year": 2024, "is_table": False})
        value = next(c for c in catalog if c["kind"] == "numeric")
        witness = next(c for c in catalog if c["kind"] == "narrative")
        owner = _obligation("value", "direct_value", "quantity", scope=_scope(period="2024"))
        program = {"status": "ready", "direct_bindings": [{
            "obligation_id": "value", "candidate_id": value["candidate_id"],
            "compatibility_candidate_ids": [witness["candidate_id"]],
            "compatibility_reason": "Same filing."}],
            "source_assertions": _source_assertions(catalog, value["candidate_id"])}
        validation = validate_semantic_calculation_program(program=program, obligations=[owner],
            candidate_catalog=catalog, query="Return the 2024 quantity.")
        self.assertNotEqual(validation["status"], "ready")

    def test_located_period_witness_can_bridge_only_its_own_source_context(self):
        value = _candidate("unknown", 10)
        witness = {**value, "candidate_id": "witness", "kind": "narrative", "period": "2023"}
        owner = _obligation("value", "direct_value", "quantity", scope=_scope(period="2023"))
        program = {"status": "ready", "direct_bindings": [{
            "obligation_id": "value", "candidate_id": "unknown",
            "compatibility_candidate_ids": ["witness"], "compatibility_reason": "Located period context."}]}
        validation = validate_semantic_calculation_program(program=program, obligations=[owner],
            candidate_catalog=[value, witness], query="Return the 2023 quantity.")
        self.assertEqual(validation["status"], "ready", validation["errors"])
        value["source_document_id"] = "filing-a"
        witness["source_document_id"] = "filing-b"
        rejected = validate_semantic_calculation_program(program=program, obligations=[owner],
            candidate_catalog=[value, witness], query="Return the 2023 quantity.")
        self.assertNotEqual(rejected["status"], "ready")


if __name__ == "__main__":
    unittest.main()
