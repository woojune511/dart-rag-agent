"""Reading exposure is not numeric identity or semantic entailment authority."""
from copy import deepcopy
from tests.narrative_address_test_support import model_program
import json
import unittest

from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_candidate_matching import structured_subject_evidence
from src.agent.financial_compiler_presentation import project_prompt_match
from src.agent.financial_graph_calculation import _rank_applicable_owner_candidates, _semantic_candidate_cohorts
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint
from tests.test_narrative_candidate_selection import candidate, owner


def target(name="Elm", label="network reach", **extra):
    result = owner(label, **extra)
    result["semantic_target"]["local_subjects"] = [name]
    return result


def row(cid="row", name="Elm", **extra):
    result = candidate(cid, table=f"table-{cid}", text=f"{name} | network reach | 1", **extra)
    result.update(row_label=name, row_headers=[name])
    return result


def reading(cid="explanation", name="Elm", **extra):
    return candidate(cid, text=f"{name} increased network reach through local partners.", **extra)


def select(catalog, required=None, **extra):
    before = deepcopy(catalog)
    result = _rank_applicable_owner_candidates(catalog, owner=required or target(),
        candidate_kind="evidence", limit=6, **extra)
    assert before == catalog
    return result


class NarrativeReadingAdmissionTests(unittest.TestCase):
    def test_short_names_and_many_exact_axes_do_not_starve_a_peer_reading(self):
        for name in ("Q", "Elm", "Birch", "별", "별빛팀"):
            with self.subTest(name=name):
                rows = [row(f"a-{index}", name, section="Chapter > A details") for index in range(30)]
                prose = reading("z-reading", name, section="Chapter > Z explanation")
                selected, _, matches, _ = select([*rows, prose], target(name))
                self.assertIn("z-reading", [item["candidate_id"] for item in selected])
                self.assertEqual(matches["z-reading"]["rank_vector"], matches["a-0"]["rank_vector"])
                self.assertEqual(len(selected), 6)
                reverse, _, _, _ = select([prose, *reversed(rows)], target(name))
                self.assertEqual(selected, reverse)

    def test_reading_tier_does_not_upgrade_existing_identity_or_applicability(self):
        _, _, matches, diagnostics = select([row(), reading()])
        self.assertEqual(matches["row"]["subject_state"], "match")
        self.assertEqual(matches["explanation"]["subject_state"], "unknown")
        self.assertEqual(matches["explanation"]["state"], "unknown_only")
        for match in matches.values():
            self.assertEqual(match["reading_subject_state"], "local_literal")
            self.assertEqual(match["reading_state"], "compatible")
            # Exposure scores/hints are diagnostics, not model guidance or a
            # new self-authored way to satisfy a validation obligation.
            self.assertNotIn("reading_state", project_prompt_match(match))
            self.assertNotIn("reading_subject_state", project_prompt_match(match))
        self.assertEqual(diagnostics["top_two_relation"], "tie")

    def test_reading_relevance_precedes_a_bare_exact_subject_axis(self):
        rows = [row(f"a-{index}", section="Chapter > A details") for index in range(20)]
        for item in rows:
            item.update(source_text="Observed volume | 1", source_bundle_text="Observed volume | 1")
        prose = reading("z-reading", section="Chapter > Z explanation")
        selected, _, matches, diagnostics = select([*rows, prose])
        self.assertEqual(selected[0]["candidate_id"], "z-reading")
        self.assertEqual(matches["a-0"]["subject_state"], "match")
        self.assertEqual(matches["z-reading"]["subject_state"], "unknown")
        self.assertEqual(matches["a-0"]["reading_state"], "compatible")
        self.assertEqual(diagnostics["first_differing_factor"], "reading_match")

    def test_same_reading_signal_is_format_neutral_even_when_scope_is_unknown(self):
        required = target()
        required["scope"]["basis"] = "excluding transfers"
        selected, _, matches, _ = select([row(), reading()], required)
        self.assertEqual(len(selected), 2)
        self.assertEqual(matches["row"]["reading_state"], "unknown_only")
        self.assertEqual(matches["row"]["rank_vector"], matches["explanation"]["rank_vector"])

    def test_mention_does_not_borrow_metadata_hidden_tails_or_joined_surfaces(self):
        required = target("Elm East")
        invisible = candidate("metadata", text="Unrelated introduction.")
        invisible.update(local_entity_surfaces=["Elm East"], document_company="Elm East", local_heading="Elm East",
            source_text="Unrelated introduction. Elm East increased network reach.")
        split = candidate("split", text="Elm", heading="East")
        punctuation = candidate("punctuation", text="Elm / East increased network reach.")
        _, _, matches, _ = select([invisible, split, punctuation], required)
        self.assertTrue(all(match["reading_subject_state"] == "unknown" for match in matches.values()))

    def test_continuations_and_attached_headings_are_read_separately_without_length_threshold(self):
        for name in ("Q", "Elm", "별빛팀"):
            for relation, expected in (("source_continuation", "local_literal"), ("ancestor_heading", "context_literal")):
                with self.subTest(name=name, relation=relation):
                    source = candidate("text", text="The network reach increased.")
                    source["source_contexts"] = [{"relation": relation, "source_text": name}]
                    _, _, matches, _ = select([source], target(name))
                    self.assertEqual(matches["text"]["reading_subject_state"], expected)

    def test_literal_overlap_is_not_full_name_or_group_equivalence(self):
        for surface in ("Elmwood", "Elm and others", "Elm East"):
            with self.subTest(surface=surface):
                source = row(name=surface)
                _, _, matches, _ = select([source])
                self.assertEqual(matches["row"]["reading_subject_state"], "local_literal")
                self.assertEqual(matches["row"]["subject_state"], "unknown")
                self.assertEqual(structured_subject_evidence(source, ["Elm"])["state"], "unknown")
                required = target(kind="direct_value")
                selected, _, numeric_matches, _ = _rank_applicable_owner_candidates([source], owner=required,
                    candidate_kind="numeric", limit=2)
                self.assertNotIn("reading_state", numeric_matches["row"])
                self.assertEqual(numeric_matches["row"]["state"], "unknown_only")
                rejected = validate_semantic_calculation_program(program={"direct_bindings": [
                    {"obligation_id": "overview", "candidate_id": "row"}]}, obligations=[required],
                    candidate_catalog=[source], query="Return the quantity for Elm.")
                self.assertIn("candidate_subject_unresolved", {error["code"] for error in rejected["errors"]})

    def test_explicit_conflicts_and_section_restrictions_still_block_good_reading_hints(self):
        good = row()
        required = target()
        required["source_sections"] = ["Detail"]
        other_subject = row("other", name="Birch")
        other_subject.update(physical_table_id=good["physical_table_id"], physical_row_id="other",
            source_contexts=[{"relation": "ancestor_heading", "source_text": "Elm network reach"}])
        sources = [good, other_subject, {**reading("foreign"), "company": "Other issuer"},
            {**reading("period"), "period": "2039"}, reading("outside", section="Other note")]
        selected, _, matches, _ = select(sources, required)
        self.assertEqual([item["candidate_id"] for item in selected], ["row"])
        for key in ("other", "foreign", "period"):
            self.assertEqual(matches[key]["state"], "explicit_conflict")
            self.assertEqual(matches[key]["reading_state"], "explicit_conflict")
        self.assertNotIn("outside", matches)

    def test_table_only_and_prose_only_inputs_have_no_fixed_format_reservation(self):
        for make in (row, reading):
            catalog = [make(f"source-{index}") for index in range(9)]
            selected, _, _, _ = select(catalog)
            self.assertEqual(len(selected), 6)

    def test_requirement_inherits_reading_mode_without_changing_catalog_or_owner_targets(self):
        parent = target()
        parent["evidence_requirements"] = [{"requirement_id": "reach", "label": "network reach",
            "scope": parent["scope"], "semantic_target": parent["semantic_target"]}]
        sources = [*[row(f"a-{index}", section="Chapter > A details") for index in range(20)],
            reading("z-reading", section="Chapter > Z explanation")]
        before = deepcopy((sources, parent))
        fingerprint = semantic_candidate_catalog_fingerprint(sources)
        plan = _semantic_candidate_cohorts(sources, [parent])
        self.assertIn("z-reading", plan["candidate_ids_by_owner"]["reach"])
        self.assertEqual(plan["candidate_match_by_id"]["z-reading"]["reach"]["reading_state"], "compatible")
        self.assertEqual((sources, parent), before)
        self.assertEqual(semantic_candidate_catalog_fingerprint(sources), fingerprint)

    def test_repeated_mentions_do_not_accumulate_priority(self):
        single, repeated = reading("single"), reading("repeated")
        repeated.update(source_text=single["source_text"] * 10, source_bundle_text=single["source_bundle_text"] * 10)
        _, _, matches, _ = select([single, repeated])
        self.assertEqual(matches["single"]["rank_vector"], matches["repeated"]["rank_vector"])

    def test_compiler_reads_newly_visible_prose_in_one_existing_call_and_keeps_quote_checks(self):
        from src.agent.financial_graph_models import SemanticCalculationProgram
        from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
        from tests.semantic_program_test_support import _StructuredQueueLLM
        from tests.test_narrative_claim_grounding import claim

        sources = [*[row(f"a-{index}", section="Chapter > A details") for index in range(20)],
            reading("z-reading", section="Chapter > Z explanation")]
        required = target()
        required["request_unit_ids"] = ["request_001"]
        body = sources[-1]["source_text"]
        response = model_program({"narrative_bindings": [{"obligation_id": "overview",
            "claims": [claim("Elm", body, "z-reading", body)]}]}, sources)
        llm = _StructuredQueueLLM(response)
        state = _case_state({"question": "Describe Elm's network reach.", "obligations": [required]}, sources)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 1)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        bad = deepcopy(response.model_dump())
        bad["narrative_bindings"][0]["claims"][0]["fact_evidence_selections"][0]["surface_id"] = "invented"
        bad = SemanticCalculationProgram.model_validate(bad).model_dump()
        rejected = validate_semantic_calculation_program(program=bad, obligations=[required], candidate_catalog=sources,
            query="Describe Elm's network reach.", require_narrative_claims=True)
        self.assertNotEqual(rejected["status"], "ready")
        self.assertNotIn("reading_subject_state", json.dumps(llm.prompts[0].to_messages()[0].content))


if __name__ == "__main__":
    unittest.main()
