"""No-call characterization, not a repair or a benchmark acceptance oracle.

The invented fixture exercises existing owners in production order. Assertions
named ``characterizes`` pin gaps that a separately approved repair must replace;
the other assertions retain the current fail-closed contracts.
"""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.semantic_program_test_support import execute_semantic_calculation_program, execute_compiled_fixture
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_model_loaders import validate_answer_slots_payload
from src.agent.financial_graph_models import AnswerObligation, SemanticCalculationProgram
from src.agent.financial_run_result import (
    FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
    FinancialRunResultV1,
)
from src.agent.financial_task_artifacts import project_task_artifact_trace
from src.ops.evaluator import (
    EvalCalculationVariant,
    EvalExample,
    RAGEvaluator,
    _compute_accepted_calculation_variant_match,
    _compute_completeness_judge,
    _compute_numeric_evaluation,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "scope_qualified_direct_answers.json"


class _FixedCompiler:
    def __init__(self, program, expected_calls, obligation_ids):
        self.response = SemanticCalculationProgram.model_validate(program)
        self.expected_calls = expected_calls
        self.obligation_ids = list(obligation_ids)
        self.models = []
        self.prompts = []

    def with_structured_output(self, model):
        self.models.append(model.__name__)
        return self

    def invoke(self, prompt):
        if len(self.prompts) >= self.expected_calls:
            raise AssertionError("unexpected extra compiler call")
        self.prompts.append(prompt)
        prompt_text = (
            prompt.to_string()
            if callable(getattr(prompt, "to_string", None))
            else str(prompt)
        )
        target_ids = [
            obligation_id
            for obligation_id in self.obligation_ids
            if f'"obligation_id": "{obligation_id}"' in prompt_text
        ]
        if not target_ids:
            raise AssertionError("expected at least one island obligation")
        response = self.response.model_dump()
        response["direct_bindings"] = [
            row
            for row in response.get("direct_bindings") or []
            if row.get("obligation_id") in target_ids
        ]
        response["expressions"] = [
            row
            for row in response.get("expressions") or []
            if row.get("obligation_id") in target_ids
        ]
        response["narrative_bindings"] = [
            row
            for row in response.get("narrative_bindings") or []
            if row.get("obligation_id") in target_ids
        ]
        response["missing_obligation_ids"] = [
            value
            for value in response.get("missing_obligation_ids") or []
            if value in target_ids
        ]
        response["ambiguous_obligation_ids"] = [
            value
            for value in response.get("ambiguous_obligation_ids") or []
            if value in target_ids
        ]
        has_binding = any(
            response.get(key)
            for key in ("direct_bindings", "expressions", "narrative_bindings")
        )
        response["status"] = (
            "ready"
            if has_binding
            and not response["missing_obligation_ids"]
            and not response["ambiguous_obligation_ids"]
            else "incomplete"
        )
        return SemanticCalculationProgram.model_validate(response)


class _FixedCompletenessJudge:
    """Capture the real prompt; the score is fixture input, not a judgement."""

    def __init__(self):
        self.prompts = []

    def invoke(self, prompt):
        if self.prompts:
            raise AssertionError("unexpected extra judge call")
        self.prompts.append(prompt)
        return SimpleNamespace(content='{"score": 0.5, "reason": "fixed fixture score"}')


def _run_result_from_state(state):
    answer_fields = {
        "answer",
        "query_type",
        "intent",
        "format_preference",
        "routing_source",
        "routing_confidence",
        "routing_scores",
        "citations",
        "structured_result",
        "resolved_calculation_trace",
    }
    review_fields = {
        "retrieved_docs",
        "retrieval_debug_trace",
        "retrieval_debug_trace_history",
        "evidence_items",
        "selected_claim_ids",
        "draft_points",
        "kept_claim_ids",
        "dropped_claim_ids",
        "unsupported_sentences",
        "sentence_checks",
        "numeric_debug_trace",
        "numeric_debug_trace_history",
        "task_artifact_trace",
    }
    return FinancialRunResultV1(
        schema_version=FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
        agent_answer={key: deepcopy(value) for key, value in state.items() if key in answer_fields},
        review_trace={key: deepcopy(value) for key, value in state.items() if key in review_fields},
        debug_bundle={},
    )


class ScopeQualifiedDirectAnswerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.catalog = self._catalog()

    def _catalog(self):
        rows = []
        for basis in self.fixture["bases"]:
            for output in self.fixture["outputs"]:
                source = basis["source"]
                obligation_id = output["obligation_id"]
                candidate_id = f"cand-{source}-{obligation_id}"
                value = basis["values"][obligation_id]
                rows.append({
                    "candidate_id": candidate_id,
                    "kind": "numeric",
                    "source_candidate_id": f"source-{candidate_id}",
                    "evidence_id": f"evidence-{candidate_id}",
                    "source_anchor": f"[Sample issuer | 2024 | {source}]",
                    "source_row_id": f"row-{source}-alpha",
                    "table_source_id": f"table-{source}",
                    "context_fingerprint": source,
                    "row_label": self.fixture["subject"],
                    "row_headers": [self.fixture["subject"]],
                    "statement_type": "notes",
                    "company": self.fixture["company"],
                    "year": int(self.fixture["period"]),
                    "period": self.fixture["period"],
                    "column_headers": [self.fixture["period"], output["label"]],
                    "consolidation_scope": basis["scope"],
                    "segment": "",
                    "basis": "",
                    "source_text": f"Unit Alpha 2024 {output['label']} {value}{output['raw_unit']}",
                    "candidate_kind": "structured_value",
                    "raw_value": str(value),
                    "raw_unit": output["raw_unit"],
                    "normalized_value": float(value * output["scale"]),
                    "normalized_unit": output["normalized_unit"],
                })
        rows.append({
            **deepcopy(rows[0]),
            "candidate_id": "cand-other-subject",
            "source_candidate_id": "source-other-subject",
            "evidence_id": "evidence-other-subject",
            "source_row_id": "row-group-note-beta",
            "row_label": "Unit Beta",
            "row_headers": ["Unit Beta"],
            "raw_value": "67",
            "normalized_value": 67.0,
            "source_text": "Unit Beta 2024 67%. Elsewhere in this table: Unit Alpha 40%.",
        })
        return rows

    def _obligations(self, scope="unknown", coupling_key=""):
        return [AnswerObligation.model_validate({
            "obligation_id": output["obligation_id"],
            "kind": "direct_value",
            "label": output["label"],
            "required": True,
            "display_unit": output["raw_unit"],
            "scope": {
                "company": self.fixture["company"],
                "period": self.fixture["period"],
                "consolidation_scope": scope,
                "segment": self.fixture["subject"],
                "basis": "",
            },
            "coupling_key": coupling_key,
        }).model_dump() for output in self.fixture["outputs"]]

    def _program(self, name):
        return SemanticCalculationProgram.model_validate(
            self.fixture["programs"][name]
        ).model_dump()

    def _execute(self, name="consolidated", *, obligations=None, catalog=None, program=None, query=None):
        inputs = {
            "program": self._program(name) if program is None else program,
            "obligations": self._obligations() if obligations is None else obligations,
            "candidate_catalog": self.catalog if catalog is None else catalog,
            "query": self.fixture["query"] if query is None else query,
        }
        before = deepcopy(inputs)
        result = execute_semantic_calculation_program(**inputs)
        self.assertEqual(inputs, before, "execution must not mutate fixed evidence or plans")
        return result

    def _scalar_execution(self, name="consolidated"):
        program = self._program(name)
        program["direct_bindings"] = [
            row for row in program["direct_bindings"] if row["obligation_id"] == "ob_amount"
        ]
        return self._execute(
            name, program=program, obligations=[self._obligations()[1]],
            query=self.fixture["single_query"],
        )

    def _graph(self, name="consolidated"):
        program = self._program(name)
        expected_calls = 2 if name in {"wrong_subject", "missing_share"} else 1
        obligations = self._obligations()
        llm = _FixedCompiler(
            program,
            expected_calls,
            [row["obligation_id"] for row in obligations],
        )
        agent = object.__new__(FinancialAgent)
        agent.llm = llm
        agent.llm_routes = {}
        agent.llm_usage_callback = None
        state = {
            "query": self.fixture["query"],
            "query_type": "business_overview",
            "intent": "business_overview",
            "topic": "unit profile",
            "format_preference": "mixed",
            "report_scope": {},
            "answer_obligations": obligations,
            "semantic_plan": {"program_required": True, "answer_obligations": obligations},
            "semantic_program": program,
            "semantic_candidate_catalog": deepcopy(self.catalog),
            "active_subtask": {
                "task_id": "task_1", "metric_family": "semantic_program",
                "metric_label": "unit profile", "query": self.fixture["query"],
            },
            "tasks": [], "artifacts": [], "evidence_items": [],
            "retrieved_docs": [], "seed_retrieved_docs": [],
            "planner_debug_trace": {}, "resolved_calculation_trace": {},
        }
        with patch.object(agent, "_semantic_candidate_catalog_for_state", return_value=deepcopy(self.catalog)):
            state.update(agent._compile_semantic_calculation_program(state))
        self.assertEqual(llm.models, ["SemanticCalculationProgram"])
        self.assertEqual(len(llm.prompts), expected_calls)
        self.assertEqual(state["semantic_program_retry_count"], expected_calls - 1)
        state.update(execute_compiled_fixture(agent, state, state["semantic_candidate_catalog"]))
        state.update(agent._format_citations(state))
        ledger = project_task_artifact_trace(state["tasks"], state["artifacts"])
        self.assertEqual(ledger["integrity_status"], "ok")
        trace = state["resolved_calculation_trace"]
        for key in ("calculation_operands", "calculation_plan", "calculation_result"):
            self.assertEqual(trace[key], state["structured_result"]["resolved_calculation_trace"][key])
        validate_answer_slots_payload(trace["calculation_result"]["answer_slots"])
        return state

    def _variant(self, basis_name, obligation_ids=("ob_amount",)):
        basis = next(row for row in self.fixture["bases"] if row["scope"] == basis_name)
        expected = []
        answer_values = []
        expected_result = {}
        for output in self.fixture["outputs"]:
            obligation_id = output["obligation_id"]
            if obligation_id not in obligation_ids:
                continue
            expected.append({
                "label": self.fixture["subject"], "strict_label": True,
                "period": self.fixture["period"],
                "raw_value": str(basis["values"][obligation_id]),
                "raw_unit": output["raw_unit"],
                "source_anchor_contains": basis["source"],
                "table_source_id_contains": f"table-{basis['source']}",
                "consolidation_scope": basis_name,
            })
            answer_values.append(f"{output['label']} {basis['values'][obligation_id]}{output['raw_unit']}")
            expected_result = {
                **expected[-1], "label": output["label"],
                "matched_operand_role": obligation_id, "operation_family": "lookup",
            }
        return EvalCalculationVariant(
            id=f"{basis_name}-answer",
            answer_key=f"{basis['display_label']}: {', '.join(answer_values)}",
            expected_operands=expected,
            expected_operation="lookup",
            expected_calculation_result=expected_result,
        )

    def _example(self, obligation_ids=("ob_amount",), *, mixed=False):
        variants = [self._variant(basis["scope"], obligation_ids) for basis in self.fixture["bases"]]
        return EvalExample(
            id="synthetic-scope-qualified-direct",
            question=self.fixture["single_query"] if obligation_ids == ("ob_amount",) else self.fixture["query"],
            ground_truth=variants[1].answer_key,
            answer_key=variants[1].answer_key,
            company=self.fixture["company"],
            year=int(self.fixture["period"]),
            section="sample notes",
            answer_type="mixed" if mixed else "numeric",
            category="business_overview" if mixed else "numeric_fact",
            accepted_calculation_variants=variants,
        )

    def _match(self, example, execution):
        return _compute_accepted_calculation_variant_match(
            example=example,
            calculation_operands=execution["calculation_operands"],
            calculation_plan={"mode": "semantic_program", "operation_family": "lookup"},
            calculation_result=execution["calculation_result"],
        )

    def _numeric(self, example, execution, answer):
        return _compute_numeric_evaluation(
            llm=None, example=example, answer=answer,
            runtime_evidence=[], contexts=[row["source_text"] for row in self.catalog],
            calculation_operands=execution["calculation_operands"],
            calculation_plan={"mode": "semantic_program", "operation_family": "lookup"},
            calculation_result=execution["calculation_result"],
            retrieval_hit_at_k=1.0, deterministic_grounding_only=True,
        )

    def test_discloses_selected_basis_for_unqualified_direct_answer(self):
        for basis in self.fixture["bases"]:
            with self.subTest(basis=basis["scope"]):
                execution = self._execute(basis["scope"])
                self.assertEqual(execution["status"], "ok")
                self.assertEqual(execution["missing_obligation_ids"], [])
                for output in execution["outputs"]:
                    self.assertEqual(output["answer_slot"]["consolidation_scope"], basis["scope"])
                    self.assertIn(basis["source"], output["source_anchors"][0])
                    self.assertEqual(output["answer_slot"]["raw_value"], str(basis["values"][output["obligation_id"]]))
                    self.assertEqual(output["candidate_ids"], [f"cand-{basis['source']}-{output['obligation_id']}"])
                self.assertEqual(
                    execution["answer"].replace(" ", "").count(basis["display_label"]),
                    1,
                )

    def test_discloses_selected_basis_for_english_direct_answer(self):
        expected_labels = {
            "consolidated": "consolidated basis",
            "separate": "separate basis",
        }
        for basis in self.fixture["bases"]:
            with self.subTest(basis=basis["scope"]):
                execution = self._execute(
                    basis["scope"], query=self.fixture["english_query"]
                )
                self.assertEqual(execution["status"], "ok")
                self.assertEqual(
                    execution["answer"].count(expected_labels[basis["scope"]]),
                    1,
                )
                for output in self.fixture["outputs"]:
                    self.assertIn(output["label"], execution["answer"])

    def test_unknown_selected_basis_is_not_filled_from_unselected_candidates(self):
        catalog = deepcopy(self.catalog)
        for candidate in catalog:
            if candidate["candidate_id"].startswith("cand-group-note-"):
                candidate["consolidation_scope"] = "unknown"
        execution = self._execute(catalog=catalog)
        self.assertEqual(execution["status"], "ok")
        self.assertNotIn("연결기준", execution["answer"].replace(" ", ""))
        self.assertNotIn("별도기준", execution["answer"].replace(" ", ""))

    def test_explicit_basis_is_rendered_and_rejects_conflicting_candidates(self):
        for basis in self.fixture["bases"]:
            with self.subTest(basis=basis["scope"]):
                obligations = self._obligations(basis["scope"])
                accepted = self._execute(basis["scope"], obligations=obligations)
                self.assertEqual(accepted["status"], "ok")
                self.assertIn(basis["display_label"], accepted["answer"])
                other = "separate" if basis["scope"] == "consolidated" else "consolidated"
                rejected = self._execute(other, obligations=obligations)
                self.assertNotEqual(rejected["status"], "ok")
                self.assertEqual(rejected["outputs"], [])
                self.assertIn("candidate_scope_mismatch", {row["code"] for row in rejected["validation"]["errors"]})

    def test_explicit_company_period_and_measurement_basis_still_fail_closed(self):
        for field, conflicting_value in (("company", "Other issuer"), ("period", "2023"), ("basis", "gross")):
            with self.subTest(field=field):
                catalog = deepcopy(self.catalog)
                obligations = self._obligations()
                if field == "basis":
                    obligations[1]["scope"]["basis"] = "net"
                catalog[1][field] = conflicting_value
                if field == "period":
                    catalog[1]["column_headers"] = [conflicting_value]
                execution = self._execute(obligations=obligations, catalog=catalog)
                self.assertEqual(execution["status"], "partial")
                self.assertEqual(execution["missing_obligation_ids"], ["ob_amount"])
                self.assertTrue(any(row["code"] == "candidate_scope_mismatch" and field in row["detail"] for row in execution["validation"]["errors"]))

    def test_wrong_row_id_is_not_repaired_by_rationale_or_table_wide_text(self):
        state = self._graph("wrong_subject")
        self.assertEqual(state["structured_result"]["status"], "partial")
        self.assertEqual(state["missing_info"], ["ob_share"])
        validation_history = state["resolved_calculation_trace"]["calculation_plan"][
            "program_validation_history"
        ]
        self.assertIn(
            "candidate_subject_mismatch",
            {
                error["code"]
                for attempt in validation_history
                for error in attempt.get("errors") or []
            },
        )
        self.assertNotIn("67%", state["answer"])
        self.assertNotIn("40%", state["answer"])
        self.assertNotIn("cand-other-subject", state["selected_claim_ids"])
        self.assertIn("120백만원", state["answer"])
        equal_value_catalog = deepcopy(self.catalog)
        equal_value_catalog[-1].update({"raw_value": "40", "normalized_value": 40.0})
        equal_value_catalog[-1]["source_text"] = "Unit Beta 2024 40%. Elsewhere: Unit Alpha 40%."
        equal_value = self._execute("wrong_subject", catalog=equal_value_catalog)
        self.assertEqual(equal_value["status"], "partial")
        self.assertEqual(equal_value["missing_obligation_ids"], ["ob_share"])
        self.assertNotIn("40%", equal_value["answer"])

    def test_missing_required_output_is_partial_even_with_valid_ledger(self):
        state = self._graph("missing_share")
        self.assertEqual(state["structured_result"]["status"], "partial")
        self.assertEqual(state["missing_info"], ["ob_share"])
        self.assertEqual(len(state["subtask_results"]), 1)
        self.assertEqual(state["subtask_results"][0]["status"], "ok")

    def test_characterizes_independent_cross_basis_outputs_not_an_atomic_answer(self):
        execution = self._execute("cross_basis")
        self.assertEqual(execution["status"], "ok")
        self.assertEqual([row["answer_slot"]["consolidation_scope"] for row in execution["outputs"]], ["consolidated", "separate"])
        self.assertEqual(execution["answer"].replace(" ", "").count("연결기준"), 1)
        self.assertEqual(execution["answer"].replace(" ", "").count("별도기준"), 1)
        match, _, _ = self._match(self._example(("ob_share", "ob_amount")), execution)
        self.assertEqual(match, 0.0)

    def test_coupled_outputs_do_not_accept_cross_basis_contexts(self):
        obligations = self._obligations(coupling_key="common-basis")
        self.assertEqual(self._execute(obligations=obligations)["status"], "ok")
        execution = self._execute("cross_basis", obligations=obligations)
        self.assertEqual(execution["status"], "incomplete")
        self.assertEqual(
            {row["code"] for row in execution["validation"]["errors"]},
            {"coupled_context_mismatch"},
        )

    def test_missing_unit_is_not_recovered_from_a_lookalike_basis(self):
        catalog = deepcopy(self.catalog)
        catalog[1]["raw_unit"] = ""
        catalog[1]["normalized_unit"] = "UNKNOWN"
        obligations = self._obligations()
        obligations[1]["display_unit"] = ""
        execution = self._execute(catalog=catalog, obligations=obligations)
        self.assertEqual(execution["status"], "partial")
        self.assertEqual(execution["missing_obligation_ids"], ["ob_amount"])
        self.assertIn("empty_direct_rendering", {row["code"] for row in execution["validation"]["errors"]})

    def test_scalar_variants_bind_each_value_to_its_own_basis_and_source(self):
        for basis in self.fixture["bases"]:
            with self.subTest(basis=basis["scope"]):
                execution = self._scalar_execution(basis["scope"])
                match, variant_id, _ = self._match(self._example(), execution)
                self.assertEqual(match, 1.0)
                self.assertEqual(variant_id, f"{basis['scope']}-answer")

    def test_equal_values_do_not_override_wrong_basis_or_source_constraints(self):
        execution = self._scalar_execution()
        for field, value in (("consolidation_scope", "separate"), ("source_anchor_contains", "standalone-note"), ("period", "2023")):
            with self.subTest(field=field):
                example = self._example()
                example.accepted_calculation_variants = [example.accepted_calculation_variants[0]]
                example.accepted_calculation_variants[0].expected_operands[0][field] = value
                match, _, _ = self._match(example, execution)
                self.assertEqual(match, 0.0)

    def test_numeric_answer_and_trace_must_match_the_same_scalar_variant(self):
        execution = self._scalar_execution()
        example = self._example()
        matched = self._numeric(example, execution, example.accepted_calculation_variants[0].answer_key)
        mismatched = self._numeric(example, execution, example.accepted_calculation_variants[1].answer_key)
        self.assertEqual(matched["accepted_calculation_variant_match"], 1.0)
        self.assertEqual(mismatched["accepted_calculation_variant_match"], 0.0)

    def test_characterizes_numeric_equivalence_not_basis_disclosure_validation(self):
        execution = self._scalar_execution()
        example = self._example()
        labelled = self._numeric(example, execution, example.accepted_calculation_variants[0].answer_key)
        unlabelled = self._numeric(example, execution, "보고 금액 120백만원")
        falsely_labelled = self._numeric(example, execution, "별도 기준: 보고 금액 120백만원")
        for result in (labelled, unlabelled, falsely_labelled):
            self.assertEqual(result["accepted_calculation_variant_match"], 1.0)
        # This numeric-only result cannot certify the semantic basis claim.

    def test_characterizes_scalar_variant_schema_cannot_certify_a_direct_output_tuple(self):
        execution = self._execute()
        example = self._example(("ob_share", "ob_amount"))
        match, _, debug = self._match(example, execution)
        self.assertEqual(execution["status"], "ok")
        self.assertEqual(match, 0.0)
        consolidated = debug["variants"][0]
        self.assertEqual(consolidated["matched_operand_count"], 2)
        self.assertFalse(consolidated["result_matched"])
        self.assertTrue(any("result_not_bound_to_all_matched_operands" in row["reasons"] for row in consolidated["results"]))

    def test_characterizes_completeness_prompt_ignores_trace_matched_scalar_variant(self):
        execution = self._scalar_execution()
        example = self._example()
        match, variant_id, _ = self._match(example, execution)
        self.assertEqual((match, variant_id), (1.0, "consolidated-answer"))
        judge = _FixedCompletenessJudge()
        score, reason = _compute_completeness_judge(judge, example, "보고 금액 120백만원")
        self.assertEqual((score, reason), (0.5, "fixed fixture score"))
        self.assertIn(example.canonical_answer_key, judge.prompts[0])
        self.assertNotIn(example.accepted_calculation_variants[0].answer_key, judge.prompts[0])
        self.assertNotIn("group-note", judge.prompts[0])

    def test_fixed_compiler_graph_and_mixed_evaluator_keep_gap_and_raw_scores_visible(self):
        state = self._graph()
        self.assertEqual(state["structured_result"]["status"], "ok")
        self.assertEqual(len(state["selected_claim_ids"]), 2)
        self.assertEqual(state["answer"].replace(" ", "").count("연결기준"), 1)
        self.assertTrue(any("group-note" in citation for citation in state["citations"]))
        example = self._example(("ob_share", "ob_amount"), mixed=True)
        before = deepcopy(example)
        judge = _FixedCompletenessJudge()
        with (
            patch("src.ops.evaluator._chat_google_generative_ai", side_effect=AssertionError("provider construction forbidden")),
            patch("src.ops.evaluator._create_embeddings", side_effect=AssertionError("embedding construction forbidden")),
            patch("src.ops.evaluator._compute_faithfulness", return_value=0.7),
            patch("src.ops.evaluator._compute_trend_interpretation_correctness", return_value=(None, "not applicable")),
        ):
            evaluator = RAGEvaluator(
                SimpleNamespace(
                    run=lambda *_args, **_kwargs: _run_result_from_state(state)
                ),
                skip_llm_judges=True,
            )
            evaluator.skip_llm_judges = False
            evaluator._llm = judge
            result = evaluator.evaluate_one(example)
        self.assertIsNone(result.error)
        self.assertEqual((result.raw_faithfulness, result.faithfulness), (0.7, 0.7))
        self.assertFalse(result.faithfulness_override_reason)
        self.assertEqual(result.completeness, 0.5)
        self.assertEqual(result.completeness_reason, "fixed fixture score")
        self.assertIsNone(result.numeric_final_judgement)
        self.assertEqual(len(judge.prompts), 1)
        self.assertIn(example.canonical_answer_key, judge.prompts[0])
        self.assertNotIn(example.accepted_calculation_variants[0].answer_key, judge.prompts[0])
        self.assertEqual(example, before)


if __name__ == "__main__":
    unittest.main()
