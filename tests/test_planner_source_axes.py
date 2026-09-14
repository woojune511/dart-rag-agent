"""Source-aware planning transport, not an oracle for model name interpretation."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.agent.financial_graph_models import RequirementPlannerOutput
from src.agent.financial_source_axis_inventory import build_source_axis_inventory
from src.config.retrieval_policy import PLANNING_POLICY
from tests.semantic_program_test_support import _StructuredQueueLLM
from tests.test_planner_subject_projection import agent_for, authored_owner, cell, validate


def source_metadata(name="Birch", *, receipt="filing-A", table="table-A", **extra):
    rows = [{"row_id": "row-A", "row_label": "quantity", "row_headers": ["quantity"],
        "cells": [{"cell_id": "cell-A", "column_index": 1,
            "column_headers": ["Operating groups", name], "value_text": "23"}]}]
    return {"company": "Issuer", "year": 2042, "rcept_no": receipt, "table_source_id": table,
        "section_path": "II. Operations > 1. Overview", "table_row_records_json": json.dumps(rows), **extra}


class PlannerSourceAxesTests(unittest.TestCase):
    def test_existing_planner_call_receives_scoped_source_axes_before_fixing_targets(self):
        query = "Return 2042 quantity for the Birch unit, excluding transfers."
        response = RequirementPlannerOutput.model_validate({"obligations": [authored_owner(["Birch"],
            scope={"basis": "excluding transfers"})]})
        agent = agent_for(_StructuredQueueLLM(response))
        rows = [source_metadata(), source_metadata("Birch Services", receipt="filing-B")]
        agent.vsm = SimpleNamespace(bm25_metadatas=rows)
        state = {"query": query, "report_scope": {"company": "Issuer", "year": 2042, "rcept_no": "filing-A"}}
        before = deepcopy((rows, state, response.model_dump()))
        planned = agent._plan_answer_obligation_program(state)
        inventory = planned["semantic_plan"]["source_axis_inventory"]
        self.assertEqual(inventory["authority"], "planning_hint_only")
        columns = [row for row in inventory["axes"] if row["axis"] == "column"]
        self.assertEqual([row["headers"] for row in columns], [["Operating groups", "Birch"]])
        prompt = agent.llm.prompts[0].to_messages()[0].content
        self.assertEqual(len(agent.llm.prompts), 1)
        self.assertIn(json.dumps(inventory, ensure_ascii=False), prompt)
        self.assertNotIn("filing-B", prompt)
        self.assertNotIn("Birch Services", prompt)
        self.assertEqual((rows, state, response.model_dump()), before)
        self.assertEqual(planned["answer_obligations"][0]["semantic_target"]["local_subjects"], ["Birch"])
        self.assertEqual(planned["answer_obligations"][0]["scope"]["basis"], "excluding transfers")
        self.assertIn(query, prompt)
        candidate = cell("Birch", basis="excluding transfers")
        self.assertEqual(validate(query, planned["answer_obligations"], [candidate])["status"], "ready")

    def test_hierarchies_whole_names_and_exact_query_offsets_are_not_shortened(self):
        query = "🗂 별빛 연구소와 Birch and others의 quantity를 비교해 줘."
        sources = [source_metadata("Birch and others"), source_metadata("별빛 연구소"), source_metadata("별빛")]
        result = build_source_axis_inventory(sources, query=query)
        columns = [row for row in result["axes"] if row["axis"] == "column"]
        self.assertEqual({tuple(row["headers"]) for row in columns}, {
            ("Operating groups", "별빛"), ("Operating groups", "별빛 연구소"), ("Operating groups", "Birch and others")})
        for row in result["axes"]:
            for match in row["query_matches"]:
                self.assertEqual(query[slice(*match["query_span"])], row["headers"][match["header_index"]])
        # Seeing a short name inside a longer request is only a hint; code
        # has not established equivalence or authorized a shorter candidate.
        self.assertEqual(result["authority"], "planning_hint_only")

    def test_chunk_row_cell_order_and_repeated_attachments_do_not_change_inventory(self):
        rows = json.loads(source_metadata()["table_row_records_json"])
        rows += [{**deepcopy(rows[0]), "row_id": "row-B"}]
        rows[0]["cells"] += [{**rows[0]["cells"][0], "cell_id": "cell-B"}]
        first = source_metadata(table_row_records_json=json.dumps(rows))
        permuted = deepcopy(rows)
        permuted.reverse()
        for row in permuted:
            row["cells"].reverse()
        other = source_metadata(table_row_records_json=json.dumps(permuted))
        sources = [first, other, source_metadata(receipt="filing-B")]
        before = deepcopy(sources)
        result = build_source_axis_inventory(sources, query="Birch quantity")
        self.assertEqual(result, build_source_axis_inventory(list(reversed(sources)), query="Birch quantity"))
        self.assertEqual(result, build_source_axis_inventory([first, first, sources[-1]], query="Birch quantity"))
        self.assertEqual(result["visible_axis_count"], 4)
        result["axes"][0]["headers"].append("changed")
        result["axes"][0]["example_reference"]["row_id"] = "changed"
        self.assertEqual(sources, before)

    def test_no_scalar_body_company_or_generated_alias_becomes_an_axis(self):
        raw = source_metadata("Unmentioned")
        rows = json.loads(raw["table_row_records_json"])
        rows[0]["cells"][0]["value_text"] = "8675309"
        raw.update(table_row_records_json=json.dumps(rows), company="Birch", local_heading="Birch",
            source_text="Birch quantity is 8675309", source_contexts=[{"source_text": "Birch"}],
            table_value_labels_text="Birch", local_entity_surfaces=["Birch"])
        result = build_source_axis_inventory([raw], query="Birch 8675309")
        self.assertEqual(result["axes"], [])
        self.assertEqual(result["observed_axis_count"], 2)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["coverage"], "observed_query_literal_axes_only")

    def test_value_only_and_table_object_inputs_preserve_original_axis_references(self):
        value = {"value_id": "value-A", "row_headers": ["Cluster", "Birch"], "column_headers": ["quantity"],
            "semantic_label": "invented", "semantic_aliases": ["invented"], "value_text": "8675309"}
        variants = [source_metadata(table_row_records_json="", table_value_records_json=json.dumps([value])),
            source_metadata(table_row_records_json="", table_source_id="", table_object_json={"table_id": "table-A", "values": [value]})]
        for raw in variants:
            with self.subTest(raw=raw):
                before = deepcopy(raw)
                result = build_source_axis_inventory([raw], query="Birch quantity invented 8675309")
                self.assertEqual(result["visible_axis_count"], 2)
                self.assertEqual(result["axes"][0]["headers"], ["Cluster", "Birch"])
                self.assertEqual(result["axes"][0]["example_reference"], {"table_source_id": "table-A", "value_id": "value-A"})
                self.assertNotIn("8675309", json.dumps(result))
                self.assertNotIn("invented", json.dumps(result))
                self.assertEqual(raw, before)

    def test_byte_and_count_limits_never_cut_an_axis_or_claim_full_coverage(self):
        one = source_metadata()
        complete = build_source_axis_inventory([one], query="Birch")
        self.assertEqual(complete["visible_axis_count"], 1)
        boundary = complete["serialized_axes_bytes"]
        self.assertEqual(build_source_axis_inventory([one], query="Birch", max_bytes=boundary), complete)
        limited = build_source_axis_inventory([one], query="Birch", max_bytes=boundary - 1)
        self.assertEqual(limited["axes"], [])
        self.assertTrue(limited["truncated"])
        self.assertEqual(limited["omitted_matching_axis_count"], 1)
        two = [one, source_metadata(receipt="filing-B")]
        limited = build_source_axis_inventory(two, query="Birch", max_axes=1)
        self.assertEqual(limited, build_source_axis_inventory(list(reversed(two)), query="Birch", max_axes=1))
        self.assertEqual(limited["visible_axis_count"], 1)
        self.assertEqual(limited["omitted_matching_axis_count"], 1)

    def test_unlocated_missing_or_invalid_payloads_do_not_invent_provenance(self):
        rows = [source_metadata(rcept_no=""), source_metadata(table_source_id=""),
            source_metadata(table_row_records_json="invalid"), {"company": "Birch", "year": 2042}]
        result = build_source_axis_inventory(rows, query="Birch quantity")
        self.assertEqual(result["axes"], [])
        self.assertEqual(result["unlocated_metadata_count"], 2)
        self.assertEqual(build_source_axis_inventory([], query="Birch")["axes"], [])

    def test_inventory_never_rewrites_request_targets_and_source_linkage_is_not_semantic_truth(self):
        for subject, source in (("Birch unit", "Birch"), ("Birch Services", "Birch"),
                                ("Birch", "Birch and others")):
            with self.subTest(subject=subject):
                query = f"Return the 2042 quantity for {subject}."
                response = RequirementPlannerOutput.model_validate({"obligations": [authored_owner([subject])]})
                agent = agent_for(_StructuredQueueLLM(response))
                agent.vsm = SimpleNamespace(bm25_metadatas=[source_metadata(source)])
                planned = agent._plan_answer_obligation_program({"query": query,
                    "report_scope": {"company": "Issuer", "year": 2042}})
                owners = planned["answer_obligations"]
                self.assertEqual(owners[0]["semantic_target"]["local_subjects"], [subject])
                rejected = validate(query, owners, [cell(source)])
                self.assertEqual(rejected["status"], "ready")
                self.assertEqual(rejected["valid_direct_bindings"][0]["source_interpretation_resolution"]["validation_scope"],
                                 "source_linkage_not_semantic_equivalence")
                self.assertEqual(len(agent.llm.prompts), 1)

    def test_inventory_is_optional_reading_context_not_a_required_name_allowlist(self):
        query = "Return 2042 quantity for Aster."
        response = RequirementPlannerOutput.model_validate({"obligations": [authored_owner(["Aster"])]})
        projections = []
        for sources in ([], [source_metadata("Aster Services")], [source_metadata("Aster")]):
            agent = agent_for(_StructuredQueueLLM(response))
            agent.vsm = SimpleNamespace(bm25_metadatas=sources)
            projections.append(agent._plan_answer_obligation_program({"query": query,
                "report_scope": {"company": "Issuer", "year": 2042}})["answer_obligations"])
        self.assertEqual(projections[0], projections[1])
        self.assertEqual(projections[1], projections[2])
        self.assertEqual(validate(query, projections[0], [cell("Aster")])["status"], "ready")

    def test_identical_payloads_are_decoded_once_per_projection(self):
        from src.agent.financial_reconciliation_candidates import _table_record_bundle
        sources = [source_metadata() for _ in range(20)]
        with patch("src.agent.financial_source_axis_inventory._table_record_bundle", wraps=_table_record_bundle) as decode:
            build_source_axis_inventory(sources, query="Birch")
            self.assertEqual(decode.call_count, 1)

    def test_repeated_whole_axes_share_one_observed_example_not_repeated_prompt_text(self):
        sources = [source_metadata(table=f"table-{index:03d}") for index in range(20)]
        result = build_source_axis_inventory(sources, query="Birch")
        self.assertEqual(result["visible_axis_count"], 1)
        self.assertEqual(result["axes"][0]["example_reference"]["table_source_id"], "table-000")
        self.assertEqual(result, build_source_axis_inventory(list(reversed(sources)), query="Birch"))
        # A different filing/section or full axis is still a different reading.
        sources += [source_metadata(receipt="filing-B"), source_metadata(section_path="III. Notes"),
                    source_metadata("Birch and others")]
        self.assertEqual(build_source_axis_inventory(sources, query="Birch and others")["visible_axis_count"], 4)

    def test_changed_axis_content_changes_hint_fingerprint_not_model_output_schema(self):
        query = "Return Birch and Aster quantities."
        first = build_source_axis_inventory([source_metadata("Birch")], query=query)
        second = build_source_axis_inventory([source_metadata("Aster")], query=query)
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])
        self.assertNotIn("source_axis_inventory", RequirementPlannerOutput.model_json_schema()["properties"])
        prompt = PLANNING_POLICY["requirement_planner_prompt_template"]
        self.assertIn("source_axis_inventory", prompt)
        self.assertIn("선택 권한", prompt)


if __name__ == "__main__":
    unittest.main()
