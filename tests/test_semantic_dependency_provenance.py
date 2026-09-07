"""Arithmetic inputs retain immediate references and transitive source provenance."""

from copy import deepcopy
import unittest

from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from tests.semantic_program_test_support import (
    _binding, _candidate, _obligation, _requirement, _scope,
    _semantic_candidate_visibility, _source_display_program_fixture,
    execute_semantic_calculation_program, validate_semantic_calculation_program,
)


def _expression(owner, bindings, formula="A - B"):
    return {
        "obligation_id": owner, "variable_bindings": bindings, "formula": formula,
        "source_display_candidate_id": None,
        "source_display_reason": "No independently stated result.",
    }


def _difference_case(sources):
    catalog = [_candidate("left", 120, period="2024", context="statement"),
               _candidate("right", 20, period="2024", context="note")]
    for candidate in catalog:
        candidate.update(physical_table_id=candidate["table_source_id"],
                         physical_row_id=candidate["source_row_id"],
                         physical_cell_id=f"cell-{candidate['candidate_id']}")
    requirements, dependencies, bindings = [], [], []
    for variable, source in zip(("A", "B"), sources):
        requirement_id = ""
        if source in {"left", "right"}:
            requirement_id = f"net:req_{variable}"
            requirements.append(_requirement(requirement_id, source, period="2024"))
        elif source not in dependencies:
            dependencies.append(source)
        bindings.append(_binding(variable, source, requirement_id))
    return {
        "query": "Subtract the second amount from the first.", "candidate_catalog": catalog,
        "obligations": [
            _obligation("reported", "direct_value", "reported result", scope=_scope(period="2024")),
            _obligation("component", "direct_value", "included amount", scope=_scope(period="2024")),
            _obligation("net", "derived_value", "net result", depends_on=dependencies,
                        evidence_requirements=requirements),
        ],
        "program": {"status": "ready", "direct_bindings": [
            {"obligation_id": "reported", "candidate_id": "left"},
            {"obligation_id": "component", "candidate_id": "right"}],
            "expressions": [_expression("net", bindings)]},
    }


class SemanticDependencyProvenanceTests(unittest.TestCase):
    def execute(self, case):
        before = deepcopy(case)
        result = execute_semantic_calculation_program(**case)
        self.assertEqual(case, before)
        self.assertEqual(result["status"], "ok", result["validation"]["errors"])
        return result

    def test_candidate_dependency_and_mixed_inputs_share_one_record_per_variable(self):
        for sources, kinds in (
            (("left", "right"), ["candidate", "candidate"]),
            (("reported", "component"), ["obligation", "obligation"]),
            (("reported", "right"), ["obligation", "candidate"]),
        ):
            with self.subTest(sources=sources):
                case = _difference_case(sources)
                case["candidate_catalog"][0]["source_period_surface"] = "reported column"
                result = self.execute(case)
                output = result["outputs_by_obligation"]["net"]
                self.assertEqual(output["normalized_value"], 100)
                rows = output["input_rows"]
                self.assertEqual(len(rows), 2)
                self.assertEqual([row["variable"] for row in rows], ["A", "B"])
                self.assertEqual([row["source_id"] for row in rows], list(sources))
                self.assertEqual([row["source_kind"] for row in rows], kinds)
                self.assertEqual([row["normalized_value"] for row in rows], [120, 20])
                self.assertEqual([row["normalized_unit"] for row in rows], ["COUNT", "COUNT"])
                self.assertEqual([row["input_candidate_ids"] for row in rows], [["left"], ["right"]])
                self.assertEqual([row["period"] for row in rows], ["2024", "2024"])
                self.assertEqual([row["physical_cell_id"] for row in rows], ["cell-left", "cell-right"])
                provenance = output["calculated_provenance"]
                self.assertEqual(provenance["input_candidate_ids"], ["left", "right"])
                self.assertEqual(provenance["source_row_ids"], output["source_row_ids"])
                self.assertEqual(provenance["source_anchors"], output["source_anchors"])
                self.assertIn("Inputs:", result["answer"])
                if kinds[0] == "obligation":
                    self.assertEqual(rows[0]["source_period_surface"], "reported column")
                    self.assertIn("2024 reported result 120items", result["answer"])
                    self.assertNotIn("reported column", result["answer"])

    def test_multi_hop_inputs_use_calculated_values_and_exclude_display_witness(self):
        case = _source_display_program_fixture()
        for owner, source in (("middle", "ob_change"), ("last", "middle")):
            case["obligations"].append(_obligation(
                owner, "derived_value", owner, display_unit="%", depends_on=[source]))
            case["program"]["expressions"].append(_expression(
                owner, [_binding("X", source)], "X + X"))
        result = self.execute(case)
        first = result["outputs_by_obligation"]["ob_change"]
        self.assertEqual(first["display_value"], 10.2)
        for owner, source, input_value, output_value in (
            ("middle", "ob_change", 10, 20), ("last", "middle", 20, 40),
        ):
            with self.subTest(owner=owner):
                output = result["outputs_by_obligation"][owner]
                self.assertEqual(output["normalized_value"], output_value)
                self.assertEqual(len(output["input_rows"]), 1)
                row = output["input_rows"][0]
                self.assertEqual((row["variable"], row["source_id"], row["source_kind"]),
                                 ("X", source, "obligation"))
                self.assertEqual(row["normalized_value"], input_value)
                self.assertEqual(row["rendered_value"], f"{input_value}%")
                self.assertFalse(row.get("candidate_id"))
                self.assertFalse(row.get("physical_cell_id"))
                self.assertIn("cand-stated", output["candidate_ids"])
                for provenance in (row, output["calculated_provenance"]):
                    self.assertEqual(provenance["input_candidate_ids"], ["cand-opening", "cand-closing"])
                    self.assertNotIn("cand-stated", provenance["source_row_ids"])
                    self.assertNotIn("[sample | 2024 | source note]", provenance["source_anchors"])
        self.assertIn("quantity change 10%", result["answer"])

    def test_derived_and_candidate_inputs_keep_distinct_sources(self):
        case = _difference_case(("reported", "component"))
        case["candidate_catalog"].append(_candidate("offset", 2, period="2024"))
        case["obligations"].append(_obligation(
            "adjusted", "derived_value", "adjusted", depends_on=["net"],
            evidence_requirements=[_requirement("offset_req", "offset", period="2024")]))
        case["program"]["expressions"].append(_expression(
            "adjusted", [_binding("A", "net"), _binding("B", "offset", "offset_req")], "A + B"))
        output = self.execute(case)["outputs_by_obligation"]["adjusted"]
        self.assertEqual(output["normalized_value"], 102)
        self.assertEqual([row["normalized_value"] for row in output["input_rows"]], [100, 2])
        self.assertEqual(output["calculated_provenance"]["input_candidate_ids"],
                         ["left", "right", "offset"])

    def test_repeated_input_keeps_variable_occurrences_but_dedupes_source_lineage(self):
        for source in ("left", "reported"):
            with self.subTest(source=source):
                case = _difference_case((source, source))
                case["program"]["expressions"][0]["formula"] = "A + B"
                output = self.execute(case)["outputs_by_obligation"]["net"]
                self.assertEqual(output["normalized_value"], 240)
                rows = output["input_rows"]
                self.assertEqual([row["variable"] for row in rows], ["A", "B"])
                self.assertEqual(output["calculated_provenance"]["input_candidate_ids"], ["left"])
                rows[0]["source_row_ids"].append("mutated")
                self.assertNotIn("mutated", rows[1]["source_row_ids"])
                self.assertNotIn("mutated", output["calculated_provenance"]["source_row_ids"])

    def test_compatibility_evidence_is_not_an_arithmetic_input(self):
        case = _difference_case(("reported", "component"))
        witness = {**_candidate("witness", 0, context="statement"), "kind": "narrative",
                   "normalized_value": None, "source_anchor": "[witness note]",
                   "source_text": "The second amount is included in the first amount."}
        case["candidate_catalog"].append(witness)
        case["program"]["direct_bindings"][0]["compatibility_candidate_ids"] = ["witness"]
        case["program"]["expressions"][0]["compatibility_candidate_ids"] = ["witness"]
        result = self.execute(case)
        for owner, ids in (("reported", ["left"]), ("net", ["left", "right"])):
            output = result["outputs_by_obligation"][owner]
            self.assertIn("witness", output["candidate_ids"])
            self.assertEqual(output["calculated_provenance"]["input_candidate_ids"], ids)
            self.assertNotIn("witness", output["calculated_provenance"]["source_row_ids"])
            self.assertNotIn("[witness note]", output["calculated_provenance"]["source_anchors"])

    def test_unavailable_dependency_creates_no_output_or_fabricated_provenance(self):
        case = _source_display_program_fixture()
        case["program"]["expressions"][0]["formula"] = "OPEN / (CLOSE - CLOSE) * 100"
        case["obligations"].append(_obligation("next", "derived_value", "next", depends_on=["ob_change"]))
        case["program"]["expressions"].append(_expression("next", [_binding("X", "ob_change")], "X + X"))
        result = execute_semantic_calculation_program(**case)
        self.assertEqual(result["validation"]["status"], "ready")
        self.assertEqual(result["outputs_by_obligation"], {})
        self.assertEqual({error["code"] for error in result["execution_errors"]},
                         {"zero_division", "unavailable_expression_source"})

    def test_direct_dependencies_preserve_source_sign_and_scale(self):
        for raw_value, unit, normalized in (("(1)", "백만달러", -1_000_000), ("9", "만 대", 90_000)):
            with self.subTest(unit=unit):
                case = _difference_case(("reported", "component"))
                case["candidate_catalog"] = [
                    _candidate("left", raw_value, raw_unit=unit, period="2024"),
                    _candidate("right", 2, raw_unit=unit, period="2024"),
                ]
                result = self.execute(case)
                output = result["outputs_by_obligation"]["net"]
                row = output["input_rows"][0]
                self.assertEqual((row["raw_value"], row["raw_unit"], row["normalized_value"]),
                                 (raw_value, unit, normalized))
                self.assertEqual(row["rendered_value"], result["outputs_by_obligation"]["reported"]["rendered_value"])
                self.assertEqual(output["normalized_value"], normalized - case["candidate_catalog"][1]["normalized_value"])

    def test_authorized_context_and_physical_provenance_survive_dependency_projection(self):
        from tests.test_semantic_document_context import parsed_catalog, value, context_binding

        _, catalog = parsed_catalog()
        selected = value(catalog)
        case = {
            "query": "2024 value and twice that value", "candidate_catalog": catalog,
            "obligations": [_obligation("reported", "direct_value", "reported", scope=_scope(period="2024")),
                            _obligation("twice", "derived_value", "twice", depends_on=["reported"])],
            "program": {"status": "ready", "direct_bindings": [{"obligation_id": "reported",
                "candidate_id": selected["candidate_id"], "context_bindings": [context_binding(selected)]}],
                "expressions": [_expression("twice", [_binding("X", "reported")], "X + X")]},
        }
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=[selected["candidate_id"]],
            candidate_ids_by_owner={"reported": [selected["candidate_id"]], "twice": []})
        validation = validate_semantic_calculation_program(**case, candidate_visibility=visibility)
        self.assertEqual(validation["status"], "ready", validation["errors"])
        envelope = CompilationEnvelopeV2.create(visibility=visibility, validation=validation, **case)
        before = deepcopy(case)
        result = execute_semantic_calculation_program(**case, compilation_envelope=envelope,
                                                      require_compilation_envelope=True)
        self.assertEqual(case, before)
        row = result["outputs_by_obligation"]["twice"]["input_rows"][0]
        operand = result["calculation_operands"][0]
        for field in ("context_resolution", "period", "value_year", "period_source", "row_headers",
                      "physical_table_id", "physical_row_id", "physical_cell_id", "raw_value", "raw_unit"):
            self.assertEqual(row[field], operand[field])
        self.assertEqual(row["period_source"], "source_context_binding")
        self.assertEqual(row["source_id"], "reported")
        row["context_resolution"]["scope"]["period"] = "changed"
        self.assertEqual(case, before)
        self.assertEqual(operand["context_resolution"]["scope"]["period"], "2024")


if __name__ == "__main__":
    unittest.main()
