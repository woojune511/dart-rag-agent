import json
import subprocess
import sys
import unittest
from collections.abc import Mapping
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.evaluator import (
    _build_operand_grounding_corpus,
    _build_runtime_evidence_contexts,
    _prioritize_runtime_evidence_contexts,
    _build_example_report_scope,
    _collect_aggregate_subtask_provenance,
    _compute_runtime_evidence_retrieval_hit_at_k,
    _compute_runtime_evidence_section_match_rate,
    _compute_runtime_evidence_citation_coverage,
    _compute_entity_coverage,
    _compute_ndcg_at_k,
    _contains_section,
    _compute_calculation_correctness,
    _compute_grounded_rendering_correctness,
    _compute_numeric_result_correctness,
    _compute_operand_selection_correctness,
    _compute_unit_consistency_pass,
    _normalise_math_operand_value,
    _numeric_values_equivalent,
    _operand_matches,
    EvalEvidence,
    EvalExample,
    RAGEvaluator,
    _format_runtime_evidence_for_numeric_judge,
    _looks_like_missing_answer,
    _resolve_evaluator_operands,
    _resolve_runtime_calculation_trace,
    _supplement_resolved_operands_from_runtime_evidence,
    _should_override_numeric_faithfulness,
    _should_override_numeric_grounding,
    _should_override_numeric_grounding_from_runtime_evidence,
)
from src.agent import financial_runtime_trace
from src.agent.financial_run_result import (
    FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
    FinancialRunResultV1,
)
from src.agent.financial_runtime_trace import runtime_trace_state_update


class _DummyDoc:
    def __init__(self, metadata: dict) -> None:
        self.metadata = metadata


class _FakeAgent:
    def __init__(self, result: dict) -> None:
        self.result = result

    def run(
        self,
        question: str,
        *,
        report_scope=None,
        include_review_trace=False,
        include_debug_bundle=False,
    ) -> FinancialRunResultV1:
        answer_fields = {
            "answer",
            "query_type",
            "intent",
            "format_preference",
            "routing_source",
            "routing_confidence",
            "routing_scores",
            "citations",
            "resolved_calculation_trace",
            "structured_result",
        }
        return FinancialRunResultV1(
            schema_version=FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
            agent_answer={
                key: value
                for key, value in self.result.items()
                if key in answer_fields
            },
            review_trace={} if include_review_trace else None,
            debug_bundle={} if include_debug_bundle else None,
        )


class _FailingAgent:
    def run(
        self,
        question: str,
        *,
        report_scope=None,
        include_review_trace=False,
        include_debug_bundle=False,
    ) -> FinancialRunResultV1:
        raise RuntimeError("model unavailable")


class EvaluatorRuntimeProjectionTests(unittest.TestCase):
    def _evaluate_fixed_qualitative_score(
        self, *, question, answer, raw_score, answer_type="summary", category="comparison",
        format_preference="mixed", narrative=True, numeric_fast_gate=False,
    ):
        evidence = [
            {"claim": "Quantity increased by 10% to 44 items.", "support_level": "direct"},
            {"claim": "The unit introduced a review stage with coverage of 75%.", "support_level": "direct"},
        ]
        outputs = [{"kind": "derived_value", "status": "ok"}]
        if narrative:
            outputs.append({"kind": "narrative", "status": "ok"})
        evaluator = RAGEvaluator(
            _FakeAgent({
                "answer": answer, "format_preference": format_preference,
                "evidence_items": evidence,
                "resolved_calculation_trace": {
                    "calculation_plan": {"mode": "semantic_program"},
                    "calculation_result": {"status": "ok", "outputs": outputs},
                },
            }),
            skip_llm_judges=True,
            numeric_fast_gate=numeric_fast_gate,
        )
        # Construct no provider; only replace judge/metric results, not promotion policy.
        evaluator.skip_llm_judges = False
        evaluator._llm = Mock()
        evaluator._llm.invoke.side_effect = AssertionError("provider call forbidden")
        example = EvalExample(
            id="generic-judgement-boundary", question=question, ground_truth="10%; review stage",
            company="sample", year=2024, section="activity",
            category=category, answer_type=answer_type,
        )
        values = {
            "_compute_faithfulness": raw_score,
            "_compute_completeness_judge": (1.0, "fixed completeness result"),
            "_compute_context_recall": 1.0,
            "_compute_retrieval_hit_at_k": 1.0,
            "_compute_section_match_rate": 1.0,
            "_compute_citation_coverage": 1.0,
            "_compute_numeric_result_correctness": 1.0,
            "_compute_grounded_rendering_correctness": (1.0, "fixed numeric rendering result"),
            "_compute_trend_interpretation_correctness": (1.0, "fixed trend result"),
            "_compute_numeric_evaluation": {
                "numeric_final_judgement": "PASS", "numeric_equivalence": 1.0,
                "numeric_grounding": 1.0, "numeric_retrieval_support": 1.0,
            },
        }
        with ExitStack() as stack:
            mocks = {
                name: stack.enter_context(patch(f"src.ops.evaluator.{name}", return_value=value))
                for name, value in values.items()
            }
            result = evaluator.evaluate_one(example)
        evaluator._llm.invoke.assert_not_called()
        self.assertIsNone(result.error)
        self.assertEqual(result.calculation_correctness, 1.0)
        self.assertEqual(result.completeness, 1.0)
        self.assertEqual(result.context_recall, 1.0)
        return result, mocks["_compute_faithfulness"]

    def test_coverage_cannot_promote_qualitative_faithfulness_in_evaluate_one(self) -> None:
        cases = (
            ("증가율을 계산하고 작업 변경의 원인을 설명해 줘.", "comparison",
             "Quantity increased by 10%; review coverage was 75%, which caused the increase."),
            ("Summarize the quantity and activity change.", "business_overview",
             "Quantity increased by 10%; review coverage was 75%, which caused the increase."),
            ("Summarize the activity change.", "business_overview",
             "The review stage caused the improvement."),
        )
        for question, category, answer in cases:
            for raw_score in (0.0, 0.4, 0.7, 1.0):
                with self.subTest(question=question, raw_score=raw_score):
                    result, judge = self._evaluate_fixed_qualitative_score(
                        question=question, answer=answer, category=category, raw_score=raw_score,
                    )
                    judge.assert_called_once()
                    self.assertEqual(result.raw_faithfulness, raw_score)
                    self.assertEqual(result.faithfulness, raw_score)
                    self.assertIsNone(result.faithfulness_override_reason)

    def test_numeric_pass_and_fast_gate_cannot_bypass_mixed_qualitative_judge(self) -> None:
        for format_preference, narrative in (("mixed", True), ("mixed", False), ("table", True)):
            for numeric_fast_gate in (False, True):
                with self.subTest(format=format_preference, narrative=narrative, fast=numeric_fast_gate):
                    result, judge = self._evaluate_fixed_qualitative_score(
                        question="Return the quantity change and explain the review stage.",
                        answer="Quantity increased by 10%; review coverage was 75%, which caused the increase.",
                        raw_score=0.4, answer_type="numeric", category="numeric_fact",
                        format_preference=format_preference, narrative=narrative,
                        numeric_fast_gate=numeric_fast_gate,
                    )
                    judge.assert_called_once()
                    self.assertEqual(result.numeric_final_judgement, "PASS")
                    self.assertEqual(result.raw_faithfulness, 0.4)
                    self.assertEqual(result.faithfulness, 0.4)
                    self.assertIsNone(result.faithfulness_override_reason)

    def test_pure_numeric_pass_retains_its_existing_faithfulness_gate(self) -> None:
        for fast_gate in (False, True):
            with self.subTest(fast_gate=fast_gate):
                result, judge = self._evaluate_fixed_qualitative_score(
                    question="Return the quantity change.", answer="10%", raw_score=0.4,
                    answer_type="numeric", category="numeric_fact",
                    format_preference="table", narrative=False, numeric_fast_gate=fast_gate,
                )
                self.assertEqual(result.faithfulness, 1.0)
                if fast_gate:
                    judge.assert_not_called()
                    self.assertIsNone(result.raw_faithfulness)
                else:
                    judge.assert_called_once()
                    self.assertEqual(result.raw_faithfulness, 0.4)

    def test_faithfulness_context_prioritizes_final_runtime_evidence(self) -> None:
        broad_contexts = [
            "retrieved chunk one",
            "retrieved chunk two",
        ]
        runtime_evidence = [
            {
                "claim": "The selected result increased by 11.5%.",
                "quote_span": "increased by 11.5%",
                "source_anchor": "ExampleCo | 2023 | Management Discussion",
            }
        ]

        contexts = _prioritize_runtime_evidence_contexts(broad_contexts, runtime_evidence)

        self.assertIn("selected result increased by 11.5%", contexts[0])
        self.assertEqual(contexts[1:], broad_contexts)

    def test_faithfulness_context_compacts_duplicate_payloads_before_global_budget(self) -> None:
        runtime_evidence = []
        for index in range(4):
            claim = (
                f"[source: filing] [table_context: {'x' * 700}] "
                f"[Heading {index}] relation-{index} "
                + ("supporting detail " * 45)
            )
            runtime_evidence.append(
                {
                    "claim": claim,
                    "quote_span": claim,
                    "source_anchor": f"ExampleCo | 2023 | Section {index}",
                }
            )

        contexts = _build_runtime_evidence_contexts(runtime_evidence)
        judge_window = "\n\n---\n\n".join(contexts)[:4000]

        self.assertNotIn("[table_context:", judge_window)
        self.assertIn("[Heading 0]", judge_window)
        for index in range(4):
            self.assertIn(f"relation-{index}", judge_window)

    def test_numeric_faithfulness_override_does_not_cover_narrative_output(self) -> None:
        numeric_eval = {
            "numeric_final_judgement": "PASS",
            "numeric_equivalence": 1.0,
            "numeric_grounding": 1.0,
            "numeric_retrieval_support": 1.0,
        }

        self.assertTrue(
            _should_override_numeric_faithfulness(
                numeric_eval,
                calculation_result={"outputs": [{"kind": "derived_value", "status": "ok"}]},
                format_preference="table",
            )
        )
        self.assertFalse(
            _should_override_numeric_faithfulness(
                numeric_eval,
                calculation_result={"outputs": [{"kind": "derived_value", "status": "ok"}]},
                format_preference="mixed",
            )
        )
        self.assertFalse(
            _should_override_numeric_faithfulness(
                numeric_eval,
                calculation_result={
                    "outputs": [
                        {"kind": "derived_value", "status": "ok"},
                        {"kind": "narrative", "status": "ok"},
                    ]
                },
                format_preference="mixed",
            )
        )

    def test_missing_answer_detection_uses_refusal_phrases_not_bare_substrings(self) -> None:
        self.assertFalse(_looks_like_missing_answer("차별화된 기술 개발을 통해 끊임없는 혁신을 추구합니다."))
        self.assertTrue(_looks_like_missing_answer("관련 정보가 없습니다."))
        self.assertTrue(_looks_like_missing_answer("현재 근거만으로는 확인하기 어렵습니다."))
        self.assertTrue(_looks_like_missing_answer("질문에 답할 근거를 찾지 못했습니다."))

    def test_operand_row_material_numeric_payload_preserves_value_policy(self) -> None:
        has_material = financial_runtime_trace.operand_row_has_material_numeric_payload

        cases = (
            ("missing status", {"status": " missing ", "normalized_value": 1}, False),
            ("unknown short raw", {"normalized_unit": "UNKNOWN", "raw_value": "123"}, False),
            ("unknown four digits", {"normalized_unit": "UNKNOWN", "raw_value": "1,234"}, True),
            (
                "whitespace raw unit suppresses fallback",
                {"raw_unit": " ", "unit": "count", "normalized_unit": "UNKNOWN", "raw_value": "123"},
                False,
            ),
            (
                "empty raw unit uses fallback",
                {"raw_unit": "", "unit": " count ", "normalized_unit": "UNKNOWN", "raw_value": "123"},
                True,
            ),
            (
                "display fallback",
                {
                    "normalized_unit": "UNKNOWN",
                    "raw_value": "",
                    "value": "",
                    "rendered_value": "",
                    "display_value": "1234",
                },
                True,
            ),
            ("zero normalized value", {"normalized_unit": "COUNT", "normalized_value": 0}, True),
            ("known unit without value", {"normalized_unit": "COUNT"}, False),
            ("unit with nonnumeric raw", {"raw_unit": "unit", "raw_value": "value"}, True),
        )
        for name, row, expected in cases:
            with self.subTest(name=name):
                before = deepcopy(row)
                self.assertEqual(has_material(row), expected)
                self.assertEqual(row, before)

    def test_operand_row_material_numeric_payload_preserves_access_and_exception_contract(self) -> None:
        has_material = financial_runtime_trace.operand_row_has_material_numeric_payload
        events = []

        class TrackedRow(Mapping):
            def __init__(self, values, *, poison_keys=()):
                self.values = values
                self.poison_keys = set(poison_keys)

            def __len__(self):
                return len(self.values)

            def __iter__(self):
                return iter(self.values)

            def __getitem__(self, key):
                return self.values[key]

            def get(self, key, default=None):
                events.append(key)
                if key in self.poison_keys:
                    raise RuntimeError(f"unexpected getter: {key}")
                return self.values.get(key, default)

        self.assertTrue(
            has_material(
                TrackedRow(
                    {
                        "status": "ok",
                        "raw_unit": "",
                        "unit": "count",
                        "normalized_unit": "COUNT",
                        "raw_value": "",
                        "value": "",
                        "rendered_value": "",
                        "display_value": "1234",
                        "normalized_value": None,
                    }
                )
            )
        )
        self.assertEqual(
            events,
            [
                "status",
                "raw_unit",
                "unit",
                "normalized_unit",
                "raw_value",
                "value",
                "rendered_value",
                "display_value",
                "normalized_value",
            ],
        )

        events.clear()
        self.assertFalse(has_material(TrackedRow({"status": "missing"})))
        self.assertEqual(events, ["status"])
        events.clear()
        self.assertFalse(
            has_material(TrackedRow({"normalized_unit": "UNKNOWN", "raw_value": "123"}))
        )
        self.assertNotIn("normalized_value", events)

        events.clear()
        self.assertTrue(
            has_material(
                TrackedRow(
                    {
                        "raw_unit": "count",
                        "normalized_unit": "COUNT",
                        "raw_value": "1234",
                    },
                    poison_keys={"unit", "value", "rendered_value", "display_value"},
                )
            )
        )
        self.assertEqual(events, ["status", "raw_unit", "normalized_unit", "raw_value", "normalized_value"])

        for name, values, poison_keys, expected_events in (
            (
                "raw value",
                {"normalized_unit": "COUNT", "raw_value": "1234"},
                {"value", "rendered_value", "display_value"},
                ["status", "raw_unit", "unit", "normalized_unit", "raw_value", "normalized_value"],
            ),
            (
                "value",
                {"normalized_unit": "COUNT", "raw_value": "", "value": "1234"},
                {"rendered_value", "display_value"},
                ["status", "raw_unit", "unit", "normalized_unit", "raw_value", "value", "normalized_value"],
            ),
            (
                "rendered value",
                {
                    "normalized_unit": "COUNT",
                    "raw_value": "",
                    "value": "",
                    "rendered_value": "1234",
                },
                {"display_value"},
                [
                    "status",
                    "raw_unit",
                    "unit",
                    "normalized_unit",
                    "raw_value",
                    "value",
                    "rendered_value",
                    "normalized_value",
                ],
            ),
        ):
            with self.subTest(lazy=name):
                events.clear()
                self.assertTrue(has_material(TrackedRow(values, poison_keys=poison_keys)))
                self.assertEqual(events, expected_events)

        class GetBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                return iter(("status",))

            def __getitem__(self, key):
                raise KeyError(key)

            def get(self, _key, _default=None):
                raise RuntimeError("mapping get failed")

        class StringBomb:
            def __str__(self):
                raise RuntimeError("string failed")

        class TruthBomb:
            def __bool__(self):
                raise RuntimeError("truthiness failed")

        with self.assertRaisesRegex(RuntimeError, "mapping get failed"):
            has_material(GetBomb())
        with self.assertRaisesRegex(RuntimeError, "string failed"):
            has_material({"status": StringBomb()})
        with self.assertRaisesRegex(RuntimeError, "truthiness failed"):
            has_material({"raw_unit": TruthBomb()})
        with patch.object(
            financial_runtime_trace,
            "_normalise_spaces",
            side_effect=RuntimeError("normalizer failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalizer failed"):
                has_material({})
        with patch.object(
            financial_runtime_trace.re,
            "findall",
            side_effect=RuntimeError("regex failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "regex failed"):
                has_material({"raw_value": "1234"})

    def test_append_aggregate_operand_uses_material_predicate_contract(self) -> None:
        nested = {"keep": True}
        operand = {
            "task_id": "task_a",
            "operand_id": "operand_a",
            "raw_value": "100",
            "raw_unit": "count",
            "source_row_id": "stale",
            "nested": nested,
        }
        before = deepcopy(operand)
        expected = {
            **operand,
            "source_row_id": "ev_a",
            "source_row_ids": ["ev_a", "ev_b"],
        }

        aggregate_operands = []
        seen = set()
        with (
            patch.object(
                financial_runtime_trace,
                "operand_row_has_material_numeric_payload",
                return_value=False,
            ) as predicate,
            patch.object(financial_runtime_trace, "_aggregate_operand_key") as later_key,
        ):
            financial_runtime_trace._append_aggregate_operand(
                aggregate_operands,
                seen,
                operand,
                source_ids=[" ev_a ", "ev_b", "ev_a"],
            )
        predicate.assert_called_once()
        copied_row = predicate.call_args.args[0]
        self.assertEqual(copied_row, expected)
        self.assertIsNot(copied_row, operand)
        self.assertIs(copied_row["nested"], nested)
        self.assertEqual((aggregate_operands, seen), ([], set()))
        later_key.assert_not_called()

        aggregate_operands = []
        seen = set()
        real_key = financial_runtime_trace._aggregate_operand_key
        expected_key = real_key(expected, ["ev_a", "ev_b"])
        with (
            patch.object(
                financial_runtime_trace,
                "operand_row_has_material_numeric_payload",
                return_value=True,
            ) as predicate,
            patch.object(financial_runtime_trace, "_aggregate_operand_key", wraps=real_key) as key_builder,
        ):
            financial_runtime_trace._append_aggregate_operand(
                aggregate_operands,
                seen,
                operand,
                source_ids=[" ev_a ", "ev_b", "ev_a"],
            )
        predicate.assert_called_once()
        copied_row = predicate.call_args.args[0]
        self.assertEqual(aggregate_operands, [expected])
        self.assertIs(aggregate_operands[0], copied_row)
        key_builder.assert_called_once_with(copied_row, ["ev_a", "ev_b"])
        self.assertEqual(seen, {expected_key})

        aggregate_operands = []
        seen = set()
        with (
            patch.object(
                financial_runtime_trace,
                "operand_row_has_material_numeric_payload",
                side_effect=RuntimeError("material predicate failed"),
            ) as predicate,
            patch.object(financial_runtime_trace, "_aggregate_operand_key") as later_key,
        ):
            with self.assertRaisesRegex(RuntimeError, "material predicate failed"):
                financial_runtime_trace._append_aggregate_operand(
                    aggregate_operands,
                    seen,
                    operand,
                    source_ids=["ev_a", "ev_b"],
                )
        predicate.assert_called_once()
        self.assertEqual((aggregate_operands, seen), ([], set()))
        later_key.assert_not_called()
        self.assertEqual(operand, before)

    def test_evaluator_import_does_not_load_runtime_trace_owner(self) -> None:
        code = (
            "import sys\n"
            "import src.ops.evaluator\n"
            "print('src.agent.financial_runtime_trace' in sys.modules)\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertEqual(completed.stdout.strip(), "False")

    def test_contains_section_accepts_parent_section_path(self) -> None:
        metadata = {
            "section": "경영진단",
            "section_path": "IV. 이사의 경영진단 및 분석의견",
        }

        self.assertTrue(
            _contains_section(
                metadata,
                "IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적",
            )
        )

    def test_runtime_evidence_supports_hybrid_section_metrics(self) -> None:
        example = EvalExample(
            id="nav_t2_006",
            question="커머스 성장률과 포시마크 영향은?",
            ground_truth="41.4%와 포시마크 영향",
            company="네이버",
            year=2023,
            section="경영진단",
            expected_sections=[
                "IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적"
            ],
            company_aliases=["NAVER"],
        )
        runtime_evidence = [
            {
                "claim": "네이버 커머스는 전년 대비 41.4% 성장했습니다.",
                "quote_span": "Poshmark의 성공적인 체질 개선 등으로 전년 대비 41.4% 성장",
                "metadata": {
                    "company": "NAVER",
                    "year": 2023,
                    "section": "경영진단",
                    "section_path": "IV. 이사의 경영진단 및 분석의견",
                },
            }
        ]

        self.assertEqual(_compute_runtime_evidence_retrieval_hit_at_k(example, runtime_evidence), 1.0)
        self.assertEqual(_compute_runtime_evidence_section_match_rate(example, runtime_evidence), 1.0)
        contexts = _build_runtime_evidence_contexts(runtime_evidence)
        self.assertTrue(any("Poshmark" in context for context in contexts))

    def test_runtime_evidence_projects_statement_type_to_expected_section_surface(self) -> None:
        example = EvalExample(
            id="cash_flow_statement_surface",
            question="연결기준 잉여현금흐름을 계산해 줘.",
            ground_truth="영업활동현금흐름에서 유형자산 취득액을 차감",
            company="네이버",
            year=2023,
            section="재무제표",
            expected_sections=["III. 재무에 관한 사항 > 연결현금흐름표"],
            company_aliases=["NAVER"],
        )
        runtime_evidence = [
            {
                "claim": "영업활동현금흐름 | 제 25 기 2,002,233,273,518 원",
                "quote_span": "영업활동현금흐름 2,002,233,273,518",
                "metadata": {
                    "company": "NAVER",
                    "year": 2023,
                    "section": "재무제표",
                    "section_path": "III. 재무에 관한 사항 > 2. 연결재무제표",
                    "statement_type": "cash_flow",
                    "table_context": "III. 재무에 관한 사항 > 2. 연결재무제표",
                },
            }
        ]

        self.assertTrue(_contains_section(runtime_evidence[0]["metadata"], "연결현금흐름표"))
        self.assertEqual(_compute_runtime_evidence_retrieval_hit_at_k(example, runtime_evidence), 1.0)
        self.assertEqual(_compute_runtime_evidence_section_match_rate(example, runtime_evidence), 1.0)

    def test_runtime_evidence_uses_source_anchor_when_metadata_is_empty(self) -> None:
        example = EvalExample(
            id="anchor_section_surface",
            question="Extract the total and summarize the related business direction.",
            ground_truth="The total is grounded and the direction is supported.",
            company="ACME",
            year=2023,
            section="II. Business",
            expected_sections=["II. Business > 7. Other notes"],
            company_aliases=["ACME Corp"],
        )
        runtime_evidence = [
            {
                "claim": "The business direction is stated in the cited section.",
                "quote_span": "The cited section states the direction.",
                "source_anchor": "[ACME Corp | 2023 | II. Business > 7. Other notes]",
                "metadata": {},
            }
        ]

        self.assertEqual(_compute_runtime_evidence_retrieval_hit_at_k(example, runtime_evidence), 1.0)
        self.assertEqual(_compute_runtime_evidence_section_match_rate(example, runtime_evidence), 1.0)

    def test_runtime_evidence_metadata_supports_citation_coverage(self) -> None:
        example = EvalExample(
            id="cash_flow_citation_surface",
            question="연결기준 잉여현금흐름을 계산해 줘.",
            ground_truth="영업활동현금흐름에서 유형자산 취득액을 차감",
            company="네이버",
            year=2023,
            section="재무제표",
            expected_sections=["III. 재무에 관한 사항 > 연결현금흐름표"],
            company_aliases=["NAVER"],
        )
        runtime_evidence = [
            {
                "claim": "영업활동현금흐름 | 제 25 기 2,002,233,273,518 원",
                "quote_span": "영업활동현금흐름 2,002,233,273,518",
                "source_anchor": "[NAVER | 2023 | III. 재무에 관한 사항 > 2. 연결재무제표]",
                "metadata": {
                    "company": "NAVER",
                    "year": 2023,
                    "section_path": "III. 재무에 관한 사항 > 2. 연결재무제표",
                    "statement_type": "cash_flow",
                },
            }
        ]

        self.assertEqual(_compute_runtime_evidence_citation_coverage(example, runtime_evidence), 1.0)

    def test_entity_coverage_accepts_korean_amount_surface_variants(self) -> None:
        example = EvalExample(
            id="cash_flow_entity_surface",
            question="연결기준 잉여현금흐름을 계산해 줘.",
            ground_truth="영업활동현금흐름에서 유형자산 취득액을 차감",
            company="네이버",
            year=2023,
            section="재무제표",
            required_entities=["2023년", "영업활동현금흐름", "유형자산 취득액"],
        )
        contexts = [
            "NAVER\n2023\nIII. 재무에 관한 사항 > 연결현금흐름표\n"
            "영업활동현금흐름 2,002,233,273,518\n"
            "유형자산의 취득 (640,623,697,250)"
        ]

        self.assertEqual(_compute_entity_coverage(example, contexts), 1.0)

    def test_section_match_accepts_canonical_quote_when_section_label_differs(self) -> None:
        example = EvalExample(
            id="quote_section_surface",
            question="Calculate US sales growth and summarize the policy context.",
            ground_truth="US sales increased 11.5% to 870 thousand units.",
            company="Example Motors",
            year=2023,
            section="Overseas market",
            expected_sections=["II. Business > Overseas market"],
            evidence=[
                EvalEvidence(
                    section_path="II. Business > Overseas market",
                    quote="2023 US market sales increased 11.5% to 870 thousand units",
                )
            ],
        )
        runtime_evidence = [
            {
                "claim": "2023 US market sales increased 11.5% to 870 thousand units.",
                "quote_span": "2023 US market sales increased 11.5% to 870 thousand units.",
                "metadata": {
                    "company": "Example Motors",
                    "year": 2023,
                    "section_path": "II. Business > 7. Other notes",
                    "parent_category": "US market",
                },
            },
            {
                "claim": "A separate policy context sentence.",
                "quote_span": "A separate policy context sentence.",
                "metadata": {
                    "company": "Example Motors",
                    "year": 2023,
                    "section_path": "IV. Risk factors",
                },
            },
        ]

        self.assertEqual(_compute_runtime_evidence_section_match_rate(example, runtime_evidence), 0.5)

    def test_ndcg_is_capped_when_multiple_docs_match_single_expected_section(self) -> None:
        example = EvalExample(
            id="cash_flow_ndcg",
            question="연결기준 잉여현금흐름을 계산해 줘.",
            ground_truth="영업활동현금흐름에서 유형자산 취득액을 차감",
            company="네이버",
            year=2023,
            section="재무제표",
            expected_sections=["III. 재무에 관한 사항 > 연결현금흐름표"],
            company_aliases=["NAVER"],
        )
        metadata = {
            "company": "NAVER",
            "year": 2023,
            "section_path": "III. 재무에 관한 사항 > 2. 연결재무제표",
            "statement_type": "cash_flow",
        }

        score = _compute_ndcg_at_k(example, [_DummyDoc(metadata), _DummyDoc(metadata)], k=2)

        self.assertEqual(score, 1.0)

    def test_numeric_judge_evidence_includes_structured_table_cell_values(self) -> None:
        metadata = {
            "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
            "table_row_records_json": json.dumps(
                [
                    {
                        "row_label": "기타영업손익",
                        "row_headers": ["기타영업손익"],
                        "cells": [
                            {
                                "column_headers": ["2023"],
                                "value_text": "676,874",
                                "unit_hint": "백만원",
                            }
                        ],
                    }
                ],
                ensure_ascii=False,
            ),
        }
        runtime_evidence = [
            {
                "source_anchor": "LG에너지솔루션 | 2023 | 연결재무제표 주석",
                "quote_span": "IRA Tax Credit: 6,769 (억원)",
                "metadata": metadata,
            }
        ]

        judge_evidence = _format_runtime_evidence_for_numeric_judge(runtime_evidence)
        corpus = _build_operand_grounding_corpus(runtime_evidence, [])

        self.assertIn("structured_values=", judge_evidence)
        self.assertIn("676,874백만원", judge_evidence)
        self.assertTrue(
            any(
                row.get("source") == "runtime_evidence_structured_table"
                and "676,874백만원" in str(row.get("text"))
                for row in corpus
            )
        )

    def test_grounded_rendering_ignores_narrative_and_validates_numeric_surfaces(self) -> None:
        calculation_result = {
            "status": "ok",
            "rendered_value": "41.4%",
            "formatted_result": "Narrative text that is outside numeric rendering scope.",
            "answer_slots": {
                "primary_value": {"rendered_value": "41.4%"},
            },
        }

        score, reason = _compute_grounded_rendering_correctness(
            answer=(
                "Current revenue was 2,546,649백만원 versus 1,801,079백만원, "
                "so it grew 41.4%. The acquisition integration improved the business."
            ),
            calculation_operands=[
                {"label": "current revenue", "raw_value": "2,546,649", "raw_unit": "백만원"},
                {"label": "prior revenue", "raw_value": "1,801,079", "raw_unit": "백만원"},
            ],
            calculation_result=calculation_result,
        )

        self.assertEqual(score, 1.0)
        self.assertIn("deterministic", reason)

    def test_grounded_rendering_rejects_unsupported_numeric_surface(self) -> None:
        score, reason = _compute_grounded_rendering_correctness(
            answer="Revenue grew 41.4%, while an unsupported claim says 99.9%.",
            calculation_operands=[
                {"label": "current revenue", "raw_value": "2,546,649", "raw_unit": "백만원"},
                {"label": "prior revenue", "raw_value": "1,801,079", "raw_unit": "백만원"},
            ],
            calculation_result={"status": "ok", "rendered_value": "41.4%"},
        )

        self.assertEqual(score, 0.0)
        self.assertIn("99.9%", reason)

    def test_grounded_rendering_accepts_additional_evidence_backed_numeric_narrative(self) -> None:
        score, reason = _compute_grounded_rendering_correctness(
            answer="Revenue grew 41.4%; a separate integration cost changed 24.3%.",
            calculation_operands=[
                {"label": "current revenue", "raw_value": "2,546,649", "raw_unit": "백만원"},
                {"label": "prior revenue", "raw_value": "1,801,079", "raw_unit": "백만원"},
            ],
            calculation_result={"status": "ok", "rendered_value": "41.4%"},
            runtime_evidence=[{"quote_span": "The separate integration cost changed 24.3%."}],
        )

        self.assertEqual(score, 1.0)
        self.assertIn("evidence", reason)

    def test_calculation_correctness_uses_numeric_checks_only(self) -> None:
        self.assertEqual(
            _compute_calculation_correctness(
                numeric_result_correctness=1.0,
                grounded_rendering_correctness=1.0,
            ),
            1.0,
        )
        self.assertEqual(
            _compute_calculation_correctness(
                numeric_result_correctness=None,
                grounded_rendering_correctness=1.0,
            ),
            1.0,
        )

    def test_should_override_numeric_grounding_for_direct_composed_ratio(self) -> None:
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
        }
        calculation_operands = [
            {
                "label": "매출원가",
                "source_row_id": "row_cost",
                "source_anchor": "연결 손익계산서",
            },
            {
                "label": "판매비와관리비",
                "source_row_id": "row_sga",
                "source_anchor": "연결 손익계산서",
            },
            {
                "label": "매출액",
                "source_row_id": "row_revenue",
                "source_anchor": "연결 손익계산서",
            },
        ]

        self.assertTrue(
            _should_override_numeric_grounding(
                numeric_eval=numeric_eval,
                calculation_operands=calculation_operands,
                operand_selection_correctness=1.0,
                numeric_result_correctness=1.0,
                grounded_rendering_correctness=1.0,
            )
        )

    def test_should_not_override_numeric_grounding_when_deterministic_rendering_fails(self) -> None:
        calculation_operands = [
            {
                "operand_id": "op_current_assets",
                "label": "current assets",
                "raw_value": "195,936,557",
                "raw_unit": "백만원",
                "source_row_id": "row_assets",
                "source_anchor": "structured balance sheet",
            },
            {
                "operand_id": "op_current_liabilities",
                "label": "current liabilities",
                "raw_value": "75,719,452",
                "raw_unit": "백만원",
                "source_row_id": "row_liabilities",
                "source_anchor": "structured balance sheet",
            },
        ]
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
            "numeric_debug": {
                "operand_grounding": {
                    "matched_operands": [
                        {"operand_id": "op_current_assets"},
                        {"operand_id": "op_current_liabilities"},
                    ],
                    "unmatched_operands": [],
                }
            },
        }

        self.assertFalse(
            _should_override_numeric_grounding(
                numeric_eval=numeric_eval,
                calculation_operands=calculation_operands,
                operand_selection_correctness=1.0,
                numeric_result_correctness=None,
                grounded_rendering_correctness=0.0,
            )
        )

    def test_should_not_override_numeric_grounding_when_rendering_fails_without_operand_grounding(self) -> None:
        calculation_operands = [
            {
                "operand_id": "op_current_assets",
                "label": "current assets",
                "source_row_id": "row_assets",
                "source_anchor": "structured balance sheet",
            },
            {
                "operand_id": "op_current_liabilities",
                "label": "current liabilities",
                "source_row_id": "row_liabilities",
                "source_anchor": "structured balance sheet",
            },
        ]
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
            "numeric_debug": {
                "operand_grounding": {
                    "matched_operands": [{"operand_id": "op_current_assets"}],
                    "unmatched_operands": [{"operand_id": "op_current_liabilities"}],
                }
            },
        }

        self.assertFalse(
            _should_override_numeric_grounding(
                numeric_eval=numeric_eval,
                calculation_operands=calculation_operands,
                operand_selection_correctness=1.0,
                numeric_result_correctness=None,
                grounded_rendering_correctness=0.0,
            )
        )

    def test_should_override_numeric_grounding_for_runtime_evidence_difference_and_growth(self) -> None:
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
        }
        runtime_evidence = [
            {
                "quote_span": "검증항목 (3,146,409) (1,847,775)",
                "metadata": {"unit_hint": "백만원"},
            }
        ]

        self.assertTrue(
            _should_override_numeric_grounding_from_runtime_evidence(
                answer="검증항목은 3,146십억원으로 전년 1,848십억원 대비 1,298십억원, 약 70.23% 증가했습니다.",
                numeric_eval=numeric_eval,
                runtime_evidence=runtime_evidence,
            )
        )

    def test_should_override_numeric_grounding_for_runtime_evidence_ratio(self) -> None:
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
        }
        runtime_evidence = [
            {"quote_span": "분자 3,531,423", "metadata": {"unit_hint": "백만원"}},
            {"quote_span": "분모 1,001,290", "metadata": {"unit_hint": "백만원"}},
        ]

        self.assertTrue(
            _should_override_numeric_grounding_from_runtime_evidence(
                answer="산출 비율은 3.5269배입니다.",
                numeric_eval=numeric_eval,
                runtime_evidence=runtime_evidence,
            )
        )

    def test_supplement_operands_rejects_short_unknown_unit_values(self) -> None:
        example = EvalExample(
            id="short_unknown",
            question="Find the metric.",
            ground_truth="The metric is not the relation-table short value.",
            company="ACME",
            year=2023,
            section="Notes",
            expected_operands=[
                {
                    "label": "target metric",
                    "period": "2022",
                    "raw_value": "9",
                    "raw_unit": "",
                }
            ],
        )
        runtime_evidence = [
            {
                "evidence_id": "ev_short",
                "claim": "target metric | current 9 | prior 1",
            }
        ]

        supplemented = _supplement_resolved_operands_from_runtime_evidence(
            example=example,
            runtime_evidence=runtime_evidence,
            calculation_operands=[],
        )

        self.assertEqual(supplemented, [])

    def test_should_not_override_numeric_grounding_for_task_output_only_operands(self) -> None:
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
        }
        calculation_operands = [
            {
                "label": "매출원가",
                "source_row_id": "task_output:task_2",
                "source_anchor": "연결 손익계산서",
            }
        ]

        self.assertFalse(
            _should_override_numeric_grounding(
                numeric_eval=numeric_eval,
                calculation_operands=calculation_operands,
                operand_selection_correctness=1.0,
                numeric_result_correctness=1.0,
                grounded_rendering_correctness=1.0,
            )
        )

    def test_should_override_numeric_grounding_for_resolved_task_output_dependency(self) -> None:
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
        }
        calculation_operands = [
            {
                "label": "종업원급여",
                "source_row_id": "task_output:task_2",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
                "dependency_resolved": True,
                "source_task_id": "task_2",
                "source_slot": "primary_value",
            },
            {
                "label": "연결기준 영업비용",
                "source_row_id": "ev_doc_005",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 2. 연결재무제표]",
            },
        ]

        self.assertTrue(
            _should_override_numeric_grounding(
                numeric_eval=numeric_eval,
                calculation_operands=calculation_operands,
                operand_selection_correctness=1.0,
                numeric_result_correctness=1.0,
                grounded_rendering_correctness=1.0,
            )
        )

    def test_should_override_numeric_grounding_for_resolved_task_output_without_anchor(self) -> None:
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
        }
        calculation_operands = [
            {
                "label": "영업이익",
                "source_row_id": "task_output:task_1",
                "source_anchor": "",
                "dependency_resolved": True,
                "source_task_id": "task_1",
                "source_slot": "primary_value",
            },
            {
                "label": "첨단제조 생산세액공제 (AMPC)",
                "source_row_id": "ev_001",
                "source_anchor": "[LG에너지솔루션 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
            },
        ]

        self.assertTrue(
            _should_override_numeric_grounding(
                numeric_eval=numeric_eval,
                calculation_operands=calculation_operands,
                operand_selection_correctness=1.0,
                numeric_result_correctness=None,
                grounded_rendering_correctness=1.0,
            )
        )

    def test_resolve_evaluator_operands_preserves_resolved_task_output_metadata(self) -> None:
        calculation_operands = [
            {
                "operand_id": "dep_task_1_001",
                "evidence_id": "task_output:task_1",
                "source_anchor": "",
                "label": "영업이익",
                "raw_value": "2,163,234",
                "raw_unit": "백만원",
                "normalized_value": 2163234000000,
                "normalized_unit": "KRW",
                "period": "2023",
                "dependency_resolved": True,
                "source_task_id": "task_1",
                "source_slot": "primary_value",
            },
            {
                "operand_id": "op_002",
                "evidence_id": "ev_001",
                "source_anchor": "[LG에너지솔루션 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
                "label": "2023년 첨단제조 생산세액공제 (AMPC)",
                "raw_value": "676,874",
                "raw_unit": "백만원",
                "normalized_value": 676874000000,
                "normalized_unit": "KRW",
                "period": "2023년",
            },
        ]
        calculation_result = {
            "answer_slots": {
                "operation_family": "difference",
                "components_by_role": {
                    "minuend": [
                        {
                            "role": "minuend",
                            "label": "영업이익",
                            "period": "2023",
                            "raw_value": "2,163,234",
                            "raw_unit": "백만원",
                            "normalized_value": 2163234000000,
                            "normalized_unit": "KRW",
                            "source_row_id": "task_output:task_1",
                            "source_row_ids": ["task_output:task_1"],
                            "source_anchor": "",
                        }
                    ],
                    "operand": [
                        {
                            "role": "operand",
                            "label": "첨단제조 생산세액공제 (AMPC)",
                            "period": "2023년",
                            "raw_value": "676,874",
                            "raw_unit": "백만원",
                            "normalized_value": 676874000000,
                            "normalized_unit": "KRW",
                            "source_row_id": "ev_001",
                            "source_row_ids": ["ev_001"],
                            "source_anchor": "[LG에너지솔루션 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
                        }
                    ],
                },
            }
        }

        resolved = _resolve_evaluator_operands(calculation_operands, calculation_result)
        task_operand = next(row for row in resolved if row["source_row_id"] == "task_output:task_1")

        self.assertTrue(task_operand["dependency_resolved"])
        self.assertEqual(task_operand["source_task_id"], "task_1")
        self.assertEqual(task_operand["source_slot"], "primary_value")

        self.assertTrue(
            _should_override_numeric_grounding(
                numeric_eval={
                    "numeric_equivalence": 1.0,
                    "numeric_grounding": 0.0,
                    "numeric_retrieval_support": 1.0,
                },
                calculation_operands=resolved,
                operand_selection_correctness=1.0,
                numeric_result_correctness=None,
                grounded_rendering_correctness=1.0,
            )
        )

    def test_should_override_numeric_grounding_for_evidence_id_trace_sources(self) -> None:
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
        }
        calculation_operands = [
            {
                "label": "종업원급여",
                "evidence_id": "task_output:task_2",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
                "dependency_resolved": True,
                "source_task_id": "task_2",
                "source_slot": "primary_value",
            },
            {
                "label": "연결기준 영업비용",
                "evidence_id": "ev_doc_005",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 2. 연결재무제표]",
            },
        ]

        self.assertTrue(
            _should_override_numeric_grounding(
                numeric_eval=numeric_eval,
                calculation_operands=calculation_operands,
                operand_selection_correctness=1.0,
                numeric_result_correctness=1.0,
                grounded_rendering_correctness=1.0,
            )
        )

    def test_operand_match_tolerates_current_fiscal_period_alias_with_same_payload(self) -> None:
        expected = {
            "label": "영업비용 합계",
            "period": "2023년",
            "raw_value": "8,181,823,307",
            "raw_unit": "천원",
        }
        actual = {
            "label": "2023년 연결기준 영업비용",
            "period": "제 25 기",
            "raw_value": "8,181,823,306,977",
            "raw_unit": "원",
            "normalized_value": 8181823306977.0,
            "normalized_unit": "KRW",
        }

        self.assertTrue(_operand_matches(expected, actual))

    def test_operand_match_rejects_different_explicit_years(self) -> None:
        expected = {
            "label": "영업비용 합계",
            "period": "2023년",
            "raw_value": "8,181,823,307",
            "raw_unit": "천원",
        }
        actual = {
            "label": "2023년 연결기준 영업비용",
            "period": "2022년",
            "raw_value": "8,181,823,306,977",
            "raw_unit": "원",
            "normalized_value": 8181823306977.0,
            "normalized_unit": "KRW",
        }

        self.assertFalse(_operand_matches(expected, actual))

    def test_operand_match_rejects_prior_period_alias(self) -> None:
        expected = {
            "label": "영업비용 합계",
            "period": "2023년",
            "raw_value": "8,181,823,307",
            "raw_unit": "천원",
        }
        actual = {
            "label": "2023년 연결기준 영업비용",
            "period": "전기",
            "raw_value": "8,181,823,306,977",
            "raw_unit": "원",
            "normalized_value": 8181823306977.0,
            "normalized_unit": "KRW",
        }

        self.assertFalse(_operand_matches(expected, actual))

    def test_should_override_numeric_grounding_when_numeric_result_is_unavailable(self) -> None:
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
        }
        calculation_operands = [
            {
                "label": "매출액",
                "source_row_id": "row_revenue",
                "source_anchor": "연결 손익계산서",
            }
        ]

        self.assertTrue(
            _should_override_numeric_grounding(
                numeric_eval=numeric_eval,
                calculation_operands=calculation_operands,
                operand_selection_correctness=1.0,
                numeric_result_correctness=None,
                grounded_rendering_correctness=1.0,
            )
        )

    def test_should_override_numeric_grounding_when_grounded_rendering_is_unavailable(self) -> None:
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
        }
        calculation_operands = [
            {
                "label": "매출액",
                "source_row_id": "row_revenue",
                "source_anchor": "연결 손익계산서",
            }
        ]

        self.assertTrue(
            _should_override_numeric_grounding(
                numeric_eval=numeric_eval,
                calculation_operands=calculation_operands,
                operand_selection_correctness=1.0,
                numeric_result_correctness=None,
                grounded_rendering_correctness=None,
            )
        )

    def test_build_example_report_scope_preserves_multi_report_inventory(self) -> None:
        example = EvalExample(
            id="sam_t2_002",
            question="2023년 CAPEX 총액과 전년 대비 증감률은?",
            ground_truth="53조 1,139억원, 전년과 거의 동일",
            company="삼성전자",
            year=2023,
            section="시설투자",
            source_reports=[
                {
                    "corp_name": "삼성전자",
                    "year": 2023,
                    "report_type": "사업보고서",
                    "rcept_no": "20240312000736",
                },
                {
                    "corp_name": "삼성전자",
                    "year": 2022,
                    "report_type": "사업보고서",
                    "rcept_no": "20230308000592",
                },
            ],
        )

        scope = _build_example_report_scope(example)

        self.assertEqual(scope["company"], "삼성전자")
        self.assertEqual(scope["year"], 2023)
        self.assertEqual(scope["report_type"], "사업보고서")
        self.assertNotIn("rcept_no", scope)
        self.assertEqual(len(scope["source_reports"]), 2)

    def test_build_example_report_scope_keeps_single_receipt_scope(self) -> None:
        example = EvalExample(
            id="nav_t1_071",
            question="2023년 법인세비용차감전순이익과 전년 대비 증감액은?",
            ground_truth="1조 4,814억원, 3,977억원 증가",
            company="네이버",
            year=2023,
            section="손익계산서",
            source_report={
                "corp_name": "네이버",
                "year": 2023,
                "report_type": "사업보고서",
                "rcept_no": "20240314002112",
            },
        )

        scope = _build_example_report_scope(example)

        self.assertEqual(scope["company"], "네이버")
        self.assertEqual(scope["year"], 2023)
        self.assertEqual(scope["report_type"], "사업보고서")
        self.assertEqual(scope["rcept_no"], "20240314002112")

    def test_resolve_runtime_trace_prefers_aggregate_subtasks(self) -> None:
        result = {
            "answer": "부채비율은 25.4%입니다. 유동비율은 258.8%입니다.",
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "debt_ratio",
                    "metric_label": "부채비율",
                    "answer": "부채비율은 25.4%입니다.",
                    "status": "ok",
                    "calculation_operands": [
                        {"row_id": "debt", "label_kr": "부채총계", "value": "92228115"},
                        {"row_id": "equity", "label_kr": "자본총계", "value": "363677865"},
                    ],
                    "calculation_plan": {"status": "ok", "operation": "divide"},
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "25.4%",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "primary_value": {"rendered_value": "25.4%"},
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "current_ratio",
                    "metric_label": "유동비율",
                    "answer": "유동비율은 258.8%입니다.",
                    "status": "ok",
                    "calculation_operands": [
                        {"row_id": "current_assets", "label_kr": "유동자산", "value": "137621922"},
                        {"row_id": "current_liabilities", "label_kr": "유동부채", "value": "53186439"},
                    ],
                    "calculation_plan": {"status": "ok", "operation": "divide"},
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "258.8%",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "primary_value": {"rendered_value": "258.8%"},
                        },
                    },
                },
            ],
        }

        trace = _resolve_runtime_calculation_trace(
            result,
            allow_legacy_top_level=True,
        )

        self.assertEqual(len(trace["calculation_operands"]), 4)
        self.assertEqual(trace["calculation_plan"]["mode"], "aggregate_subtasks")
        self.assertEqual(trace["calculation_result"]["formatted_result"], result["answer"])
        self.assertEqual(
            trace["calculation_result"]["derived_metrics"]["subtask_ids"],
            ["task_1", "task_2"],
        )
        self.assertEqual(
            trace["calculation_result"]["answer_slots"]["operation_family"],
            "aggregate_subtasks",
        )
        self.assertEqual(trace["runtime_projection"]["source"], "aggregate_subtasks")
        self.assertFalse(trace["runtime_projection"]["legacy_fallback"])

    def test_resolve_runtime_trace_can_project_single_task_from_ledger(self) -> None:
        result = {
            "answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "active_subtask": {"task_id": "task_1"},
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "status": "completed",
                    "artifact_ids": ["artifact:001", "artifact:002", "artifact:003"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:001",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "debt", "label_kr": "부채총계", "value": "92228115"},
                            {"row_id": "equity", "label_kr": "자본총계", "value": "363677865"},
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:002",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "divide"}
                    },
                },
                {
                    "artifact_id": "artifact:003",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {"status": "ok", "rendered_value": "25.4%"}
                    },
                },
            ],
        }

        trace = _resolve_runtime_calculation_trace(result)

        self.assertEqual(len(trace["calculation_operands"]), 2)
        self.assertEqual(trace["calculation_plan"]["operation"], "divide")
        self.assertEqual(trace["calculation_result"]["rendered_value"], "25.4%")
        self.assertEqual(trace["runtime_projection"]["source"], "task_artifact_ledger")
        self.assertEqual(trace["runtime_projection"]["source_task_id"], "task_1")
        self.assertFalse(trace["runtime_projection"]["legacy_fallback"])

    def test_resolve_runtime_trace_prefers_explicit_structured_contract(self) -> None:
        result = {
            "calculation_operands": [{"label": "stale", "value": "999"}],
            "calculation_plan": {"status": "stale"},
            "calculation_result": {"status": "stale", "rendered_value": "999"},
            "resolved_calculation_trace": {
                "calculation_operands": [{"label": "fresh", "value": "123"}],
                "calculation_plan": {"status": "ok", "operation": "lookup"},
                "calculation_result": {"status": "ok", "rendered_value": "123"},
            },
            "structured_result": {"status": "ok", "rendered_value": "123"},
        }

        trace = _resolve_runtime_calculation_trace(
            result,
            allow_legacy_top_level=True,
        )

        self.assertEqual(trace["calculation_operands"], [{"label": "fresh", "value": "123"}])
        self.assertEqual(trace["calculation_plan"]["operation"], "lookup")
        self.assertEqual(trace["calculation_result"]["rendered_value"], "123")
        self.assertEqual(trace["runtime_projection"]["source"], "resolved_calculation_trace")
        self.assertFalse(trace["runtime_projection"]["legacy_fallback"])

    def test_resolve_runtime_trace_marks_top_level_calculation_fields_as_legacy_fallback(self) -> None:
        result = {
            "calculation_operands": [{"label": "legacy", "value": "999"}],
            "calculation_plan": {"status": "legacy"},
            "calculation_result": {"status": "ok", "rendered_value": "999"},
            "resolved_calculation_trace": {},
            "structured_result": {},
        }

        trace = _resolve_runtime_calculation_trace(
            result,
            allow_legacy_top_level=True,
        )

        self.assertEqual(trace["calculation_operands"], [{"label": "legacy", "value": "999"}])
        self.assertEqual(trace["calculation_result"]["rendered_value"], "999")
        self.assertEqual(trace["runtime_projection"]["source"], "legacy_top_level")
        self.assertTrue(trace["runtime_projection"]["legacy_fallback"])

    def test_resolve_runtime_trace_strict_mode_rejects_legacy_top_level_fallback(self) -> None:
        result = {
            "calculation_operands": [{"label": "legacy", "value": "999"}],
            "calculation_plan": {"status": "legacy"},
            "calculation_result": {"status": "ok", "rendered_value": "999"},
            "resolved_calculation_trace": {},
            "structured_result": {},
        }

        trace = _resolve_runtime_calculation_trace(
            result,
            allow_legacy_top_level=False,
        )

        self.assertEqual(trace, {})

    def test_resolve_runtime_trace_marks_structured_result_only_as_non_legacy(self) -> None:
        result = {
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "resolved_calculation_trace": {},
            "structured_result": {"status": "ok", "rendered_value": "123"},
        }

        trace = _resolve_runtime_calculation_trace(result)

        self.assertEqual(trace["calculation_operands"], [])
        self.assertEqual(trace["calculation_plan"], {})
        self.assertEqual(trace["calculation_result"]["rendered_value"], "123")
        self.assertEqual(trace["runtime_projection"]["source"], "structured_result")
        self.assertFalse(trace["runtime_projection"]["legacy_fallback"])

    def test_resolve_runtime_trace_prefers_structured_result_over_stale_legacy_result(self) -> None:
        result = {
            "calculation_operands": [{"label": "legacy", "value": "123"}],
            "calculation_plan": {"status": "legacy", "operation": "lookup"},
            "calculation_result": {"status": "stale", "rendered_value": "999"},
            "resolved_calculation_trace": {},
            "structured_result": {"status": "ok", "rendered_value": "123"},
        }

        trace = _resolve_runtime_calculation_trace(
            result,
            allow_legacy_top_level=True,
        )

        self.assertEqual(trace["calculation_operands"], [{"label": "legacy", "value": "123"}])
        self.assertEqual(trace["calculation_plan"]["operation"], "lookup")
        self.assertEqual(trace["calculation_result"]["rendered_value"], "123")
        self.assertEqual(trace["runtime_projection"]["source"], "legacy_top_level")
        self.assertTrue(trace["runtime_projection"]["legacy_fallback"])
        self.assertEqual(
            trace["runtime_projection"]["calculation_result_source"],
            "structured_result",
        )
        self.assertEqual(
            trace["runtime_projection"]["superseded_calculation_result_source"],
            "legacy_top_level",
        )

    def test_resolve_runtime_trace_strict_mode_keeps_structured_result_without_legacy_inputs(self) -> None:
        result = {
            "calculation_operands": [{"label": "legacy", "value": "123"}],
            "calculation_plan": {"status": "legacy", "operation": "lookup"},
            "calculation_result": {"status": "stale", "rendered_value": "999"},
            "resolved_calculation_trace": {},
            "structured_result": {"status": "ok", "rendered_value": "123"},
        }

        trace = _resolve_runtime_calculation_trace(
            result,
            allow_legacy_top_level=False,
        )

        self.assertEqual(trace["calculation_operands"], [])
        self.assertEqual(trace["calculation_plan"], {})
        self.assertEqual(trace["calculation_result"]["rendered_value"], "123")
        self.assertEqual(trace["runtime_projection"]["source"], "structured_result")
        self.assertFalse(trace["runtime_projection"]["legacy_fallback"])
        self.assertNotIn("calculation_result_source", trace["runtime_projection"])

    def test_runtime_trace_state_update_omits_compatibility_mirrors_by_default(self) -> None:
        update = runtime_trace_state_update(
            {
                "resolved_calculation_trace": {},
                "structured_result": {},
                "calculation_operands": [{"row_id": "stale"}],
                "calculation_plan": {"status": "stale"},
                "calculation_result": {"status": "stale"},
            },
            calculation_operands=[{"row_id": "fresh"}],
            calculation_plan={"operation": "lookup"},
            calculation_result={"status": "ok", "rendered_value": "123"},
        )

        self.assertEqual(
            update["resolved_calculation_trace"]["calculation_operands"],
            [{"row_id": "fresh"}],
        )
        self.assertEqual(update["structured_result"]["rendered_value"], "123")
        self.assertNotIn("calculation_operands", update)
        self.assertNotIn("calculation_plan", update)
        self.assertNotIn("calculation_result", update)

    def test_evaluate_one_rejects_legacy_top_level_runtime_projection(self) -> None:
        evaluator = RAGEvaluator(
            _FakeAgent(
                {
                    "answer": "answer",
                    "query_type": "qa",
                    "intent": "qa",
                    "calculation_operands": [{"label": "legacy", "value": "999"}],
                    "calculation_plan": {"status": "legacy", "operation": "lookup"},
                    "calculation_result": {"status": "ok", "rendered_value": "999"},
                    "resolved_calculation_trace": {},
                    "structured_result": {},
                }
            ),
            skip_llm_judges=True,
        )
        example = EvalExample(
            id="Q1",
            question="question",
            ground_truth="answer",
            company="TEST",
            year=2023,
            section="section",
        )

        result = evaluator.evaluate_one(example)

        self.assertEqual(result.resolved_calculation_trace, {})
        self.assertEqual(result.calculation_operands, [])
        self.assertEqual(result.calculation_plan, {})
        self.assertEqual(result.calculation_result, {})
        self.assertEqual(result.structured_result, {})
        self.assertEqual(result.runtime_projection_source, "")
        self.assertFalse(result.runtime_projection_legacy_fallback)

    def test_evaluate_one_preserves_agent_failure_without_runtime_projection(self) -> None:
        evaluator = RAGEvaluator(
            _FailingAgent(),
            skip_llm_judges=True,
        )
        example = EvalExample(
            id="Q1",
            question="question",
            ground_truth="answer",
            company="TEST",
            year=2023,
            section="section",
        )

        result = evaluator.evaluate_one(example)

        self.assertEqual(result.error, "model unavailable")
        self.assertEqual(result.runtime_projection_source, "")
        self.assertFalse(result.runtime_projection_legacy_fallback)
        self.assertEqual(result.resolved_calculation_trace, {})

    def test_evaluate_one_uses_canonical_runtime_projection_metadata(self) -> None:
        evaluator = RAGEvaluator(
            _FakeAgent(
                {
                    "answer": "answer",
                    "query_type": "qa",
                    "intent": "qa",
                    "calculation_operands": [{"label": "legacy", "value": "999"}],
                    "calculation_plan": {"status": "legacy", "operation": "lookup"},
                    "calculation_result": {"status": "stale", "rendered_value": "999"},
                    "resolved_calculation_trace": {
                        "calculation_operands": [{"label": "fresh", "value": "123"}],
                        "calculation_plan": {"status": "ok", "operation": "lookup"},
                        "calculation_result": {"status": "ok", "rendered_value": "123"},
                    },
                }
            ),
            skip_llm_judges=True,
        )
        example = EvalExample(
            id="Q1",
            question="question",
            ground_truth="answer",
            company="TEST",
            year=2023,
            section="section",
        )

        result = evaluator.evaluate_one(example)

        self.assertEqual(result.calculation_operands, [{"label": "fresh", "value": "123"}])
        self.assertEqual(result.calculation_plan["operation"], "lookup")
        self.assertEqual(result.calculation_result["rendered_value"], "123")
        self.assertEqual(result.structured_result["rendered_value"], "123")
        self.assertEqual(result.runtime_projection_source, "resolved_calculation_trace")
        self.assertFalse(result.runtime_projection_legacy_fallback)
        self.assertNotIn(
            "999",
            json.dumps(result.resolved_calculation_trace, ensure_ascii=False),
        )

    def test_resolve_runtime_trace_prefers_explicit_non_aggregate_over_active_subtask(self) -> None:
        result = {
            "answer": "Motional summary",
            "active_subtask": {"task_id": "task_1"},
            "resolved_calculation_trace": {
                "calculation_operands": [{"operand_id": "ownership_ratio"}],
                "calculation_plan": {
                    "status": "ok",
                    "operation": "lookup",
                    "operation_family": "lookup",
                },
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "Motional summary",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "ownership_ratio",
                            "rendered_value": "25.81%",
                        },
                    },
                },
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "status": "partial",
                    "calculation_operands": [],
                    "calculation_plan": {"mode": "aggregate_subtasks"},
                    "calculation_result": {
                        "status": "partial",
                        "answer_slots": {"operation_family": "aggregate_subtasks"},
                    },
                }
            ],
        }

        trace = _resolve_runtime_calculation_trace(result)

        self.assertEqual(trace["calculation_plan"]["operation"], "lookup")
        self.assertEqual(trace["calculation_operands"], [{"operand_id": "ownership_ratio"}])
        self.assertEqual(
            trace["calculation_result"]["answer_slots"]["operation_family"],
            "lookup",
        )

    def test_resolve_evaluator_operands_prefers_answer_slots_components(self) -> None:
        operands = [
            {"operand_id": "legacy", "label": "legacy", "raw_value": "999", "raw_unit": "%"},
        ]
        calculation_result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "difference",
                "components_by_role": {
                    "current_period": [
                        {
                            "status": "ok",
                            "role": "current_period",
                            "label": "2023 명목순이자마진(NIM)",
                            "concept": "net_interest_margin",
                            "period": "2023",
                            "raw_value": "1.83",
                            "raw_unit": "%",
                            "normalized_value": 1.83,
                            "normalized_unit": "PERCENT",
                            "rendered_value": "1.83%",
                            "source_row_id": "row_2023",
                            "source_row_ids": ["row_2023"],
                            "source_anchor": "표 A",
                        }
                    ],
                    "prior_period": [
                        {
                            "status": "ok",
                            "role": "prior_period",
                            "label": "2022 명목순이자마진(NIM)",
                            "concept": "net_interest_margin",
                            "period": "2022",
                            "raw_value": "1.73",
                            "raw_unit": "%",
                            "normalized_value": 1.73,
                            "normalized_unit": "PERCENT",
                            "rendered_value": "1.73%",
                            "source_row_id": "row_2022",
                            "source_row_ids": ["row_2022"],
                            "source_anchor": "표 A",
                        }
                    ],
                },
            },
        }

        resolved = _resolve_evaluator_operands(operands, calculation_result)

        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0]["source_row_id"], "row_2023")
        self.assertEqual(resolved[0]["normalized_value"], 1.83)
        self.assertEqual(resolved[1]["source_row_id"], "row_2022")
        self.assertEqual(resolved[1]["normalized_value"], 1.73)

    def test_resolve_evaluator_operands_preserves_slot_source_evidence_ids(self) -> None:
        calculation_result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "lookup",
                "primary_value": {
                    "status": "ok",
                    "role": "primary_value",
                    "label": "target metric",
                    "period": "2023",
                    "raw_value": "100",
                    "raw_unit": "",
                    "normalized_value": 100.0,
                    "normalized_unit": "COUNT",
                    "source_row_id": "task_output:task_1",
                    "source_row_ids": ["task_output:task_1"],
                    "source_evidence_ids": ["ev_direct"],
                },
            },
        }
        calculation_operands = [
            {
                "operand_id": "op_1",
                "evidence_id": "ev_direct",
                "label": "target metric",
                "raw_value": "100",
                "raw_unit": "",
                "normalized_value": 100.0,
                "normalized_unit": "COUNT",
                "source_anchor": "[Company | 2023 | section]",
            }
        ]

        resolved = _resolve_evaluator_operands(calculation_operands, calculation_result)

        self.assertEqual(resolved[0]["source_evidence_ids"], ["ev_direct"])
        self.assertEqual(resolved[0]["source_anchor"], "[Company | 2023 | section]")

    def test_count_scaled_units_match_expected_operands(self) -> None:
        self.assertEqual(_normalise_math_operand_value("87.0", "만대"), (870000.0, "COUNT"))
        self.assertEqual(_normalise_math_operand_value("87.0", "만 대"), (870000.0, "COUNT"))
        example = EvalExample(
            id="Q",
            question="",
            ground_truth="",
            company="테스트",
            year=2023,
            section="",
            expected_operands=[
                {"label": "2023년 미국 판매대수", "period": "2023", "raw_value": "87.0", "raw_unit": "만대"},
                {"label": "2022년 미국 판매대수", "period": "2022", "raw_value": "78.1", "raw_unit": "만대"},
            ],
        )
        operands = [
            {
                "operand_id": "current_period",
                "matched_operand_role": "current_period",
                "label": "2023년 미국 시장 판매대수",
                "period": "2023년",
                "raw_value": "87.0",
                "raw_unit": "만 대",
                "normalized_value": 870000.0,
                "normalized_unit": "COUNT",
            },
            {
                "operand_id": "prior_period",
                "matched_operand_role": "prior_period",
                "label": "2022년 미국 시장 판매대수",
                "period": "2022년",
                "raw_value": "78.1",
                "raw_unit": "만 대",
                "normalized_value": 781000.0,
                "normalized_unit": "COUNT",
            },
        ]
        plan = {"ordered_operand_ids": ["current_period", "prior_period"]}

        self.assertTrue(_operand_matches(example.expected_operands[0], operands[0]))
        self.assertEqual(_compute_operand_selection_correctness(example, operands), 1.0)
        self.assertEqual(_compute_unit_consistency_pass(operands, plan), 1.0)

    def test_unit_consistency_is_not_applicable_to_single_operand_lookup(self) -> None:
        operands = [
            {
                "operand_id": "lookup_value",
                "raw_value": "28,352,769",
                "raw_unit": "백만원",
                "normalized_value": 28_352_769_000_000.0,
                "normalized_unit": "KRW",
            }
        ]
        plan = {"ordered_operand_ids": ["lookup_value"]}

        self.assertIsNone(_compute_unit_consistency_pass(operands, plan))

    def test_resolve_evaluator_operands_flattens_aggregate_subtask_answer_slots(self) -> None:
        operands = [
            {"operand_id": "stale_current", "label": "2023 시설투자(CAPEX)", "raw_value": "531,139", "raw_unit": "억원"},
            {"operand_id": "stale_prior", "label": "2022 시설투자(CAPEX)", "raw_value": "531,153", "raw_unit": ""},
        ]
        calculation_result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "aggregate_subtasks",
                "subtask_results": [
                    {
                        "task_id": "task_1",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2023 시설투자(CAPEX)",
                                "concept": "capital_expenditure_total",
                                "period": "2023",
                                "raw_value": "531,139",
                                "raw_unit": "억원",
                                "normalized_value": 53113900000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "53조 1,139억원",
                                "source_row_id": "row_2023",
                                "source_row_ids": ["row_2023"],
                                "source_anchor": "표 A",
                            },
                        },
                    },
                    {
                        "task_id": "task_2",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "components_by_role": {
                                "current_period": [
                                    {
                                        "status": "ok",
                                        "role": "current_period",
                                        "label": "2023 시설투자(CAPEX)",
                                        "concept": "capital_expenditure_total",
                                        "period": "2023",
                                        "raw_value": "531,139",
                                        "raw_unit": "억원",
                                        "normalized_value": 53113900000000.0,
                                        "normalized_unit": "KRW",
                                        "rendered_value": "53조 1,139억원",
                                        "source_row_id": "row_2023",
                                        "source_row_ids": ["row_2023"],
                                        "source_anchor": "표 A",
                                    }
                                ],
                                "prior_period": [
                                    {
                                        "status": "ok",
                                        "role": "prior_period",
                                        "label": "2022 시설투자(CAPEX)",
                                        "concept": "capital_expenditure_total",
                                        "period": "2022",
                                        "raw_value": "531,153",
                                        "raw_unit": "억원",
                                        "normalized_value": 53115300000000.0,
                                        "normalized_unit": "KRW",
                                        "rendered_value": "53조 1,153억원",
                                        "source_row_id": "row_2022",
                                        "source_row_ids": ["row_2022"],
                                        "source_anchor": "표 A",
                                    }
                                ],
                            },
                        },
                    },
                ],
            },
        }

        resolved = _resolve_evaluator_operands(operands, calculation_result)

        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0]["source_row_id"], "row_2023")
        self.assertEqual(resolved[1]["source_row_id"], "row_2022")

    def test_collect_aggregate_subtask_provenance_keeps_evidence_ids_for_narrative_child(self) -> None:
        answer_slots = {
            "operation_family": "aggregate_subtasks",
            "subtask_results": [
                {
                    "task_id": "task_growth",
                    "operation_family": "growth_rate",
                    "source_row_ids": ["row_growth"],
                    "source_evidence_ids": [],
                },
                {
                    "task_id": "task_summary",
                    "operation_family": "narrative_summary",
                    "source_row_ids": [],
                    "source_evidence_ids": ["ev_summary", "None"],
                    "answer_slots": {
                        "operation_family": "aggregate_subtasks",
                        "subtask_results": [
                            {
                                "task_id": "task_summary",
                                "operation_family": "narrative_summary",
                                "source_row_ids": [],
                                "source_evidence_ids": ["ev_summary"],
                            }
                        ],
                    },
                },
            ],
        }

        provenance = _collect_aggregate_subtask_provenance(answer_slots)

        self.assertEqual(
            provenance,
            [
                {
                    "task_id": "task_growth",
                    "operation_family": "growth_rate",
                    "source_row_ids": ["row_growth"],
                    "source_evidence_ids": [],
                },
                {
                    "task_id": "task_summary",
                    "operation_family": "narrative_summary",
                    "source_row_ids": [],
                    "source_evidence_ids": ["ev_summary"],
                },
            ],
        )

    def test_resolve_evaluator_operands_dedupes_task_output_duplicates(self) -> None:
        calculation_result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "ratio",
                "components_by_role": {
                    "numerator_1": [
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "2023 매출원가",
                            "concept": "cost_of_sales",
                            "period": "2023",
                            "raw_value": "129,179,183",
                            "raw_unit": "백만원",
                            "normalized_value": 129179183000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "129조 1,792억원",
                            "source_row_id": "row_cost",
                            "source_row_ids": ["row_cost"],
                            "source_anchor": "연결 손익계산서",
                        },
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "매출원가",
                            "concept": "cost_of_sales",
                            "period": "2023",
                            "raw_value": "129,179,183",
                            "raw_unit": "백만원",
                            "normalized_value": 129179183000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "129조 1,792억원",
                            "source_row_id": "task_output:task_2",
                            "source_row_ids": ["task_output:task_2"],
                            "source_anchor": "연결 손익계산서",
                        },
                    ],
                },
            },
        }

        resolved = _resolve_evaluator_operands([], calculation_result)

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["source_row_id"], "row_cost")
        self.assertEqual(resolved[0]["normalized_unit"], "KRW")

    def test_resolve_evaluator_operands_dedupes_aggregate_subtask_duplicates(self) -> None:
        calculation_result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "aggregate_subtasks",
                "subtask_results": [
                    {
                        "task_id": "task_2",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "components_by_role": {
                                "numerator_1": [
                                    {
                                        "status": "ok",
                                        "role": "numerator_1",
                                        "label": "2023 매출원가",
                                        "concept": "cost_of_sales",
                                        "period": "2023",
                                        "raw_value": "129,179,183",
                                        "raw_unit": "백만원",
                                        "normalized_value": 129179183000000.0,
                                        "normalized_unit": "KRW",
                                        "source_row_id": "row_cost",
                                        "source_anchor": "연결 손익계산서",
                                    }
                                ],
                            },
                        },
                    },
                    {
                        "task_id": "task_1",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "components_by_role": {
                                "numerator_1": [
                                    {
                                        "status": "ok",
                                        "role": "numerator_1",
                                        "label": "매출원가",
                                        "concept": "cost_of_sales",
                                        "period": "2023",
                                        "raw_value": "129,179,183",
                                        "raw_unit": "백만원",
                                        "normalized_value": 129179183000000.0,
                                        "normalized_unit": "KRW",
                                        "source_row_id": "task_output:task_2",
                                        "source_anchor": "연결 손익계산서",
                                    }
                                ],
                            },
                        },
                    },
                ],
            },
        }

        resolved = _resolve_evaluator_operands([], calculation_result)

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["source_row_id"], "row_cost")

    def test_resolve_evaluator_operands_promotes_direct_source_across_role_mismatch(self) -> None:
        calculation_result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "aggregate_subtasks",
                "subtask_results": [
                    {
                        "task_id": "task_lookup_cost",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "매출원가",
                                "concept": "cost_of_sales",
                                "period": "2023",
                                "raw_value": "129,179,183",
                                "raw_unit": "백만원",
                                "normalized_value": 129179183000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "129조 1,792억원",
                                "source_row_id": "row_cost",
                                "source_row_ids": ["row_cost"],
                                "source_anchor": "연결 손익계산서",
                            },
                        },
                    },
                    {
                        "task_id": "task_ratio",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "components_by_role": {
                                "numerator_1": [
                                    {
                                        "status": "ok",
                                        "role": "numerator_1",
                                        "label": "매출원가",
                                        "concept": "cost_of_sales",
                                        "period": "2023",
                                        "raw_value": "129,179,183",
                                        "raw_unit": "백만원",
                                        "normalized_value": 129179183000000.0,
                                        "normalized_unit": "KRW",
                                        "rendered_value": "129조 1,792억원",
                                        "source_row_id": "task_output:task_lookup_cost",
                                        "source_row_ids": ["task_output:task_lookup_cost"],
                                        "source_anchor": "연결 손익계산서",
                                    }
                                ],
                            },
                        },
                    },
                ],
            },
        }

        resolved = _resolve_evaluator_operands([], calculation_result)

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["matched_operand_role"], "numerator_1")
        self.assertEqual(resolved[0]["source_row_id"], "row_cost")
        self.assertEqual(resolved[0]["source_anchor"], "연결 손익계산서")

    def test_supplement_resolved_operands_from_runtime_evidence_for_composed_ratio(self) -> None:
        example = EvalExample(
            id="MIX_T1_064",
            question="총 영업비용과 영업비용률은?",
            ground_truth="90.70%",
            company="현대자동차",
            year=2023,
            section="재무제표",
            expected_operands=[
                {"label": "매출액", "period": "2023", "raw_value": "162663579", "raw_unit": "백만원"},
                {"label": "매출원가", "period": "2023", "raw_value": "129179183", "raw_unit": "백만원"},
                {"label": "판매비와관리비", "period": "2023", "raw_value": "18357495", "raw_unit": "백만원"},
            ],
        )
        runtime_evidence = [
            {
                "evidence_id": "ev_001",
                "source_anchor": "현대자동차 | 2023 | 연결 손익계산서",
                "claim": "2023년 현대자동차의 매출원가는 129,179,183 백만원입니다.",
            },
            {
                "evidence_id": "ev_002",
                "source_anchor": "현대자동차 | 2023 | 연결 손익계산서",
                "claim": "2023년 현대자동차의 판매비와관리비는 18,357,495 백만원입니다.",
            },
        ]
        calculation_operands = [
            {
                "operand_id": "denominator_1",
                "matched_operand_role": "denominator_1",
                "label": "매출액",
                "period": "2023",
                "raw_value": "162,663,579",
                "raw_unit": "백만원",
                "normalized_value": 162663579000000.0,
                "normalized_unit": "KRW",
                "source_row_id": "row_revenue",
                "source_anchor": "현대자동차 | 2023 | 연결 손익계산서",
            }
        ]

        supplemented = _supplement_resolved_operands_from_runtime_evidence(
            example=example,
            runtime_evidence=runtime_evidence,
            calculation_operands=calculation_operands,
        )

        self.assertEqual(len(supplemented), 3)
        labels = {row["label"] for row in supplemented}
        self.assertEqual(labels, {"매출액", "매출원가", "판매비와관리비"})
        self.assertTrue(any(row["source_row_id"] == "ev_001" for row in supplemented))
        self.assertTrue(any(row["source_row_id"] == "ev_002" for row in supplemented))

    def test_numeric_result_correctness_can_use_answer_slots_primary_value(self) -> None:
        example = EvalExample(
            id="T",
            question="2023년 KB금융의 순이자마진은?",
            ground_truth="1.83%",
            company="KB금융",
            year=2023,
            section="II. 사업의 내용",
            category="numeric_fact",
            answer_key="1.83%",
            evidence=[],
            answer_type="numeric",
            expected_calculation_result={
                "normalized_value": 1.83,
                "normalized_unit": "PERCENT",
                "tolerance": 0.0,
            },
        )
        calculation_result = {
            "status": "ok",
            "result_value": None,
            "answer_slots": {
                "operation_family": "lookup",
                "primary_value": {
                    "status": "ok",
                    "role": "primary_value",
                    "label": "명목순이자마진(NIM)",
                    "concept": "net_interest_margin",
                    "period": "2023",
                    "raw_value": "1.83",
                    "raw_unit": "%",
                    "normalized_value": 1.83,
                    "normalized_unit": "PERCENT",
                    "rendered_value": "1.83%",
                    "source_row_id": "row_1",
                    "source_row_ids": ["row_1"],
                    "source_anchor": "표 A",
                },
            },
        }

        score = _compute_numeric_result_correctness(example, calculation_result)

        self.assertEqual(score, 1.0)

    def test_numeric_result_correctness_can_use_aggregate_subtask_primary_value(self) -> None:
        example = EvalExample(
            id="mix_t1_064",
            question="영업비용률은?",
            ground_truth="90.7%",
            company="현대자동차",
            year=2023,
            section="연결 손익계산서",
            category="numeric_fact",
            answer_key="90.7%",
            evidence=[],
            answer_type="numeric",
            expected_calculation_result={
                "normalized_value": 90.7004990957441,
                "normalized_unit": "PERCENT",
                "tolerance": 0.0,
            },
        )
        calculation_result = {
            "status": "ok",
            "result_value": None,
            "answer_slots": {
                "operation_family": "aggregate_subtasks",
                "subtask_results": [
                    {
                        "task_id": "task_1",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "영업비용률",
                                "normalized_value": 90.7004990957441,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "90.7%",
                            },
                        },
                    }
                ],
            },
        }

        score = _compute_numeric_result_correctness(example, calculation_result)

        self.assertEqual(score, 1.0)

    def test_percent_equivalence_allows_display_rounding_gap(self) -> None:
        left = {
            "kind": "percent",
            "value_text": "25.36",
            "unit_text": "%",
            "normalized_value": 25.36,
        }
        right = {
            "kind": "percent",
            "value_text": "25.4",
            "unit_text": "%",
            "normalized_value": 25.4,
        }

        self.assertTrue(_numeric_values_equivalent(left, right))

    def test_operand_match_accepts_parenthesized_negative_and_display_scale(self) -> None:
        expected = {
            "label": "영업활동으로 인한 현금흐름",
            "period": "2023",
            "raw_value": "2,002",
            "raw_unit": "십억원",
        }
        actual = {
            "label": "2023 영업활동현금흐름",
            "period": "2023",
            "raw_value": "2,002,233,273,518",
            "raw_unit": "원",
            "normalized_value": 2002233273518.0,
            "normalized_unit": "KRW",
        }
        negative_expected = {
            "label": "유형자산의 취득",
            "period": "2023",
            "raw_value": "(640,623,697,250)",
            "raw_unit": "원",
        }
        negative_actual = {
            "label": "2023 유형자산의 취득",
            "period": "2023",
            "raw_value": "(640,623,697,250)",
            "raw_unit": "원",
            "normalized_value": -640623697250.0,
            "normalized_unit": "KRW",
        }

        self.assertTrue(_operand_matches(expected, actual))
        self.assertTrue(_operand_matches(negative_expected, negative_actual))


if __name__ == "__main__":
    unittest.main()
