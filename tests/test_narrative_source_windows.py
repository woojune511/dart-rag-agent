from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program,
    validate_semantic_calculation_program,
)
from src.agent.financial_runtime_contracts import CandidateVisibilityV1, CompilationEnvelopeV2

from src.agent.financial_graph_calculation import (
    FinancialAgentCalculationMixin,
    _semantic_candidate_cohorts,
)
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_source_bundles import build_semantic_source_bundles


def source(text: str, source_id: str = "source-body") -> dict:
    return {
        "candidate_id": source_id, "candidate_kind": "chunk",
        "source_anchor": "[sample]", "text": " ".join(text.split()),
        "source_text_exact": text, "metadata": {"is_table": False},
    }


def narrative_owner() -> dict:
    return {
        "obligation_id": "ob_summary", "kind": "narrative", "label": "service policy",
        "required": True, "scope": {}, "display_unit": "",
        "semantic_target": {"local_subjects": [], "concept_keys": [], "metric_surfaces": ["service policy"]},
        "evidence_requirements": [], "depends_on": [], "coupling_key": "",
    }


class NarrativeSourceWindowTests(unittest.TestCase):
    def test_metadata_prefix_does_not_displace_the_original_body(self) -> None:
        prefix = "[섹션: " + "metadata " * 100 + "]\r\n"
        body = "Service policy.\t  " + "A source statement. " * 15 + "Final funding response."
        exact = prefix + body
        catalog = build_semantic_candidate_catalog([source(exact)])
        narrative = next(row for row in catalog if row["kind"] == "narrative")
        bundle = next(bundle for bundle in build_semantic_source_bundles(catalog)
                      if narrative["candidate_id"] in bundle.candidate_ids)
        self.assertEqual(bundle.source_text, body)
        self.assertEqual(narrative["source_bundle_context_span"], [len(prefix), len(exact)])
        self.assertFalse(narrative["source_body_coverage"]["truncated"])
        self.assertEqual(narrative["source_text"], body)

    def test_long_body_continuations_are_exact_linked_and_serialized_once(self) -> None:
        prefix = "[섹션: metadata]\n"
        body = "Service policy. " + "A source statement. " * 80 + "Tail integration strategy.\t  Exact ending."
        exact = prefix + body
        catalog = build_semantic_candidate_catalog([source(exact)])
        before = deepcopy(catalog)
        narrative = next(row for row in catalog if row["kind"] == "narrative")
        owner = narrative_owner()
        other = {**owner, "obligation_id": "ob_other"}
        plan = _semantic_candidate_cohorts(catalog, [owner, other])
        payload = FinancialAgentCalculationMixin._semantic_program_prompt_payload(catalog, plan)
        bundle = payload["source_bundles_by_id"][payload["candidates_by_id"][narrative["candidate_id"]]["source_bundle_id"]]
        continuations = [payload["source_contexts_by_id"][key] for key in bundle["context_ids"]
                         if bundle["context_relations"][key] == "source_continuation"]
        continuations.sort(key=lambda row: row["source_span"])
        windows = [(narrative["source_bundle_context_span"], bundle["source_text"])] + [
            (row["source_span"], row["source_text"]) for row in continuations
        ]
        self.assertEqual("".join(text for _, text in windows), body)
        for span, text in windows:
            self.assertLessEqual(len(text), 1200)
            self.assertEqual(exact[slice(*span)], text)
        self.assertTrue(any("Tail integration strategy.\t  Exact ending." in text for _, text in windows))
        self.assertEqual(len(payload["source_bundles_by_id"]), 1)
        self.assertEqual(len(payload["source_contexts_by_id"]), len(continuations))
        self.assertEqual(payload["reservation"]["narrative"], 1)
        self.assertEqual(catalog, before)

    def test_oversized_body_is_bounded_and_omission_is_visible(self) -> None:
        text = "Service policy. " + "A source statement. " * 350 + "Unseen ending."
        catalog = build_semantic_candidate_catalog([source(text)])
        narrative = next(row for row in catalog if row["kind"] == "narrative")
        coverage = narrative["source_body_coverage"]
        self.assertTrue(coverage["truncated"])
        self.assertEqual(coverage["source_span"], [0, len(text)])
        self.assertLessEqual(coverage["visible_span"][1], 4800)
        plan = _semantic_candidate_cohorts(catalog, [narrative_owner()])
        payload = FinancialAgentCalculationMixin._semantic_program_prompt_payload(catalog, plan)
        self.assertEqual(payload["candidates_by_id"][narrative["candidate_id"]]["source_body_coverage"], coverage)
        windows = [b["source_text"] for b in payload["source_bundles_by_id"].values()] + [
            c["source_text"] for c in payload["source_contexts_by_id"].values()
        ]
        self.assertLessEqual(sum(map(len, windows)), 4800)
        self.assertNotIn("Unseen ending.", "".join(windows))

    def test_hidden_candidate_cannot_leak_its_continuation(self) -> None:
        text = "Service policy. " + "A source statement. " * 80 + "Hidden source ending."
        catalog = build_semantic_candidate_catalog([source(text), source("Visible policy.", "visible")])
        visible = next(row for row in catalog if row["source_candidate_id"] == "visible")
        payload = FinancialAgentCalculationMixin._semantic_program_prompt_payload(
            catalog, {"visible_candidate_ids": [visible["candidate_id"]]},
        )
        self.assertEqual(payload["source_contexts_by_id"], {})
        self.assertNotIn("Hidden source ending.", str(payload))

    def test_original_bracket_notes_are_not_parser_metadata(self) -> None:
        body = "[Note: original source statement.]\r\nService policy."
        for prefix in ("", "[섹션: sample]\r\n[table_context: heading]\r\n"):
            with self.subTest(prefix=prefix):
                catalog = build_semantic_candidate_catalog([source(prefix + body)])
                narrative = next(row for row in catalog if row["kind"] == "narrative")
                self.assertEqual(narrative["source_bundle_text"], body)

    def test_reversed_sources_keep_catalog_identity_and_exact_windows(self) -> None:
        sources = [source("Service policy. " + "Statement. " * 180, "long"), source("Other policy.", "short")]
        forward = build_semantic_candidate_catalog(sources)
        reverse = build_semantic_candidate_catalog(list(reversed(sources)))
        self.assertEqual(semantic_candidate_catalog_fingerprint(forward), semantic_candidate_catalog_fingerprint(reverse))
        self.assertEqual(build_semantic_source_bundles(forward), build_semantic_source_bundles(reverse))
        project = lambda catalog: FinancialAgentCalculationMixin._semantic_program_prompt_payload(
            catalog, _semantic_candidate_cohorts(catalog, [narrative_owner()]),
        )
        self.assertEqual(project(forward), project(reverse))

    def test_continuation_numbers_ground_narrative_and_content_drift_blocks_execution(self) -> None:
        body = "Service policy. " + "Statement. " * 160 + "Final delivery count is 47."
        catalog = build_semantic_candidate_catalog([source(body)])
        narrative = next(row for row in catalog if row["kind"] == "narrative")
        owner = narrative_owner()
        plan = _semantic_candidate_cohorts(catalog, [owner])
        visibility = CandidateVisibilityV1.create(
            catalog_fingerprint=semantic_candidate_catalog_fingerprint(catalog),
            visible_candidate_ids=plan["visible_candidate_ids"],
            candidate_ids_by_owner=plan["candidate_ids_by_owner"],
        )
        inputs = {"candidate_catalog": catalog, "obligations": [owner], "query": "Summarize the service policy."}
        program = {"status": "ready", "narrative_bindings": [{
            "obligation_id": owner["obligation_id"], "candidate_ids": [narrative["candidate_id"]],
            "text": "Final delivery count is 47.",
        }]}
        validation = validate_semantic_calculation_program(program=program, candidate_visibility=visibility, **inputs)
        self.assertEqual(validation["status"], "ready", validation["errors"])
        envelope = CompilationEnvelopeV2.create(visibility=visibility, program=program, validation=validation, **inputs)
        execution = execute_semantic_calculation_program(
            program=program, compilation_envelope=envelope, require_compilation_envelope=True, **inputs,
        )
        self.assertEqual(execution["status"], "ok")
        for field, value in (("source_text", "Rewritten source."), ("source_span", [0, 1])):
            with self.subTest(field=field):
                changed = deepcopy(inputs)
                altered = next(row for row in changed["candidate_catalog"] if row["kind"] == "narrative")
                altered["source_contexts"][0][field] = value
                with patch("src.agent.financial_calculation_execution.validate_semantic_calculation_program") as validator:
                    result = execute_semantic_calculation_program(
                        program=program, compilation_envelope=envelope, require_compilation_envelope=True, **changed,
                    )
                validator.assert_not_called()
                self.assertIn("execution_content_mismatch", str(result))


if __name__ == "__main__":
    unittest.main()
