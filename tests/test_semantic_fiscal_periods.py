"""Fiscal column precedence with real parser records and no provider/store writes."""

from copy import deepcopy

from lxml import etree

from tests.semantic_program_test_support import *
from src.processing.table_records import build_table_row_records, build_table_value_records
from src.processing.table_structure import build_table_object


def fiscal_source(row_label="비율[부분÷당기합계×100]"):
    table = build_table_object(etree.fromstring(f"""<TABLE><THEAD>
        <TR><TH>Metric</TH><TH>제55기</TH><TH>제54기</TH><TH>제53기</TH></TR></THEAD>
        <TBODY><TR><TD>{row_label}</TD><TD>15%</TD><TD>18%</TD><TD>21%</TD></TR></TBODY></TABLE>"""))
    rows = build_table_row_records(table, "%")
    values = build_table_value_records(rows, table_id="fiscal-table", unit_hint="%")
    return {"candidate_id": "fiscal-source", "candidate_kind": "structured_row",
        "source_anchor": "[sample | 2024 | table]", "text": row_label,
        "metadata": {"company": "sample", "year": 2024, "rcept_no": "fiscal-fixture",
            "table_source_id": "fiscal-table", "table_row_records_json": json.dumps(rows, ensure_ascii=False),
            "table_value_records_json": json.dumps(values, ensure_ascii=False)}}


def numeric_rows(source):
    return [row for row in _catalog_from_document(source["text"], source["metadata"]) if row["kind"] == "numeric"]


class FiscalPeriodPrecedenceTests(unittest.TestCase):
    def test_parser_row_relative_label_does_not_override_fiscal_columns(self):
        source = fiscal_source()
        before = deepcopy(source)
        values = json.loads(source["metadata"]["table_value_records_json"])
        self.assertEqual([row["period_text"] for row in values], ["당기"] * 3)
        catalog = numeric_rows(source)
        self.assertEqual([row["value_year"] for row in catalog], [2024, 2023, 2022])
        self.assertEqual([row["period"] for row in catalog], ["제55기", "제54기", "제53기"])
        self.assertEqual([row["period_source"] for row in catalog], ["fiscal_period"] * 3)
        self.assertEqual([row["source_period_surface"] for row in catalog], ["당기"] * 3)
        self.assertEqual([row["period_role"] for row in catalog], ["current", "prior", "prior"])
        self.assertEqual(source, before)

    def test_fiscal_columns_precede_relative_value_role_and_source_period(self):
        for marker in ("당기", "전기", "전전기"):
            source = fiscal_source(f"비율[부분÷{marker}합계×100]")
            source["metadata"].update(value_role="current", period_text="당기", period_labels=["2020"])
            with self.subTest(marker=marker):
                self.assertEqual([row["value_year"] for row in numeric_rows(source)], [2024, 2023, 2022])

    def test_explicit_calendar_labels_still_precede_fiscal_ordinals(self):
        source = fiscal_source()
        values = json.loads(source["metadata"]["table_value_records_json"])
        values[1]["column_headers"].append("2021년 12월말")
        source["metadata"]["table_value_records_json"] = json.dumps(values, ensure_ascii=False)
        prior = next(row for row in numeric_rows(source) if row["raw_value"] == "18%")
        self.assertEqual(prior["value_year"], 2021)
        self.assertEqual(prior["period_source"], "explicit_period")
        self.assertEqual(prior["source_period_surface"], "당기")

    def test_ambiguous_fiscal_columns_cannot_fall_back_to_relative_labels(self):
        source = fiscal_source()
        values = json.loads(source["metadata"]["table_value_records_json"])
        values[1]["column_headers"] = ["제54기 / 제53기"]
        source["metadata"]["table_value_records_json"] = json.dumps(values, ensure_ascii=False)
        prior = next(row for row in numeric_rows(source) if row["raw_value"] == "18%")
        self.assertIsNone(prior["value_year"])
        self.assertIn("제54기 / 제53기", prior["period_label_surfaces"])
        for period in ("2024", "2023", "당기"):
            owner = _obligation("amount", "direct_value", "quantity", scope=_scope(period=period))
            self.assertEqual(semantic_candidate_applicability(prior, owner)["state"], "unknown_only")

    def test_unanchored_fiscal_columns_do_not_borrow_row_relative_identity(self):
        source = fiscal_source()
        source["metadata"]["year"] = None
        for row in numeric_rows(source):
            self.assertIsNone(row["value_year"])
            for candidate in (row, {key: value for key, value in row.items() if key != "value_year"}):
                for period in ("2024", "당기"):
                    owner = _obligation("amount", "direct_value", "quantity", scope=_scope(period=period))
                    self.assertEqual(semantic_candidate_applicability(candidate, owner)["state"], "unknown_only")

    def test_owner_visibility_prompt_and_execution_use_fiscal_year(self):
        from src.agent.financial_runtime_contracts import CompilationEnvelopeV2

        catalog = numeric_rows(fiscal_source())
        owners = [_obligation(f"amount-{year}", "direct_value", "quantity", display_unit="%",
                             scope=_scope(period=str(year))) for year in (2024, 2023, 2022)]
        cohorts = _semantic_candidate_cohorts(catalog, owners)
        payload = FinancialAgent._semantic_program_prompt_payload(catalog, cohorts)
        for owner, row in zip(owners, catalog):
            self.assertEqual(cohorts["candidate_ids_by_owner"][owner["obligation_id"]], [row["candidate_id"]])
            self.assertEqual(payload["candidates_by_id"][row["candidate_id"]]["value_year"], row["value_year"])
        visibility = _semantic_candidate_visibility(catalog,
            visible_candidate_ids=cohorts["visible_candidate_ids"], candidate_ids_by_owner=cohorts["candidate_ids_by_owner"])
        program = {"status": "ready", "direct_bindings": [
            {"obligation_id": owner["obligation_id"], "candidate_id": row["candidate_id"]}
            for owner, row in zip(owners, catalog)]}
        inputs = dict(program=program, obligations=owners, candidate_catalog=catalog, query="Return annual quantities.")
        validation = validate_semantic_calculation_program(**inputs, candidate_visibility=visibility)
        envelope = CompilationEnvelopeV2.create(visibility=visibility, validation=validation, **inputs)
        result = execute_semantic_calculation_program(**inputs,
            compilation_envelope=envelope, require_compilation_envelope=True)
        self.assertEqual(result["status"], "ok", validation["errors"])
        self.assertEqual([row["value_year"] for row in result["calculation_operands"]], [2024, 2023, 2022])
        changed = deepcopy(catalog)
        changed[1]["value_year"] = 2024
        self.assertEqual(semantic_candidate_catalog_fingerprint(changed), semantic_candidate_catalog_fingerprint(catalog))
        blocked = execute_semantic_calculation_program(**{**inputs, "candidate_catalog": changed},
            compilation_envelope=envelope, require_compilation_envelope=True)
        self.assertEqual(blocked["validation"]["errors"][0]["code"], "execution_content_mismatch")

    def test_record_order_does_not_change_identity_or_period_projection(self):
        source = fiscal_source()
        before = numeric_rows(source)
        self.assertEqual([row["candidate_id"] for row in before], [
            "cand_93418454ebf512eddc43", "cand_b3a42005ba3d94dabd8d", "cand_d92652ed4eca20dca867"])
        self.assertEqual(semantic_candidate_catalog_fingerprint(before),
                         "d845bf4f67d429243f1a6aac98e588ae7d18fdd57834174fe8f6ca69a8bbe881")
        for key in ("table_row_records_json", "table_value_records_json"):
            source["metadata"][key] = json.dumps(list(reversed(json.loads(source["metadata"][key]))), ensure_ascii=False)
        after = numeric_rows(source)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
