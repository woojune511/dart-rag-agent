"""Source-located table context, not filing-year guesses or model-quality claims."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json

from tests.semantic_program_test_support import *
from src.processing.financial_parser import FinancialParser
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2


FIXTURE = Path(__file__).parent / "fixtures" / "source_context_hierarchy.xml"


def parsed_catalog():
    chunks = FinancialParser(chunk_size=2500, chunk_overlap=320).process_document(
        str(FIXTURE), {"company": "sample", "year": 2024, "rcept_no": "source-context-fixture"}
    )
    docs = [SimpleNamespace(page_content=c.content, metadata=c.metadata) for c in chunks]
    sources = build_semantic_source_candidates({"retrieved_docs": [(d, 1.0) for d in docs]},
        source_anchor_builder=lambda m: f"[{m['rcept_no']} | {m['year']} | {m['section_path']}]")
    return chunks, build_semantic_candidate_catalog(sources)


def value(catalog, raw="100"):
    return next(c for c in catalog if c["kind"] == "numeric" and c["raw_value"] == raw
                and c["consolidation_scope"] == "consolidated")


def context_binding(candidate, text="당기 (단위: 백만원)", period="2024"):
    context = next(c for c in candidate["source_contexts"] if text in c["source_text"])
    return {"context_id": context["context_id"], "evidence_text": text,
            "field": "period", "value": period}


class DocumentContextTests(unittest.TestCase):
    def test_context_addition_preserves_existing_ids_and_adds_text_row_readings(self):
        chunks, catalog = parsed_catalog()
        docs = []
        for chunk in chunks:
            metadata = deepcopy(chunk.metadata)
            table = json.loads(metadata["table_object_json"])
            for key in ("source_contexts", "source_table_locator", "source_document_sha256"):
                table.pop(key, None)
            metadata["table_object_json"] = json.dumps(table, ensure_ascii=False)
            docs.append((SimpleNamespace(page_content=chunk.content, metadata=metadata), 1.0))
        sources = build_semantic_source_candidates({"retrieved_docs": docs},
            source_anchor_builder=lambda m: f"[{m['rcept_no']} | {m['year']} | {m['section_path']}]")
        before = build_semantic_candidate_catalog(sources)
        before_ids = {c["candidate_id"] for c in before}
        preserved = [c for c in catalog if c["candidate_id"] in before_ids]
        self.assertEqual([c["candidate_id"] for c in preserved], [c["candidate_id"] for c in before])
        self.assertEqual(semantic_candidate_catalog_fingerprint(preserved), semantic_candidate_catalog_fingerprint(before))
        readings = [c for c in catalog if c["candidate_id"] not in before_ids]
        self.assertEqual(len(readings), 2)
        self.assertTrue(all(c["kind"] == "narrative" and c["normalized_value"] is None for c in readings))
        self.assertTrue(all(c["source_context_provenance"]["relation"] == "table_text_row" for c in readings))

    def test_parser_preserves_located_ancestors_and_separates_periods(self):
        _, catalog = parsed_catalog()
        current, prior = value(catalog), value(catalog, "90")
        contexts = current["source_contexts"]
        self.assertEqual(len([c for c in contexts if c["relation"] == "ancestor_heading"]), 3)
        self.assertTrue(all(c["source_locator"] and c["document_sha256"] for c in contexts))
        current_context = context_binding(current)
        prior_context = context_binding(prior, "전기 (단위: 백만원)", "2023")
        self.assertNotEqual(current_context["context_id"], prior_context["context_id"])
        self.assertNotIn(prior_context["context_id"], [c["context_id"] for c in contexts])
        self.assertIsNone(current["value_year"])
        self.assertEqual(current["period"], "")
        self.assertTrue(any("2020년" in c["source_text"] for c in contexts))

    def test_prompt_dedupes_context_without_changing_candidate_identity(self):
        _, catalog = parsed_catalog()
        stripped = deepcopy(catalog)
        for candidate in stripped:
            candidate.pop("source_contexts", None)
            candidate.pop("source_table_locator", None)
            candidate.pop("source_document_sha256", None)
        self.assertEqual(semantic_candidate_catalog_fingerprint(catalog),
                         semantic_candidate_catalog_fingerprint(stripped))
        owners = [_obligation("a", "direct_value", "영업이익"),
                  _obligation("b", "direct_value", "영업이익")]
        cohort = _semantic_candidate_cohorts(catalog, owners)
        payload = FinancialAgent._semantic_program_prompt_payload(catalog, cohort)
        contexts = payload["source_contexts_by_id"]
        self.assertTrue(contexts)
        for bundle in payload["source_bundles_by_id"].values():
            self.assertTrue(set(bundle.get("context_ids", [])) <= contexts.keys())
        for row in payload["candidates_by_id"].values():
            self.assertNotIn("source_contexts", row)
        reverse = FinancialAgent._semantic_program_prompt_payload(
            list(reversed(catalog)), _semantic_candidate_cohorts(list(reversed(catalog)), owners))
        self.assertEqual(payload, reverse)

    def test_context_binding_reaches_authorized_execution_without_mutating_catalog(self):
        _, catalog = parsed_catalog()
        selected = value(catalog)
        owner = _obligation("a", "direct_value", "영업이익", scope=_scope(period="2024"))
        program = {"status": "ready", "direct_bindings": [{"obligation_id": "a",
            "candidate_id": selected["candidate_id"], "context_bindings": [context_binding(selected)]}]}
        before = deepcopy(catalog)
        cohort = _semantic_candidate_cohorts(catalog, [owner])
        visibility = _semantic_candidate_visibility(catalog,
            visible_candidate_ids=cohort["visible_candidate_ids"],
            candidate_ids_by_owner=cohort["candidate_ids_by_owner"])
        inputs = dict(program=program, obligations=[owner], candidate_catalog=catalog, query="2024 value")
        validation = validate_semantic_calculation_program(**inputs, candidate_visibility=visibility)
        self.assertEqual(validation["status"], "ready", validation["errors"])
        envelope = CompilationEnvelopeV2.create(visibility=visibility, validation=validation, **inputs)
        result = execute_semantic_calculation_program(**inputs, compilation_envelope=envelope,
                                                      require_compilation_envelope=True)
        self.assertEqual(result["status"], "ok", result["validation"]["errors"])
        operand = result["calculation_operands"][0]
        self.assertEqual(operand["value_year"], 2024)
        self.assertEqual(operand["period_source"], "source_context_binding")
        self.assertTrue(operand["context_resolution"])
        self.assertEqual(catalog, before)
        selected["source_contexts"][0]["source_text"] += " changed"
        rejected = execute_semantic_calculation_program(**inputs, compilation_envelope=envelope,
                                                        require_compilation_envelope=True)
        self.assertEqual(rejected["validation"]["errors"][0]["code"], "execution_content_mismatch")

    def test_bad_quote_other_table_hidden_owner_and_conflict_are_program_repairs(self):
        _, catalog = parsed_catalog()
        selected, prior = value(catalog), value(catalog, "90")
        owner = _obligation("a", "direct_value", "영업이익", scope=_scope(period="2024"))
        good = context_binding(selected)
        changes = [
            ({**good, "evidence_text": "당기 (단위: 백만 원)"}, "context_quote_not_exact"),
            ({**good, "context_id": "ctx_hidden"}, "context_not_attached_to_candidate"),
            (context_binding(prior, "전기 (단위: 백만원)", "2023"), "context_not_attached_to_candidate"),
            ({**good, "value": "2023"}, "context_period_mismatch"),
            ({**good, "field": "company", "value": "another"}, "invalid_context_scope_binding"),
        ]
        for binding, code in changes:
            with self.subTest(code=code):
                program = {"direct_bindings": [{"obligation_id": "a", "candidate_id": selected["candidate_id"],
                                               "context_bindings": [binding]}]}
                validation = validate_semantic_calculation_program(program=program, obligations=[owner],
                    candidate_catalog=catalog, query="2024 value")
                errors = [e for e in validation["errors"] if e["code"] == code]
                self.assertTrue(errors, validation["errors"])
                self.assertEqual(errors[0]["repair_action"], "repair_program")
                self.assertEqual(errors[0]["candidate_id"], selected["candidate_id"])
                self.assertFalse(validation["valid_direct_bindings"])
        program = {"direct_bindings": [{"obligation_id": "a", "candidate_id": selected["candidate_id"],
                                       "context_bindings": [good]}]}
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=[selected["candidate_id"]],
            candidate_ids_by_owner={"other": [selected["candidate_id"]], "a": []})
        validation = validate_semantic_calculation_program(program=program, obligations=[owner],
            candidate_catalog=catalog, query="2024 value", candidate_visibility=visibility)
        self.assertFalse(validation["valid_direct_bindings"])
        selected.update(period="2023", value_year=2023, period_source="explicit_period")
        validation = validate_semantic_calculation_program(program=program, obligations=[owner],
            candidate_catalog=catalog, query="2024 value")
        self.assertIn("context_conflicts_with_candidate", [e["code"] for e in validation["errors"]])

    def test_expression_inputs_and_source_display_share_grounded_period_view(self):
        _, catalog = parsed_catalog()
        current, prior = value(catalog), value(catalog, "90")
        owner = _obligation("a", "derived_value", "change",
            evidence_requirements=[_requirement("now", "current", period="2024"),
                                   _requirement("before", "previous", period="2023")])
        expression = {"obligation_id": "a", "formula": "A - B",
            "variable_bindings": [
                {"variable": "A", "source_id": current["candidate_id"], "source_requirement_id": "now",
                 "context_bindings": [context_binding(current)]},
                {"variable": "B", "source_id": prior["candidate_id"], "source_requirement_id": "before",
                 "context_bindings": [context_binding(prior, "전기 (단위: 백만원)", "2023")]},
            ], "source_display_candidate_id": None, "source_display_reason": "No displayed difference."}
        program = {"expressions": [expression]}
        before = deepcopy(program)
        result = execute_semantic_calculation_program(program=program, obligations=[owner],
            candidate_catalog=catalog, query="Difference of the two periods")
        self.assertEqual(result["status"], "ok", result["validation"]["errors"])
        self.assertEqual(result["outputs_by_obligation"]["a"]["normalized_value"], 10_000_000)
        self.assertEqual(program, before)
        expression.update(formula="A", variable_bindings=expression["variable_bindings"][:1],
            source_display_candidate_id=current["candidate_id"],
            source_display_reason="The same source value is displayed.",
            source_display_context_bindings=[context_binding(current)])
        owner.update(scope=_scope(period="2024"), evidence_requirements=owner["evidence_requirements"][:1])
        result = execute_semantic_calculation_program(program=program, obligations=[owner],
            candidate_catalog=catalog, query="Current reported value")
        self.assertEqual(result["status"], "ok", result["validation"]["errors"])
        self.assertTrue(result["validation"]["valid_expressions"][0]["source_display_context_resolution"])

    def test_exact_context_survives_payload_compaction_and_hydration(self):
        from src.storage.metadata_payloads import compact_node_for_storage, metadata_with_table_payload
        chunks, _ = parsed_catalog()
        payloads = {}
        metadata = chunks[0].metadata
        compact = compact_node_for_storage({"metadata": metadata}, payloads)
        hydrated = metadata_with_table_payload(compact["metadata"], payloads)
        self.assertEqual(json.loads(hydrated["table_object_json"])["source_contexts"],
                         json.loads(metadata["table_object_json"])["source_contexts"])

    def test_wrong_context_interpretation_does_not_evict_an_unknown_period_candidate(self):
        _, catalog = parsed_catalog()
        selected = value(catalog)
        explanation = next(c for c in selected["source_contexts"] if "2020년" in c["source_text"])
        program = {"direct_bindings": [{"obligation_id": "a", "candidate_id": selected["candidate_id"],
            "context_bindings": [{"context_id": explanation["context_id"], "evidence_text": "2020년",
                                  "field": "period", "value": "2020"}]}]}
        owner = _obligation("a", "direct_value", "current", scope=_scope(period="2024"))
        validation = validate_semantic_calculation_program(program=program, obligations=[owner],
            candidate_catalog=catalog, query="2024 value")
        self.assertFalse(validation["valid_direct_bindings"])
        self.assertTrue(all(e["repair_action"] == "repair_program" for e in validation["errors"]))
        self.assertEqual(_retry_candidate_exclusions(program=program, validation_errors=validation["errors"],
                         target_obligation_ids=["a"]), {})

    def test_mixed_old_and_enriched_attachments_choose_context_deterministically(self):
        chunks, _ = parsed_catalog()
        current = deepcopy(chunks[0].metadata)
        legacy = deepcopy(current)
        legacy["chunk_uid"] += "_legacy"
        table = json.loads(legacy["table_object_json"])
        for key in ("source_contexts", "source_table_locator", "source_document_sha256"):
            table.pop(key, None)
        legacy["table_object_json"] = json.dumps(table, ensure_ascii=False)
        docs = [(SimpleNamespace(page_content=chunks[0].content, metadata=m), 1.0) for m in (legacy, current)]
        def build(entries):
            sources = build_semantic_source_candidates({"retrieved_docs": entries},
                source_anchor_builder=lambda m: "[source]")
            return [c for c in build_semantic_candidate_catalog(sources) if c["kind"] == "numeric"]
        forward, reverse = build(docs), build(list(reversed(docs)))
        self.assertTrue(all(c.get("source_contexts") for c in forward))
        self.assertEqual(forward, reverse)

    def test_context_cannot_be_misattached_from_a_different_section_of_same_filing(self):
        _, catalog = parsed_catalog()
        current = value(catalog)
        other = next(c for c in catalog if c["kind"] == "numeric" and c["consolidation_scope"] == "separate")
        quote = context_binding(other)
        context = next(c for c in other["source_contexts"] if c["context_id"] == quote["context_id"])
        current["source_contexts"].append(deepcopy(context))
        program = {"direct_bindings": [{"obligation_id": "a", "candidate_id": current["candidate_id"],
                                       "context_bindings": [quote]}]}
        result = validate_semantic_calculation_program(program=program,
            obligations=[_obligation("a", "direct_value", "current", scope=_scope(period="2024"))],
            candidate_catalog=catalog, query="Current value")
        self.assertIn("context_not_attached_to_candidate", [e["code"] for e in result["errors"]])

    def test_context_retry_preserves_other_island_and_reuses_visible_ids(self):
        _, catalog = parsed_catalog()
        current, prior = value(catalog), value(catalog, "90")
        owners = [_obligation("a", "direct_value", "current", scope=_scope(period="2024")),
                  _obligation("b", "direct_value", "previous", scope=_scope(period="2023"))]
        first = {"obligation_id": "a", "candidate_id": current["candidate_id"],
                 "context_bindings": [context_binding(current)]}
        second = {"obligation_id": "b", "candidate_id": prior["candidate_id"],
                  "context_bindings": [context_binding(prior, "전기 (단위: 백만원)", "2023")]}
        wrong = deepcopy(second)
        wrong["context_bindings"][0]["evidence_text"] += " invented"
        llm = _StructuredQueueLLM(*[SemanticCalculationProgram.model_validate({"direct_bindings": [binding]})
                                    for binding in (first, wrong, second)])
        agent = object.__new__(FinancialAgent)
        agent.llm, agent.llm_routes, agent.llm_usage_callback = llm, {}, None
        state = {"query": "Return both values", "answer_obligations": owners,
            "semantic_plan": {"program_required": True, "answer_obligations": owners},
            "active_subtask": {"task_id": "task"}, "tasks": [], "artifacts": [], "resolved_calculation_trace": {}}
        with patch.object(agent, "_semantic_candidate_catalog_for_state", return_value=catalog):
            compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        actual = next(b for b in compiled["semantic_program"]["direct_bindings"] if b["obligation_id"] == "a")
        self.assertEqual(json.dumps(actual["context_bindings"], ensure_ascii=False),
                         json.dumps(first["context_bindings"], ensure_ascii=False))
        attempts = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]["attempts"]
        retry = [a for a in attempts if a["island_id"] == "island_002"]
        self.assertEqual(retry[0]["visible_candidate_ids"], retry[1]["visible_candidate_ids"])
        self.assertEqual(retry[0]["source_context_fingerprint"], retry[1]["source_context_fingerprint"])


if __name__ == "__main__":
    unittest.main()
