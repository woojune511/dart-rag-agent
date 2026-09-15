"""Presentation is not candidate authority, semantic judging, or a new model call."""

from copy import deepcopy
from tests.narrative_address_test_support import model_program
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.agent.financial_compiler_presentation import EMPTY_SCALAR_FIELDS
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts, _merge_targeted_program_retry
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint
from src.agent.financial_source_bundles import build_semantic_source_bundles, semantic_source_bundle_fingerprint
from src.config.retrieval_policy import CALCULATION_PROMPT_POLICY
from src.processing.financial_parser import FinancialParser
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM
from tests.test_narrative_claim_grounding import source, claim
from tests.test_narrative_retry_context import prompt_json
from tests.compiler_presentation_test_support import bundle_text, context_surfaces, surface_text
from tests.test_located_heading_context import catalog as parsed_catalog


MARKER = "Source bundles, candidate cohorts, and candidates_by_id:"


def context(key, text, locator, relation="ancestor_heading", document="doc-a", span=None):
    return {"context_id": key, "source_text": text, "source_locator": locator,
            "parent_locator": locator.rsplit("/", 1)[0], "relation": relation,
            "document_sha256": document, "source_span": span or [0, len(text)]}


def all_keys(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(all_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(all_keys(v) for v in value))
    return set()


class CompilerReadingPresentationTests(unittest.TestCase):
    def setUp(self):
        self.heading = context("z-heading", "[Cedar]\t ", "/ROOT/SECTION/TITLE")
        self.catalog = [source("paragraph", "We use local partners.\r\n", company="Parent",
            source_document_id="doc-a", source_contexts=[self.heading],
            local_entity_surfaces=["We"], year=2037)]
        self.owners = [_obligation("routes", "narrative", "Describe routes and subject.")]

    def payload(self, catalog=None, owners=None):
        catalog = self.catalog if catalog is None else catalog
        owners = self.owners if owners is None else owners
        return FinancialAgent._semantic_program_prompt_payload(catalog, _semantic_candidate_cohorts(catalog, owners))

    def compile(self, programs, *, owners=None, catalog=None):
        llm = _StructuredQueueLLM(*[model_program(p, catalog or self.catalog) for p in programs])
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = llm
        result = agent._compile_semantic_calculation_program({
            "query": "Describe routes and identify the local subject; report size when requested.",
            "answer_obligations": owners or self.owners, "semantic_candidate_catalog": catalog or self.catalog,
            "semantic_candidate_catalog_prebuilt": True, "semantic_source_candidates": [],
        })
        return result, llm.prompts

    def program(self):
        row = claim("Cedar", "Uses local partners.", "paragraph", "We use local partners.")
        row["evidence_bindings"].append({"candidate_id": "paragraph", "context_id": "z-heading", "evidence_text": "Cedar"})
        return {"narrative_bindings": [{"obligation_id": "routes", "claims": [row]}]}

    def test_allowlists_remove_rank_and_future_diagnostics_without_mutating_trace(self):
        plan = _semantic_candidate_cohorts(self.catalog, self.owners)
        match = plan["candidate_match_by_id"]["paragraph"]["routes"]
        self.assertIn("rank_vector", match)
        match["future_diagnostic"] = {"rank_vector": [999], "score": 999}
        plan["cohorts"][0]["future_diagnostic"] = {"rank_vector": [998]}
        before = deepcopy((self.catalog, plan))
        payload = FinancialAgent._semantic_program_prompt_payload(self.catalog, plan)
        self.assertFalse({"rank_vector", "ranking_diagnostics", "future_diagnostic", "match_counts"} & all_keys(payload))
        self.assertEqual((self.catalog, plan), before)
        self.assertIn("ranking_diagnostics", plan["cohorts"][0])
        self.assertNotIn('match_by_owner', payload['candidates_by_id']['paragraph'])

    def test_projection_preserves_catalog_bundle_and_owner_authority(self):
        before = deepcopy(self.catalog)
        fingerprint = semantic_candidate_catalog_fingerprint(self.catalog)
        plan = _semantic_candidate_cohorts(self.catalog, self.owners)
        payload = FinancialAgent._semantic_program_prompt_payload(self.catalog, plan)
        self.assertEqual(list(payload["candidates_by_id"]), plan["visible_candidate_ids"])
        self.assertEqual([c["candidate_ids"] for c in payload["cohorts"]], [c["candidate_ids"] for c in plan["cohorts"]])
        bundles = build_semantic_source_bundles(self.catalog, candidate_ids=plan["visible_candidate_ids"])
        self.assertEqual(payload["source_bundle_fingerprint"], semantic_source_bundle_fingerprint(bundles))
        self.assertEqual(set(payload["source_bundles_by_id"]), {b.source_bundle_id for b in bundles})
        self.assertEqual(self.catalog, before)
        self.assertEqual(semantic_candidate_catalog_fingerprint(self.catalog), fingerprint)

    def test_source_reading_orders_enclosing_hierarchy_before_exact_body(self):
        nested = context("a-inner", "[Local section]", "/ROOT/SECTION/SECTION/TITLE")
        self.catalog[0]["source_contexts"].insert(0, nested)
        payload = self.payload()
        reading, = payload["source_readings"]
        self.assertEqual([c["context_id"] for c in reading["enclosing_contexts"]], ["z-heading", "a-inner"])
        self.assertEqual(surface_text(reading["bodies"][0]), "We use local partners.\r\n")
        self.assertEqual(context_surfaces(payload)["z-heading"], "[Cedar]\t ")
        self.assertLess(list(reading).index("enclosing_contexts"), list(reading).index("bodies"))
        self.assertNotIn("source_text", payload["source_contexts_by_id"]["z-heading"])

    def test_same_parent_formal_and_intermediate_headings_follow_anonymous_xml(self):
        for outer, inner, local in (("Overview", "Details", "Willow"),
                                    ("Zeta", "Alpha", "오로라")):
            with self.subTest(titles=(outer, inner, local)), TemporaryDirectory() as directory:
                xml = (f'<DOCUMENT><SECTION-1><TITLE ATOC="Y">{outer}</TITLE>'
                       f'<SECTION-2><TITLE ATOC="Y">{inner}</TITLE>'
                       f'<P USERMARK="B">[{local}]</P><P>We use partners.</P>'
                       '<TABLE><THEAD><TR><TH>Item</TH><TH>Route</TH></TR></THEAD>'
                       '<TBODY><TR><TD>Delivery</TD><TD>We use partners.</TD></TR></TBODY></TABLE>'
                       '</SECTION-2></SECTION-1></DOCUMENT>')
                path = Path(directory) / "anonymous.xml"
                path.write_text(xml, encoding="utf-8")
                parser = FinancialParser()
                catalog = parsed_catalog(parser.process_document(str(path),
                    {"company": "Issuer", "year": 2042, "rcept_no": "anonymous"}))
                root = parser._parse_xml(str(path))
                tree = root.getroottree()
                xml_order = {tree.getpath(node): index for index, node in enumerate(root.iter())}
                before = deepcopy(catalog)
                fingerprint = semantic_candidate_catalog_fingerprint(catalog)
                payload = self.payload(catalog)
                self.assertTrue(payload["source_readings"])
                for reading in payload["source_readings"]:
                    headings = reading["enclosing_contexts"]
                    self.assertEqual([h["relation"] for h in headings],
                                     ["ancestor_heading", "ancestor_heading", "intermediate_heading"])
                    positions = [xml_order[payload["source_contexts_by_id"][h["context_id"]]["source_locator"]]
                                 for h in headings]
                    self.assertEqual(positions, sorted(positions))
                self.assertEqual(set(context_surfaces(payload).values()) & {outer, inner, f"[{local}]"},
                                 {outer, inner, f"[{local}]"})
                reordered = deepcopy(catalog[::-1])
                for candidate in reordered:
                    candidate["source_contexts"].reverse()
                self.assertEqual(json.dumps(payload), json.dumps(self.payload(reordered)))
                self.assertEqual(catalog, before)
                self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)

    def test_heading_hierarchy_precedes_role_and_preserves_natural_local_order(self):
        contexts = [
            context("a-inner", "Inner", "/ROOT/SECTION/SECTION/TITLE"),
            context("b-late", "Late", "/ROOT/SECTION/SECTION/P[10]", "intermediate_heading"),
            context("c-early", "Early", "/ROOT/SECTION/SECTION/P[2]", "intermediate_heading"),
            context("d-outer-local", "Outer local", "/ROOT/SECTION/P[1]", "intermediate_heading"),
            context("z-outer", "Outer", "/ROOT/SECTION/TITLE"),
        ]
        self.catalog[0]["source_contexts"] = contexts
        payload = self.payload()
        self.assertEqual([row["context_id"] for row in payload["source_readings"][0]["enclosing_contexts"]],
                         ["z-outer", "d-outer-local", "a-inner", "c-early", "b-late"])
        self.assertEqual(context_surfaces(payload), {row["context_id"]: row["source_text"] for row in contexts})

    def test_heading_role_does_not_reorder_different_parent_scopes(self):
        catalog = [source("p2", "First body.", source_document_id="doc-a",
                          source_contexts=[context("z-local", "Local", "/ROOT/SECTION[2]/P[1]", "intermediate_heading")]),
                   source("p10", "Second body.", source_document_id="doc-a",
                          source_contexts=[context("a-formal", "Formal", "/ROOT/SECTION[10]/TITLE")])]
        payload = self.payload(catalog)
        self.assertEqual([b["candidate_ids"] for row in payload["source_readings"] for b in row["bodies"]],
                         [["p2"], ["p10"]])

    def test_peer_locations_and_foreign_filings_never_group_by_issuer_or_title(self):
        catalog = [source(key, f"Body {key}.", company="Same issuer", source_document_id=doc,
            source_contexts=[context(heading, "[Same title]", f"/ROOT/SECTION/P[{index}]",
                relation="intermediate_heading", document=doc)])
            for key, heading, doc, index in (("p10", "a", "doc-a", 10), ("p2", "z", "doc-a", 2), ("foreign", "f", "doc-b", 2))]
        payload = self.payload(catalog)
        self.assertEqual([b["candidate_ids"] for r in payload["source_readings"] for b in r["bodies"]], [["p2"], ["p10"], ["foreign"]])
        self.assertEqual(len(context_surfaces(payload)), 3)
        self.assertEqual(json.dumps(payload, ensure_ascii=False), json.dumps(self.payload(list(reversed(catalog))), ensure_ascii=False))

    def test_shared_context_serializes_once_but_each_attachment_stays_explicit(self):
        catalog = [*self.catalog, source("second", "Cedar also delivers directly.",
            source_document_id="doc-a", source_contexts=[deepcopy(self.heading)])]
        payload = self.payload(catalog)
        fragments = [c for r in payload["source_readings"] for c in r["enclosing_contexts"]]
        self.assertEqual(sum("pieces" in c for c in fragments), 1)
        self.assertEqual(len(payload["source_readings"]), 1)
        self.assertEqual(len(payload["source_readings"][0]["bodies"]), 2)
        for row in payload["candidates_by_id"].values():
            self.assertEqual(row.get("attached_context_ids", payload["source_bundles_by_id"][row["source_bundle_id"]]["context_ids"]), ["z-heading"])
        self.assertEqual(context_surfaces(payload), {"z-heading": self.heading["source_text"]})

    def test_shared_row_does_not_grant_another_members_context(self):
        physical = {"physical_table_id": "table", "physical_row_id": "row"}
        catalog = [dict(self.catalog[0], **physical), source("other", "We use local partners.\r\n", **physical)]
        payload = self.payload(catalog)
        self.assertEqual(len(payload["source_readings"]), 1)
        self.assertEqual(payload["candidates_by_id"]["other"]["attached_context_ids"], [])
        self.assertNotIn("attached_context_ids", payload["candidates_by_id"]["paragraph"])
        self.assertEqual(payload["source_bundles_by_id"][payload["candidates_by_id"]["paragraph"]["source_bundle_id"]]["context_ids"], ["z-heading"])

    def test_filing_metadata_is_not_a_quote_or_local_subject(self):
        payload = self.payload()
        metadata = payload["document_provenance"]["candidates_by_id"]["paragraph"]
        self.assertEqual(metadata["document_company"], "Parent")
        row = payload["candidates_by_id"]["paragraph"]
        self.assertNotIn("company", row)
        self.assertNotIn("source_anchor", row)
        self.assertEqual(row["local_entity_surfaces"], ["We"])
        self.assertNotIn("Parent", json.dumps(payload["source_readings"]))

    def test_only_narrative_empty_scalar_fields_are_omitted_unknowns_survive(self):
        narrative = self.payload()["candidates_by_id"]["paragraph"]
        self.assertFalse(EMPTY_SCALAR_FIELDS & set(narrative))
        self.assertEqual(narrative["normalized_unit"], "UNKNOWN")
        for owners in ([_obligation("size", "direct_value", "Size")],
                       [*self.owners, _obligation("size", "direct_value", "Size")]):
            catalog = [*self.catalog, _candidate("cell", 12)]
            payload = self.payload(catalog, owners)
            self.assertEqual(payload["reading_mode"], "numeric_or_mixed")
            row = payload["candidates_by_id"]["cell"]
            self.assertIn("period", row)
            self.assertIn("source_value_span", row)

    def test_narrative_dispatch_uses_same_schema_and_no_arithmetic_instructions(self):
        result, prompts = self.compile([self.program()])
        self.assertEqual(result["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(prompts), 1)
        text = prompts[0].to_messages()[0].content
        for numeric in ("source_display_reason", "request_inputs", "binding_count"):
            self.assertNotIn(numeric, text)
            self.assertIn(numeric, CALCULATION_PROMPT_POLICY["semantic_program_prompt_template"])
        self.assertNotIn("row_description_quote_options", text)
        self.assertEqual(prompt_json(prompts[0], MARKER)["schema"], "semantic_program_candidate_payload_v9")
        self.assertIn("source_display_reason", SemanticCalculationProgram.model_json_schema()["$defs"]["SemanticProgramExpression"]["properties"])

    def test_special_row_permission_requires_real_scalar_axes_and_provenance(self):
        valid = {**_candidate("cell", 18, row_label="Partners"), "source_text": "Partners | 18",
            "source_document_id": "doc-a", "year": 2037, "physical_table_id": "table",
            "physical_row_id": "row", "physical_cell_id": "cell-physical"}
        payload = self.payload([valid])
        row = payload["candidates_by_id"]["cell"]
        self.assertEqual(row["row_description_quote_options"], ["Partners"])
        self.assertEqual(row["physical_cell_id"], "cell-physical")
        for change in ({"kind": "narrative"}, {"source_document_id": ""}, {"year": None},
                       {"physical_row_id": ""}, {"row_label": "18"}, {"row_label": "Absent"}):
            with self.subTest(change=change):
                candidate = {**valid, **change}
                row = self.payload([candidate])["candidates_by_id"]["cell"]
                self.assertNotIn("row_description_quote_options", row)

    def test_retry_switches_mixed_to_narrative_view_and_preserves_accepted_bytes(self):
        owners = [*self.owners, _obligation("size", "direct_value", "Size")]
        owners[0]['depends_on'] = ['size']
        accepted = {"obligation_id": "size", "candidate_id": "cell"}
        bad = self.program()
        bad["narrative_bindings"][0]["claims"][0]["evidence_bindings"][0]["context_id"] = "z-heading"
        with patch("src.agent.financial_graph_calculation._merge_targeted_program_retry", wraps=_merge_targeted_program_retry) as merge:
            result, prompts = self.compile([{**bad, "direct_bindings": [accepted]}, self.program()],
                owners=owners, catalog=[*self.catalog, _candidate("cell", 12)])
        self.assertEqual(result["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(prompts), 2)
        self.assertIn("source_display_reason", prompts[0].to_messages()[0].content)
        self.assertNotIn("source_display_reason", prompts[1].to_messages()[0].content)
        self.assertEqual(prompt_json(prompts[1], "Answer obligations:"), [owners[0]])
        expected = merge.call_args.kwargs["previous_program"]["direct_bindings"]
        self.assertEqual(json.dumps(result["semantic_program"]["direct_bindings"], sort_keys=True), json.dumps(expected, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
