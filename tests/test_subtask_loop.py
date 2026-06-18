import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _AggregateSynthesisState
from src.agent.financial_graph_helpers import _project_task_artifact_trace, _resolve_runtime_calculation_trace
from src.agent.financial_graph_models import (
    AggregateSynthesisOutput,
    CalculationOperand,
    CalculationRenderOutput,
    EvidenceItem,
    OperandExtraction,
)
from src.config.report_scoped_cache import (
    CACHE_ENTRY_SOURCE_LOCAL_INDEX,
    REPORT_CACHE_ENTRY_VERSION,
    report_cache_key_id,
)
from src.config.retrieval_policy import CALCULATION_NARRATIVE_POLICY, CALCULATION_RENDER_POLICY


class _StubStructuredLLM:
    def __init__(self, response):
        self._response = response

    def __call__(self, _prompt_value):
        return self._response

    def invoke(self, _prompt_value):
        return self._response


class _StubLLM:
    def __init__(self, response):
        self._response = response

    def with_structured_output(self, _schema):
        return RunnableLambda(lambda _prompt_value: self._response)


class _CapturingLLM:
    def __init__(self, response):
        self._response = response
        self.prompt_text = ""

    def with_structured_output(self, _schema):
        def _invoke(prompt_value):
            self.prompt_text = prompt_value.to_string()
            return self._response

        return RunnableLambda(_invoke)


class _FailingStructuredLLM:
    def with_structured_output(self, _schema):
        return RunnableLambda(lambda _prompt_value: (_ for _ in ()).throw(RuntimeError("structured output disabled")))


class _RecordingVectorStore:
    def __init__(self):
        self.queries = []
        self.last_search_telemetry = {}

    def search(self, query, k=4, where_filter=None):
        self.queries.append({"query": query, "k": k, "where_filter": where_filter})
        return []


class SubtaskLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = FinancialAgent.__new__(FinancialAgent)
        self.agent.llm = _StubLLM(OperandExtraction(coverage="missing", operands=[]))
        self.agent._llm_for_phase = lambda _phase: self.agent.llm

    def _lookup_result_row(
        self,
        *,
        task_id: str,
        metric_label: str = "",
        label: str,
        concept: str = "",
        raw_value: str,
        raw_unit: str = "백만원",
        normalized_value: float,
        normalized_unit: str = "KRW",
        rendered_value: str = "",
        source_row_id: str = "",
        source_anchor: str = "",
        answer: str = "",
    ) -> dict:
        return {
            "task_id": task_id,
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "metric_label": metric_label,
            "answer": answer,
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "primary_value": {
                        "status": "ok",
                        "role": "primary_value",
                        "label": label,
                        "concept": concept,
                        "raw_value": raw_value,
                        "raw_unit": raw_unit,
                        "normalized_value": normalized_value,
                        "normalized_unit": normalized_unit,
                        "rendered_value": rendered_value,
                        "source_row_id": source_row_id,
                        "source_row_ids": [source_row_id] if source_row_id else [],
                        "source_anchor": source_anchor,
                    }
                },
            },
        }

    def _ratio_component(
        self,
        *,
        role: str,
        label: str,
        concept: str = "",
        raw_value: str,
        raw_unit: str = "백만원",
        normalized_value: float,
        normalized_unit: str = "KRW",
        source_row_id: str = "",
        source_anchor: str = "",
    ) -> dict:
        return {
            "role": role,
            "label": label,
            "concept": concept,
            "raw_value": raw_value,
            "raw_unit": raw_unit,
            "normalized_value": normalized_value,
            "normalized_unit": normalized_unit,
            "source_row_id": source_row_id,
            "source_row_ids": [source_row_id] if source_row_id else [],
            "source_anchor": source_anchor,
        }

    def _ratio_result_row(
        self,
        *,
        status: str,
        metric_label: str = "target value to base value share",
        components_by_group: Optional[dict] = None,
        components_by_role: Optional[dict] = None,
        answer: str = "",
    ) -> dict:
        answer_slots = {
            "operation_family": "ratio",
            "metric_label": metric_label,
        }
        if components_by_group is not None:
            answer_slots["components_by_group"] = components_by_group
        if components_by_role is not None:
            answer_slots["components_by_role"] = components_by_role
        return {
            "task_id": "task_ratio",
            "metric_family": "concept_ratio",
            "operation_family": "ratio",
            "status": status,
            "metric_label": metric_label,
            "answer": answer,
            "calculation_result": {
                "status": status,
                "answer_slots": answer_slots,
            },
        }

    def test_growth_explanatory_signal_ignores_numeric_direction_only_sentence(self) -> None:
        self.assertFalse(
            self.agent._sentence_has_growth_explanatory_signal(
                "2023 revenue increased 70.28% compared with 2022."
            )
        )
        self.assertTrue(
            self.agent._sentence_has_growth_explanatory_signal(
                "The reason was weaker demand and stricter risk management."
            )
        )

    def test_supported_growth_narrative_candidate_selects_uncovered_driver_sentence(self) -> None:
        growth_row = {
            "task_id": "task_growth",
            "metric_family": "concept_growth_rate",
            "metric_label": "metric growth",
            "operation_family": "growth_rate",
            "answer": "2023년 metric은 303백만원이며, 2022년 202백만원 대비 50% 증가했습니다.",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "operation_family": "growth_rate",
                "rendered_value": "50%",
                "formatted_result": "2023년 metric은 303백만원이며, 2022년 202백만원 대비 50% 증가했습니다.",
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {
                        "status": "ok",
                        "label": "metric growth",
                        "period": "2023",
                        "rendered_value": "50%",
                        "raw_value": "50",
                        "raw_unit": "%",
                        "normalized_value": 50.0,
                        "normalized_unit": "PERCENT",
                    },
                    "current_value": {
                        "status": "ok",
                        "label": "metric",
                        "period": "2023",
                        "rendered_value": "303백만원",
                        "raw_value": "303",
                        "raw_unit": "백만원",
                        "normalized_value": 303_000_000.0,
                        "normalized_unit": "KRW",
                    },
                    "prior_value": {
                        "status": "ok",
                        "label": "metric",
                        "period": "2022",
                        "rendered_value": "202백만원",
                        "raw_value": "202",
                        "raw_unit": "백만원",
                        "normalized_value": 202_000_000.0,
                        "normalized_unit": "KRW",
                    },
                },
            },
        }
        narrative_row = {
            "task_id": "task_summary",
            "metric_family": "narrative_summary",
            "operation_family": "narrative_summary",
            "answer": "보수적인 관리 강화가 증가 원인입니다.",
            "status": "ok",
            "selected_claim_ids": ["driver_1"],
            "calculation_result": {
                "status": "ok",
                "formatted_result": "보수적인 관리 강화가 증가 원인입니다.",
            },
        }
        final_answer = (
            "2023년 metric은 303백만원이며, 2022년 202백만원 대비 50% 증가했습니다. "
            "보수적인 관리 강화가 증가 원인입니다."
        )
        candidate = self.agent._uncovered_supported_growth_narrative_candidate(
            query="2023년 metric 증가율을 계산하고 원인을 설명해 줘.",
            answer=final_answer,
            ordered_results=[growth_row, narrative_row],
            evidence_items=[
                {
                    "evidence_id": "driver_1",
                    "claim": "보수적인 관리 강화가 증가 원인입니다.",
                    "quote_span": "보수적인 관리 강화가 증가 원인입니다.",
                },
                {
                    "evidence_id": "driver_2",
                    "claim": "시장 환경 둔화에 따라 추가 관리가 강화되었으며 이는 metric 증가의 원인 중 하나입니다.",
                    "quote_span": "시장 환경 둔화에 따라 추가 관리가 강화되었으며 이는 metric 증가의 원인 중 하나입니다.",
                },
            ],
        )

        self.assertIn("시장 환경 둔화", candidate["sentence"])
        self.assertIn("driver_2", candidate["selected_claim_ids"])

    def test_uncovered_growth_narrative_skips_covered_driver_group(self) -> None:
        growth_row = {
            "task_id": "task_growth",
            "metric_family": "concept_growth_rate",
            "operation_family": "growth_rate",
            "answer": "41.4%",
            "status": "ok",
        }
        narrative_row = {
            "task_id": "task_summary",
            "metric_family": "narrative_summary",
            "operation_family": "narrative_summary",
            "answer": "개발/운영비는 Poshmark 연결 편입효과로 인해 전년대비 상승하였습니다.",
            "status": "ok",
            "selected_claim_ids": ["driver_cost"],
        }
        final_answer = (
            "2023년 커머스 매출액은 전년 대비 41.4% 성장했습니다. "
            "Poshmark의 성공적인 체질 개선이 주요 원인 중 하나입니다. "
            "또한 연결 편입 효과도 실적 성장에 기여했습니다."
        )

        candidate = self.agent._uncovered_supported_growth_narrative_candidate(
            query="커머스 부문의 2023년 매출 성장률을 계산하고, 포시마크(Poshmark) 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            answer=final_answer,
            ordered_results=[growth_row, narrative_row],
            evidence_items=[
                {
                    "evidence_id": "driver_cost",
                    "claim": "개발/운영비는 Poshmark 연결 편입효과로 인해 전년대비 상승하였습니다.",
                    "quote_span": "개발/운영비는 Poshmark 연결 편입효과로 인해 전년대비 상승하였습니다.",
                }
            ],
        )

        self.assertEqual({}, candidate)

    def test_nested_promotion_reads_answer_slot_subtask_results(self) -> None:
        stale_prior = {
            "task_id": "task_prior",
            "operation_family": "lookup",
            "answer": "(303) units",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "(303) units",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {
                        "status": "ok",
                        "raw_value": "(303)",
                        "raw_unit": "units",
                    },
                },
                "source_row_ids": ["visible_row"],
            },
        }
        stronger_prior = {
            "task_id": "task_prior",
            "operation_family": "lookup",
            "answer": "(1,847,775) units",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "(1,847,775) units",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {
                        "status": "ok",
                        "raw_value": "(1,847,775)",
                        "raw_unit": "units",
                    },
                },
                "source_row_ids": ["seed_row"],
            },
        }
        narrative = {
            "task_id": "task_narrative",
            "operation_family": "aggregate_subtasks",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "operation_family": "aggregate_subtasks",
                    "subtask_results": [stronger_prior],
                },
            },
        }

        promoted = self.agent._promote_stronger_nested_aggregate_results([stale_prior, narrative])

        self.assertEqual(promoted[0]["calculation_result"]["rendered_value"], "(1,847,775) units")
        self.assertTrue(promoted[0]["promoted_from_nested_aggregate"])

    def test_aggregate_subtasks_preserves_supported_quantitative_impact_answer(self) -> None:
        self.agent.llm = None
        state = {
            "query": "2023년 주석에서 '평가손실' 규모를 찾고, 이것이 영업비용에 미친 영향을 분석해 줘.",
            "calc_subtasks": [{"task_id": "task_1"}],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "영업비용 대비 평가손실 비중",
                "operation_family": "ratio",
            },
            "answer": "2023년 연결기준 영업비용 대비 평가손실 비중은 2.00%입니다.",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "2.00%",
                "formatted_result": "2023년 연결기준 영업비용 대비 평가손실 비중은 2.00%입니다.",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "영업비용 대비 평가손실 비중",
                    "primary_value": {
                        "status": "ok",
                        "label": "영업비용 대비 평가손실 비중",
                        "raw_value": "2.00",
                        "raw_unit": "%",
                        "normalized_value": 2.0,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "2.00%",
                    },
                },
            },
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "evidence_items": [
                {
                    "evidence_id": "ev_loss",
                    "claim": "평가손실 2,000",
                    "metadata": {
                        "table_value_labels_text": "평가손실 2,000",
                        "unit_hint": "백만원",
                        "statement_type": "notes",
                        "consolidation_scope": "consolidated",
                        "period_focus": "current",
                    },
                },
                {
                    "evidence_id": "ev_cost",
                    "claim": "영업비용 100,000",
                    "metadata": {
                        "table_value_labels_text": "영업비용 100,000",
                        "unit_hint": "백만원",
                        "statement_type": "income_statement",
                        "consolidation_scope": "consolidated",
                        "period_focus": "current",
                    },
                },
                {
                    "evidence_id": "ev_relation",
                    "claim": "동 비용에는 평가손실 금액이 포함되어 있습니다.",
                    "metadata": {
                        "statement_type": "notes",
                        "consolidation_scope": "consolidated",
                        "period_focus": "current",
                    },
                },
            ],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("평가손실은 2,000백만원입니다", updated["answer"])
        self.assertIn("영업비용에 포함되어 비용을 증가시키고 매출총이익을 압박하는 요인", updated["answer"])
        self.assertIn("영업비용 100,000백만원 대비 약 2.00%", updated["answer"])
        self.assertEqual(set(updated["selected_claim_ids"]), {"ev_cost", "ev_loss"})

    def test_quantitative_impact_relation_chunk_is_promoted_as_section_seed(self) -> None:
        self.agent.vsm = type(
            "_VSM",
            (),
            {
                "bm25_docs": [
                    "영업실적 일반 설명입니다.",
                    "수익인식 정책상 반품 권리와 관련된 금액만큼 매출원가를 조정합니다.",
                    "기간동안 비용으로 인식한 재고자산의 원가에 대한 기술\n동 비용에는 재고자산평가손실 금액이 포함되어 있습니다.",
                ],
                "bm25_metadatas": [
                    {
                        "chunk_uid": "mda::1",
                        "company": "테스트",
                        "year": 2023,
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                        "block_type": "paragraph",
                        "statement_type": "mda",
                    },
                    {
                        "chunk_uid": "note::false_positive",
                        "company": "테스트",
                        "year": 2023,
                        "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                        "block_type": "table",
                        "statement_type": "notes",
                        "table_row_labels_text": (
                            "수익인식 정책상 반품 권리와 관련된 금액만큼 매출원가를 조정합니다."
                        ),
                    },
                    {
                        "chunk_uid": "note::1",
                        "company": "테스트",
                        "year": 2023,
                        "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                        "block_type": "table",
                        "statement_type": "notes",
                        "table_row_labels_text": (
                            "기간동안 비용으로 인식한 재고자산의 원가에 대한 기술 "
                            "동 비용에는 재고자산평가손실 금액이 포함되어 있습니다."
                        ),
                    },
                ],
            },
        )()
        state = {
            "query": "2023년 재무제표 주석에서 재고자산평가손실 규모와 매출원가 영향을 분석해 줘.",
            "topic": "재고자산평가손실 매출원가 영향",
            "intent": "comparison",
            "query_type": "comparison",
            "companies": ["테스트"],
            "years": [2023],
            "active_subtask": {
                "operation_family": "narrative_summary",
                "preferred_sections": ["IV. 이사의 경영진단 및 분석의견"],
            },
        }

        docs = self.agent._supplement_section_seed_docs(state)

        self.assertGreaterEqual(len(docs), 1)
        self.assertEqual(docs[0][0].metadata["chunk_uid"], "note::1")
        self.assertIn("포함", docs[0][0].page_content)

    def test_aggregate_subtasks_prefers_supported_aggregate_answer_over_weaker_growth_trace(self) -> None:
        self.agent.llm = None
        supported_answer = (
            "2023년 metric은 전년 대비 70.28% 증가한 3,146,409백만원입니다. "
            "이 증가는 driver context 때문입니다."
        )
        state = {
            "query": "2023년 metric 증가율을 계산하고 원인을 설명해 줘.",
            "answer": "2023년 metric은 (303)백만원이며, 2022년 (303)백만원 대비 0% 증가했습니다.",
            "compressed_answer": "2023년 metric은 (303)백만원이며, 2022년 (303)백만원 대비 0% 증가했습니다.",
            "calc_subtasks": [
                {"task_id": "task_growth"},
                {"task_id": "task_summary"},
                {"task_id": "task_aggregate"},
            ],
            "active_subtask_index": 2,
            "active_subtask": {
                "task_id": "task_aggregate",
                "metric_family": "concept_growth_rate",
                "metric_label": "metric growth",
                "operation_family": "aggregate_subtasks",
            },
            "subtask_results": [
                {
                    "task_id": "task_growth",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "metric growth",
                    "operation_family": "growth_rate",
                    "answer": "2023년 metric은 (303)백만원이며, 2022년 (303)백만원 대비 0% 증가했습니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "operation_family": "growth_rate",
                        "rendered_value": "0%",
                        "formatted_result": "2023년 metric은 (303)백만원이며, 2022년 (303)백만원 대비 0% 증가했습니다.",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "metric growth",
                                "period": "2023",
                                "rendered_value": "0%",
                                "raw_value": "0",
                                "raw_unit": "%",
                                "normalized_value": 0.0,
                                "normalized_unit": "PERCENT",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "metric",
                                "period": "2023",
                                "rendered_value": "(303)백만원",
                                "raw_value": "(303)",
                                "raw_unit": "백만원",
                                "normalized_value": -303_000_000.0,
                                "normalized_unit": "KRW",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "metric",
                                "period": "2022",
                                "rendered_value": "(303)백만원",
                                "raw_value": "(303)",
                                "raw_unit": "백만원",
                                "normalized_value": -303_000_000.0,
                                "normalized_unit": "KRW",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_summary",
                    "metric_family": "narrative_summary",
                    "operation_family": "narrative_summary",
                    "answer": "driver context 때문입니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "formatted_result": "driver context 때문입니다.",
                    },
                },
                {
                    "task_id": "task_aggregate",
                    "metric_family": "concept_growth_rate",
                    "operation_family": "aggregate_subtasks",
                    "answer": supported_answer,
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": supported_answer,
                        "formatted_result": supported_answer,
                        "subtask_results": [],
                        "answer_slots": {"operation_family": "aggregate_subtasks"},
                    },
                },
            ],
            "evidence_items": [],
            "artifacts": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        trace = _resolve_runtime_calculation_trace(updated)
        self.assertEqual(updated["answer"], supported_answer)
        self.assertEqual(trace["calculation_result"]["formatted_result"], supported_answer)
        self.assertEqual(trace["calculation_result"]["rendered_value"], supported_answer)
        self.assertNotIn("(303)백만원", updated["answer"])

    def test_aggregate_subtasks_refreshes_supported_aggregate_numeric_when_trace_is_stronger(self) -> None:
        self.agent.llm = None
        rounded_answer = (
            "2023년 metric은 3조 146십억원으로 전년 대비 70.24% 증가했습니다. "
            "이는 driver context 때문입니다."
        )
        state = {
            "query": "2023년 metric 증가율을 계산하고 원인을 설명해 줘.",
            "answer": rounded_answer,
            "compressed_answer": rounded_answer,
            "calc_subtasks": [
                {"task_id": "task_growth"},
                {"task_id": "task_summary"},
                {"task_id": "task_aggregate"},
            ],
            "active_subtask_index": 2,
            "active_subtask": {
                "task_id": "task_aggregate",
                "metric_family": "concept_growth_rate",
                "metric_label": "metric growth",
                "operation_family": "aggregate_subtasks",
            },
            "subtask_results": [
                {
                    "task_id": "task_growth",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "metric growth",
                    "operation_family": "growth_rate",
                    "answer": "2023년 metric은 2022년 대비 70.28% 증가했습니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "operation_family": "growth_rate",
                        "rendered_value": "70.28%",
                        "formatted_result": "2023년 metric은 2022년 대비 70.28% 증가했습니다.",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "metric growth",
                                "period": "2023",
                                "rendered_value": "70.28%",
                                "raw_value": "70.28",
                                "raw_unit": "%",
                                "normalized_value": 70.28,
                                "normalized_unit": "PERCENT",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "metric",
                                "period": "2023",
                                "rendered_value": "3,146,409백만원",
                                "raw_value": "3,146,409",
                                "raw_unit": "백만원",
                                "normalized_value": 3_146_409_000_000.0,
                                "normalized_unit": "KRW",
                                "source_row_id": "ev_current",
                                "source_row_ids": ["ev_current"],
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "metric",
                                "period": "2022",
                                "rendered_value": "1,847,775백만원",
                                "raw_value": "1,847,775",
                                "raw_unit": "백만원",
                                "normalized_value": 1_847_775_000_000.0,
                                "normalized_unit": "KRW",
                                "source_row_id": "ev_prior",
                                "source_row_ids": ["ev_prior"],
                            },
                        },
                    },
                },
                {
                    "task_id": "task_summary",
                    "metric_family": "narrative_summary",
                    "operation_family": "narrative_summary",
                    "answer": "driver context 때문입니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "formatted_result": "driver context 때문입니다.",
                    },
                },
                {
                    "task_id": "task_aggregate",
                    "metric_family": "concept_growth_rate",
                    "operation_family": "aggregate_subtasks",
                    "answer": rounded_answer,
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": rounded_answer,
                        "formatted_result": rounded_answer,
                        "subtask_results": [],
                        "answer_slots": {"operation_family": "aggregate_subtasks"},
                    },
                },
            ],
            "evidence_items": [],
            "artifacts": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("70.28%", updated["answer"])
        self.assertIn("3,146,409백만원", updated["answer"])
        self.assertIn("1,847,775백만원", updated["answer"])
        self.assertIn("driver context 때문입니다", updated["answer"])
        self.assertNotIn("70.24%", updated["answer"])

    def test_ratio_definition_phrase_does_not_request_explanatory_context(self) -> None:
        self.assertFalse(
            self.agent._query_requests_explanatory_context(
                "2023년 CIR을 계산해 줘. 여기서 CIR은 A 대비 B 비율을 의미한다."
            )
        )
        self.assertTrue(self.agent._query_requests_explanatory_context("2023년 CIR의 의미를 설명해 줘."))

    def test_dependency_rows_preserve_sibling_operand_source_anchor(self) -> None:
        state = {
            "active_subtask": {
                "inputs": [
                    {
                        "role": "minuend",
                        "concept": "operating_profit",
                        "period": "2023",
                        "label": "영업이익",
                        "preferred_task_id": "task_1",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    }
                ]
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_label": "2023년 연결기준 영업이익",
                    "calculation_operands": [
                        {
                            "matched_operand_label": "영업이익",
                            "matched_operand_concept": "operating_profit",
                            "matched_operand_role": "minuend",
                            "source_anchor": "[LG에너지솔루션 | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
                        }
                    ],
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "영업이익",
                                "concept": "operating_profit",
                                "period": "2023",
                                "raw_value": "2,163,234",
                                "raw_unit": "백만원",
                                "normalized_value": 2163234000000.0,
                                "normalized_unit": "KRW",
                            }
                        },
                    },
                }
            ],
        }

        rows = self.agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["source_anchor"],
            "[LG에너지솔루션 | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
        )
        self.assertTrue(rows[0]["dependency_resolved"])

    def test_dependency_rows_prefer_matching_operand_anchor_over_sibling_result_anchor(self) -> None:
        self.agent.vsm = type(
            "StubVSM",
            (),
            {
                "_structure_graph": {
                    "nodes": {
                        "chunk_consolidated_income": {
                            "text": "operating income 6,566,976 revenue 258,935,494",
                            "metadata": {
                                "company": "ACME",
                                "year": "2023",
                                "rcept_no": "r-2023",
                                "section_path": "III. Financial Statements > 2. Consolidated Financial Statements",
                                "table_value_labels_text": "operating income 6,566,976 revenue 258,935,494",
                                "table_row_labels_text": "operating income revenue",
                                "consolidation_scope": "consolidated",
                                "statement_type": "income_statement",
                                "table_source_id": "consolidated-income-table",
                            },
                        }
                    }
                }
            },
        )()
        state = {
            "query": "Calculate the 2023 consolidated operating margin.",
            "report_scope": {"company": "ACME", "year": "2023", "rcept_no": "r-2023", "consolidation": "consolidated"},
            "active_subtask": {
                "inputs": [
                    {
                        "role": "numerator",
                        "concept": "operating_income",
                        "period": "2023",
                        "label": "operating income",
                        "preferred_task_id": "task_income",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output"],
                    }
                ]
            },
            "calc_subtasks": [
                {
                    "task_id": "task_income",
                    "preferred_statement_types": ["income_statement"],
                    "required_operands": [
                        {
                            "role": "numerator",
                            "concept": "operating_income",
                            "label": "operating income",
                            "preferred_statement_types": ["income_statement"],
                        }
                    ],
                }
            ],
            "subtask_results": [
                {
                    "task_id": "task_income",
                    "metric_label": "2023 consolidated operating income",
                    "runtime_evidence": [
                        {
                            "evidence_id": "ev_consolidated_income",
                            "source_anchor": "[ACME | 2023 | III. Financial Statements > 2. Consolidated Financial Statements]",
                            "metadata": {"consolidation_scope": "consolidated", "statement_type": "income_statement"},
                        }
                    ],
                    "calculation_operands": [
                        {
                            "matched_operand_label": "operating income",
                            "matched_operand_concept": "operating_income",
                            "matched_operand_role": "numerator",
                            "raw_value": "6,566,976",
                            "raw_unit": "million",
                            "normalized_value": 6_566_976_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "ev_consolidated_income",
                            "source_row_ids": ["ev_consolidated_income"],
                            "source_anchor": "[ACME | 2023 | III. Financial Statements > 4. Financial Statements]",
                            "consolidation_scope": "consolidated",
                            "statement_type": "income_statement",
                        }
                    ],
                    "calculation_result": {
                        "status": "ok",
                        "source_anchor": "[ACME | 2023 | III. Financial Statements > 4. Financial Statements]",
                        "source_row_ids": ["ev_parent"],
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "operating income",
                                "concept": "operating_income",
                                "period": "2023",
                                "raw_value": "(11,526,297)",
                                "raw_unit": "million",
                                "normalized_value": -11_526_297_000_000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "(11,526,297)million",
                                "source_row_id": "ev_consolidated_income",
                                "source_row_ids": ["ev_consolidated_income"],
                            }
                        },
                    },
                }
            ],
        }
        self.agent._refine_operand_precision_from_evidence_table = lambda row, _evidence: {
            **dict(row),
            "raw_value": "(11,526,297)",
            "normalized_value": -11_526_297_000_000.0,
        }

        rows = self.agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["source_anchor"],
            "[ACME | 2023 | III. Financial Statements > 2. Consolidated Financial Statements]",
        )
        self.assertEqual(rows[0]["raw_value"], "6,566,976")
        self.assertEqual(rows[0]["normalized_value"], 6_566_976_000_000.0)
        self.assertEqual(
            rows[0]["source_row_ids"],
            ["task_output:task_income", "ev_consolidated_income", "ev_parent", "chunk_consolidated_income"],
        )
        self.assertEqual(rows[0]["consolidation_scope"], "consolidated")
        self.assertEqual(rows[0]["statement_type"], "income_statement")
        self.assertEqual(rows[0]["table_source_id"], "consolidated-income-table")

    def test_dependency_rows_resolve_task_output_to_direct_source_metadata(self) -> None:
        state = {
            "active_subtask": {
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "revenue",
                        "period": "2023",
                        "label": "2023년 커머스 매출액",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    }
                ]
            },
            "subtask_results": [
                {
                    "task_id": "task_3",
                    "metric_label": "2023년 커머스 매출액",
                    "runtime_evidence": [
                        {
                            "evidence_id": "ev_001",
                            "source_anchor": "[NAVER | 2023 | IV. 이사의 경영진단 및 분석의견]",
                        }
                    ],
                    "calculation_result": {
                        "status": "ok",
                        "source_row_ids": ["ev_001"],
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "2023년 커머스 매출액",
                                "concept": "revenue",
                                "period": "2023",
                                "raw_value": "2,546,649",
                                "raw_unit": "백만원",
                                "normalized_value": 2546649000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "2,546,649백만원",
                                "source_row_id": "ev_001",
                                "source_row_ids": ["ev_001"],
                            }
                        },
                    },
                }
            ],
        }

        rows = self.agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_row_id"], "task_output:task_3")
        self.assertEqual(rows[0]["source_row_ids"], ["task_output:task_3", "ev_001"])
        self.assertEqual(
            rows[0]["source_anchor"],
            "[NAVER | 2023 | IV. 이사의 경영진단 및 분석의견]",
        )

    def test_dependency_rows_preserve_task_output_when_retrieval_scope_conflicts_evidence_metadata(self) -> None:
        state = {
            "active_subtask": {
                "inputs": [
                    {
                        "role": "numerator",
                        "concept": "operating_income",
                        "period": "2023",
                        "label": "target metric",
                        "preferred_task_id": "task_target",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator",
                        "concept": "operating_income",
                        "period": "2023",
                        "label": "total metric",
                        "preferred_task_id": "task_total",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output"],
                    },
                ]
            },
            "subtask_results": [
                {
                    "task_id": "task_target",
                    "metric_label": "target metric",
                    "runtime_evidence": [
                        {
                            "evidence_id": "ev_target",
                            "source_anchor": "[ACME | 2023 | note]",
                            "metadata": {"consolidation_scope": "연결 기준으로 판단"},
                        }
                    ],
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "target metric",
                                "concept": "operating_income",
                                "period": "2023",
                                "raw_value": "120",
                                "raw_unit": "unit",
                                "normalized_value": 120.0,
                                "normalized_unit": "COUNT",
                                "rendered_value": "120unit",
                                "source_row_id": "ev_target",
                                "source_row_ids": ["ev_target"],
                            }
                        },
                    },
                },
                {
                    "task_id": "task_total",
                    "metric_label": "total metric",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "total metric",
                                "concept": "operating_income",
                                "period": "2023",
                                "raw_value": "150",
                                "raw_unit": "unit",
                                "normalized_value": 150.0,
                                "normalized_unit": "COUNT",
                                "rendered_value": "150unit",
                                "source_row_id": "ev_total",
                                "source_row_ids": ["ev_total"],
                            }
                        },
                    },
                },
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_target",
                    "claim": "target metric 70; total metric 150",
                    "raw_row_text": "target metric 70; total metric 150",
                    "metadata": {
                        "table_value_labels_text": "target metric total metric",
                        "consolidation_scope": "separate",
                    },
                }
            ],
        }
        separate_slot = {
            "label": "target metric",
            "matched_operand_label": "target metric",
            "matched_operand_role": "numerator",
            "raw_value": "70",
            "raw_unit": "unit",
            "normalized_value": 70.0,
            "normalized_unit": "COUNT",
            "period": "2023",
            "source_row_id": "ev_target",
            "source_row_ids": ["ev_target"],
            "consolidation_scope": "separate",
        }
        self.agent._direct_structured_lookup_evidence_score = lambda _binding, _evidence: 0.0
        self.agent._best_direct_lookup_slot_from_evidence_pool_compat = (
            lambda binding, _pool, state=None: (dict(separate_slot), 10.0)
            if binding.get("label") == "target metric"
            else ({}, 0.0)
        )

        rows = self.agent._build_dependency_operand_rows(state)

        self.assertEqual(rows[0]["raw_value"], "120")
        self.assertEqual(rows[0]["normalized_value"], 120.0)
        self.assertEqual(rows[0]["source_row_ids"], ["task_output:task_target", "ev_target"])
        self.assertEqual(rows[0]["consolidation_scope"], "consolidated")

    def test_growth_rate_task_consumes_sibling_lookup_outputs_before_retrieval(self) -> None:
        state = {
            "query": "2023년 시설투자(CAPEX) 총액과 전년 대비 증감률을 계산해 줘.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "삼성전자", "year": 2023},
            "topic": "시설투자(CAPEX) 총액과 전년 대비 증감률",
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "concept_growth_rate",
                "metric_label": "시설투자(CAPEX) 증감률",
                "query": "2023년 시설투자(CAPEX) 증감률을 계산해 줘.",
                "operation_family": "growth_rate",
                "required_operands": [
                    {"label": "2023년 시설투자(CAPEX) 총액", "concept": "capital_expenditure_total", "role": "current_period"},
                    {"label": "2022년 시설투자(CAPEX) 총액", "concept": "capital_expenditure_total", "role": "prior_period"},
                ],
                "depends_on": ["task_1", "task_3"],
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "capital_expenditure_total",
                        "period": "2023",
                        "label": "2023년 시설투자(CAPEX) 총액",
                        "preferred_task_id": "task_1",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "prior_period",
                        "concept": "capital_expenditure_total",
                        "period": "2022",
                        "label": "2022년 시설투자(CAPEX) 총액",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 시설투자(CAPEX) 총액",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 53113900000000.0,
                        "result_unit": "원",
                        "rendered_value": "53조 1,139억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 시설투자(CAPEX) 총액",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2023년 시설투자(CAPEX) 총액",
                                "concept": "capital_expenditure_total",
                                "period": "2023",
                                "raw_value": "53조 1,139억원",
                                "raw_unit": "원",
                                "normalized_value": 53113900000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "53조 1,139억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022년 시설투자(CAPEX) 총액",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 18116800000000.0,
                        "result_unit": "원",
                        "rendered_value": "18조 1,168억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2022년 시설투자(CAPEX) 총액",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2022년 시설투자(CAPEX) 총액",
                                "concept": "capital_expenditure_total",
                                "period": "2022",
                                "raw_value": "18조 1,168억원",
                                "raw_unit": "원",
                                "normalized_value": 18116800000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "18조 1,168억원",
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        extracted = self.agent._extract_calculation_operands(state)
        merged_state = {**state, **extracted}
        trace = _resolve_runtime_calculation_trace(merged_state)
        self.assertEqual(len(trace["calculation_operands"]), 2)
        self.assertEqual(
            [row["matched_operand_role"] for row in trace["calculation_operands"]],
            ["current_period", "prior_period"],
        )

        planned = self.agent._plan_formula_calculation(merged_state)
        plan_trace = _resolve_runtime_calculation_trace(planned)
        self.assertEqual(plan_trace["calculation_plan"]["status"], "ok")
        self.assertEqual(plan_trace["calculation_plan"]["operation"], "growth_rate")
        self.assertEqual(len(plan_trace["calculation_plan"]["ordered_operand_ids"]), 2)

    def test_narrative_summary_subtask_routes_from_evidence_to_compress_and_then_retrieve(self) -> None:
        state = {
            "query": "2023년 커머스 부문 매출 성장률을 계산하고, 포시마크 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            "query_type": "trend",
            "intent": "trend",
            "calc_subtasks": [
                {"task_id": "task_1", "operation_family": "lookup"},
                {"task_id": "task_2", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 1,
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "metric_label": "질문 관련 배경/영향 설명",
                "operation_family": "narrative_summary",
            },
        }

        self.assertEqual(self.agent._route_after_evidence(state), "compress")
        self.assertEqual(self.agent._route_after_validate(state), "advance_subtask")
        self.assertEqual(self.agent._route_after_advance_subtask(state), "retrieve")

    def test_numeric_extractor_advances_when_subtask_loop_exists(self) -> None:
        state = {
            "query": "2023년 연결 현금흐름표에서 배당금 지급 규모를 찾고 주주환원 정책을 요약해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "operation_family": "single_value"},
                {"task_id": "task_2", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "operation_family": "single_value",
            },
        }

        self.assertEqual(self.agent._route_after_numeric_extractor(state), "advance_subtask")

    def test_numeric_extractor_missing_lookup_falls_back_to_reconciliation(self) -> None:
        state = {
            "query": "2023년 재고자산평가손실 규모를 찾아줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "operation_family": "lookup"},
                {"task_id": "task_2", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "operation_family": "lookup",
                "metric_label": "재고자산평가손실",
            },
            "retrieved_docs": [(object(), 1.0)],
            "evidence_status": "missing",
        }

        self.assertEqual(self.agent._route_after_numeric_extractor(state), "reconcile_plan")

    def test_lookup_subtask_routes_to_fresh_retrieval_after_advance(self) -> None:
        state = {
            "query": "2023년 두 개념의 비율을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "operation_family": "lookup"},
                {"task_id": "task_2", "operation_family": "lookup"},
                {"task_id": "task_3", "operation_family": "ratio"},
            ],
            "active_subtask_index": 1,
            "active_subtask": {
                "task_id": "task_2",
                "operation_family": "lookup",
            },
            "retrieved_docs": [(object(), 1.0)],
            "evidence_status": "missing",
        }

        self.assertEqual(self.agent._route_after_advance_subtask(state), "retrieve")

    def test_lookup_subtask_routes_to_numeric_extractor_even_when_top_level_intent_is_qa(self) -> None:
        state = {
            "query": "2023년 재무제표 주석에서 재고자산평가손실 규모와 매출원가 영향을 분석해 줘.",
            "query_type": "qa",
            "intent": "qa",
            "calc_subtasks": [
                {"task_id": "task_1", "operation_family": "lookup"},
                {"task_id": "task_2", "operation_family": "lookup"},
                {"task_id": "task_3", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "operation_family": "lookup",
                "metric_label": "재고자산평가손실(환입) 등",
            },
        }

        self.assertEqual(self.agent._route_after_expand(state), "numeric_extractor")

    def test_non_narrative_subtask_routes_to_reconcile_plan_even_when_top_level_intent_is_qa(self) -> None:
        state = {
            "query": "2023년 재무제표 주석에서 재고자산평가손실 규모와 매출원가 영향을 분석해 줘.",
            "query_type": "qa",
            "intent": "qa",
            "calc_subtasks": [
                {"task_id": "task_1", "operation_family": "lookup"},
                {"task_id": "task_2", "operation_family": "lookup"},
                {"task_id": "task_3", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 1,
            "active_subtask": {
                "task_id": "task_2",
                "operation_family": "lookup",
                "metric_label": "매출원가",
            },
        }

        self.assertEqual(self.agent._route_after_evidence(state), "reconcile_plan")

    def test_formula_planner_route_ignores_legacy_top_level_plan_status(self) -> None:
        state = {
            "query": "route decision",
            "query_type": "comparison",
            "intent": "comparison",
            "reflection_count": 0,
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_plan": {"status": "incomplete"},
        }

        self.assertEqual(self.agent._route_after_formula_planner(state), "calculator")

    def test_calculator_route_ignores_legacy_top_level_result_status(self) -> None:
        state = {
            "query": "route decision",
            "query_type": "comparison",
            "intent": "comparison",
            "reflection_count": 0,
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_result": {"status": "insufficient_operands"},
        }

        self.assertEqual(self.agent._route_after_calculator(state), "calc_render")

    def test_table_label_lookup_uses_period_role_for_repeated_row_labels(self) -> None:
        evidence_item = {
            "evidence_id": "ev_table",
            "source_anchor": "[ExampleCo | 2023 | MD&A]",
            "metadata": {
                "year": 2023,
                "unit_hint": "억원",
                "statement_type": "mda",
                "table_source_id": "mda::table:1",
                "table_header_context": "사업부문 | 당기 | 전기 | 증감률 | 비중",
                "table_value_labels_text": "\n".join(
                    [
                        "영업수익 9,670.6",
                        "영업수익 8,220.1",
                        "영업수익 17.6%",
                        "영업수익 100.0%",
                        "A부문 2,546.6",
                        "A부문 1,801.1",
                        "A부문 41.4%",
                        "A부문 26.4%",
                    ]
                ),
            },
        }
        base_operand = {
            "label": "A부문 매출액",
            "aliases": ["A부문"],
            "concept": "revenue",
        }

        current = self.agent._lookup_value_from_table_label_metadata(
            {**base_operand, "role": "current_period", "period": "2023"},
            evidence_item,
        )
        prior = self.agent._lookup_value_from_table_label_metadata(
            {**base_operand, "role": "prior_period", "period": "2022"},
            evidence_item,
        )

        self.assertEqual(current["raw_value"], "2,546.6")
        self.assertEqual(current["raw_unit"], "억원")
        self.assertEqual(current["period"], "2023")
        self.assertEqual(prior["raw_value"], "1,801.1")
        self.assertEqual(prior["raw_unit"], "억원")
        self.assertEqual(prior["period"], "2022")

    def test_ok_lookup_can_be_replaced_by_stronger_table_label_metadata(self) -> None:
        ordered_results = [
            {
                "task_id": "task_prior",
                "metric_family": "concept_lookup",
                "metric_label": "2022년 A부문 매출액",
                "status": "ok",
                "answer": "2022년 A부문 매출액은 1,801,079천원입니다.",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "prior_period",
                            "label": "2022년 A부문 매출액",
                            "concept": "revenue",
                            "period": "2022",
                            "raw_value": "1,801,079",
                            "raw_unit": "천원",
                            "normalized_value": 1801079000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "ev_weak",
                            "source_row_ids": ["ev_weak"],
                        },
                    },
                },
            }
        ]
        state = {
            "calc_subtasks": [
                {
                    "task_id": "task_prior",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "2022년 A부문 매출액",
                            "aliases": ["A부문"],
                            "concept": "revenue",
                            "role": "prior_period",
                            "period": "2022",
                        }
                    ],
                }
            ],
            "runtime_evidence": [
                {
                    "evidence_id": "ev_table",
                    "source_anchor": "[ExampleCo | 2023 | MD&A]",
                    "metadata": {
                        "year": 2023,
                        "unit_hint": "억원",
                        "statement_type": "mda",
                        "table_source_id": "mda::table:1",
                        "table_value_labels_text": "\n".join(
                            [
                                "A부문 2,546.6",
                                "A부문 1,801.1",
                                "A부문 41.4%",
                            ]
                        ),
                    },
                }
            ],
            "evidence_items": [],
        }

        recovered = self.agent._recover_lookup_results_from_sibling_table_evidence(ordered_results, state)
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertTrue(recovered[0]["recovered_from_sibling_table_evidence"])
        self.assertEqual(slot["raw_value"], "1,801.1")
        self.assertEqual(slot["raw_unit"], "억원")
        self.assertEqual(slot["source_row_id"], "ev_table")

    def test_growth_operands_align_units_when_raw_scale_matches(self) -> None:
        rows = [
            {
                "operand_id": "current",
                "matched_operand_role": "current_period",
                "matched_operand_concept": "revenue",
                "raw_value": "2,546,649",
                "raw_unit": "백만원",
                "normalized_value": 2546649000000.0,
                "normalized_unit": "KRW",
            },
            {
                "operand_id": "prior",
                "matched_operand_role": "prior_period",
                "matched_operand_concept": "revenue",
                "raw_value": "1,801,079",
                "raw_unit": "천원",
                "normalized_value": 1801079000.0,
                "normalized_unit": "KRW",
            },
        ]

        aligned = self.agent._align_growth_operand_units_when_raw_scale_matches(rows)
        prior = next(row for row in aligned if row["operand_id"] == "prior")

        self.assertEqual(prior["raw_unit"], "백만원")
        self.assertEqual(prior["normalized_value"], 1801079000000.0)
        self.assertEqual(prior["unit_alignment_source"], "growth_raw_scale_match")

    def test_execute_growth_aligns_units_when_only_one_concept_is_known(self) -> None:
        state = {
            "query": "Calculate segment revenue growth.",
            "active_subtask": {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "segment revenue growth",
                "operation_family": "growth_rate",
                "required_operands": [
                    {"label": "segment revenue", "concept": "revenue", "role": "current_period"},
                    {"label": "segment revenue", "concept": "revenue", "role": "prior_period"},
                ],
            },
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "current",
                        "matched_operand_role": "operand",
                        "matched_operand_concept": "",
                        "label": "segment revenue",
                        "raw_value": "2,546,649",
                        "raw_unit": "백만원",
                        "normalized_value": 2546649000000.0,
                        "normalized_unit": "KRW",
                    },
                    {
                        "operand_id": "prior",
                        "matched_operand_role": "prior_period",
                        "matched_operand_concept": "revenue",
                        "label": "segment revenue",
                        "raw_value": "1,801,079",
                        "raw_unit": "천원",
                        "normalized_value": 1801079000.0,
                        "normalized_unit": "KRW",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "growth_rate",
                    "operation_family": "growth_rate",
                    "formula": "((A - B) / B) * 100",
                    "result_unit": "%",
                    "ordered_operand_ids": ["current", "prior"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "current"},
                        {"variable": "B", "operand_id": "prior"},
                    ],
                },
                "calculation_result": {},
            },
        }

        result = self.agent._execute_calculation(state)
        trace = result["resolved_calculation_trace"]
        prior = next(
            row
            for row in trace["calculation_operands"]
            if row.get("operand_id") == "prior"
        )

        self.assertEqual(prior["raw_unit"], "백만원")
        self.assertEqual(prior["normalized_value"], 1801079000000.0)
        self.assertEqual(prior["unit_alignment_source"], "growth_raw_scale_match")
        self.assertAlmostEqual(
            trace["calculation_result"]["result_value"],
            41.396,
            places=2,
        )

    def test_execute_growth_repairs_raw_unit_scale_before_magnitude_policy(self) -> None:
        state = {
            "query": "신용손실충당금전입액 전년 대비 증가율을 계산해 줘.",
            "active_subtask": {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "신용손실충당금전입액 증가율",
                "operation_family": "growth_rate",
                "required_operands": [
                    {
                        "label": "신용손실충당금전입액",
                        "concept": "credit_loss_provision_expense",
                        "role": "current_period",
                    },
                    {
                        "label": "신용손실충당금전입액",
                        "concept": "credit_loss_provision_expense",
                        "role": "prior_period",
                    },
                ],
            },
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "current",
                        "matched_operand_role": "current_period",
                        "matched_operand_concept": "credit_loss_provision_expense",
                        "label": "신용손실충당금전입액",
                        "raw_value": "3,146",
                        "raw_unit": "십억원",
                        "normalized_value": 3146.0,
                        "normalized_unit": "KRW",
                        "statement_type": "summary_financials",
                    },
                    {
                        "operand_id": "prior",
                        "matched_operand_role": "prior_period",
                        "matched_operand_concept": "credit_loss_provision_expense",
                        "label": "신용손실충당금전입액",
                        "raw_value": "(1,847,775)",
                        "raw_unit": "백만원",
                        "normalized_value": -1847775000000.0,
                        "normalized_unit": "KRW",
                        "statement_type": "income_statement",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "growth_rate",
                    "operation_family": "growth_rate",
                    "formula": "((A - B) / B) * 100",
                    "result_unit": "%",
                    "ordered_operand_ids": ["current", "prior"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "current"},
                        {"variable": "B", "operand_id": "prior"},
                    ],
                },
                "calculation_result": {},
            },
        }

        result = self.agent._execute_calculation(state)
        trace = result["resolved_calculation_trace"]
        operands = {row["operand_id"]: row for row in trace["calculation_operands"]}

        self.assertEqual(operands["current"]["normalized_value"], 3_146_000_000_000.0)
        self.assertEqual(operands["current"]["unit_normalization_repair_source"], "raw_unit_scale")
        self.assertEqual(operands["prior"]["normalized_value"], 1_847_775_000_000.0)
        self.assertEqual(operands["prior"]["value_coercion"], "lookup_magnitude_from_source_surface")
        self.assertAlmostEqual(trace["calculation_result"]["result_value"], 70.26, places=2)

    def test_reconcile_short_circuits_when_dependency_outputs_are_fully_resolved(self) -> None:
        state = {
            "query": "커머스 부문의 2023년 매출 성장률(전년 대비)을 계산해 줘.",
            "query_type": "trend",
            "intent": "trend",
            "report_scope": {
                "source_reports": [
                    {"corp_name": "NAVER", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
                    {"corp_name": "NAVER", "year": 2022, "report_type": "사업보고서", "rcept_no": "20230314001049"},
                ]
            },
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_growth_rate",
                "metric_label": "커머스 부문 매출 성장률",
                "query": "연결기준 커머스 부문 매출 성장률(커머스 매출액/커머스 매출액)을 계산해 줘.",
                "operation_family": "growth_rate",
                "required_operands": [
                    {"label": "커머스 매출액", "concept": "revenue", "role": "current_period"},
                    {"label": "커머스 매출액", "concept": "revenue", "role": "prior_period"},
                ],
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "revenue",
                        "period": "2023",
                        "label": "커머스 매출액",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                        "segment_label": "커머스",
                    },
                    {
                        "role": "prior_period",
                        "concept": "revenue",
                        "period": "2022",
                        "label": "커머스 매출액",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                        "segment_label": "커머스",
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022년 커머스 매출액",
                    "status": "ok",
                    "calculation_result": {
                        "result_value": 1801079000000,
                        "result_unit": "KRW",
                        "answer_slots": {
                            "primary_value": {
                                "label": "2022년 커머스 매출액",
                                "raw_value": "1조 8,011억원",
                                "raw_unit": "원",
                                "normalized_value": 1801079000000,
                                "normalized_unit": "KRW",
                                "period": "2022",
                                "source_anchor": "[NAVER | 2022 | IV. 이사의 경영진단 및 분석의견]",
                            }
                        },
                    },
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 커머스 매출액",
                    "status": "ok",
                    "calculation_result": {
                        "result_value": 2546649000000,
                        "result_unit": "KRW",
                        "answer_slots": {
                            "primary_value": {
                                "label": "2023년 커머스 매출액",
                                "raw_value": "2조 5,466억원",
                                "raw_unit": "원",
                                "normalized_value": 2546649000000,
                                "normalized_unit": "KRW",
                                "period": "2023",
                                "source_anchor": "[NAVER | 2023 | IV. 이사의 경영진단 및 분석의견]",
                            }
                        },
                    },
                },
            ],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_items": [],
            "reconciliation_retry_count": 0,
            "tasks": [],
            "artifacts": [],
        }

        updates = self.agent._reconcile_retrieved_evidence(state)
        result = updates["reconciliation_result"]
        self.assertEqual(result["status"], "ready")
        self.assertEqual(
            [item["reason"] for item in result["matched_operands"]],
            ["resolved_from_task_outputs", "resolved_from_task_outputs"],
        )
        self.assertEqual(updates["retry_strategy"], "")

    def test_ratio_task_consumes_sibling_lookup_outputs_before_retrieval(self) -> None:
        state = {
            "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "report_scope": {"company": "네이버", "year": 2023},
            "topic": "종업원급여 비중",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "종업원급여 비중",
                "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "종업원급여", "concept": "employee_benefits_expense", "role": "numerator_1"},
                    {"label": "영업비용", "concept": "operating_expense_total", "role": "denominator_1"},
                ],
                "depends_on": ["task_2", "task_3"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "employee_benefits_expense",
                        "period": "2023",
                        "label": "종업원급여",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_expense_total",
                        "period": "2023",
                        "label": "영업비용",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 종업원급여",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 1701418940000.0,
                        "result_unit": "천원",
                        "rendered_value": "1조 7,014억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 종업원급여",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2023년 종업원급여",
                                "concept": "employee_benefits_expense",
                                "period": "2023",
                                "raw_value": "1,701,418,940",
                                "raw_unit": "천원",
                                "normalized_value": 1701418940000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "1조 7,014억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 영업비용",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 8181823307000.0,
                        "result_unit": "천원",
                        "rendered_value": "8조 1,818억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 영업비용",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2023년 영업비용",
                                "concept": "operating_expense_total",
                                "period": "2023",
                                "raw_value": "8,181,823,307",
                                "raw_unit": "천원",
                                "normalized_value": 8181823307000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "8조 1,818억원",
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        extracted = self.agent._extract_calculation_operands(state)
        merged_state = {**state, **extracted}
        trace = _resolve_runtime_calculation_trace(merged_state)
        self.assertEqual(
            [row["matched_operand_role"] for row in trace["calculation_operands"]],
            ["numerator_1", "denominator_1"],
        )

        planned = self.agent._plan_formula_calculation(merged_state)
        plan_trace = _resolve_runtime_calculation_trace(planned)
        self.assertEqual(plan_trace["calculation_plan"]["status"], "ok")
        self.assertEqual(plan_trace["calculation_plan"]["operation"], "ratio")
        self.assertEqual(len(plan_trace["calculation_plan"]["ordered_operand_ids"]), 2)

    def test_ratio_dependency_prefers_same_table_sibling_retrieval_slot(self) -> None:
        state = {
            "query": "2023년 수익성 표의 비용 비율을 계산해 줘.",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "비용 비율",
                "operation_family": "ratio",
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "expense_component",
                        "period": "2023",
                        "label": "비용항목",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "profit_before_expense",
                        "period": "2023",
                        "label": "차감전이익",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "비용항목",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 435_542_000.0,
                        "result_unit": "천원",
                        "rendered_value": "435,542천원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "numerator_1",
                                "label": "비용항목",
                                "concept": "expense_component",
                                "period": "2023",
                                "raw_value": "435,542",
                                "raw_unit": "천원",
                                "normalized_value": 435_542_000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "435,542천원",
                                "source_row_id": "ev_current",
                                "source_row_ids": ["ev_current"],
                            },
                        },
                    },
                    "runtime_evidence": [
                        {
                            "evidence_id": "ev_current",
                            "claim": "비용항목 435,542천원",
                            "quote_span": "비용항목 435,542천원",
                            "metadata": {
                                "row_label": "비용항목",
                                "semantic_label": "비용항목",
                                "unit_hint": "천원",
                                "structured_cells": [
                                    {
                                        "value_text": "435,542",
                                        "unit_hint": "천원",
                                        "column_headers": ["2023"],
                                    }
                                ],
                            },
                        }
                    ],
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "차감전이익",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "denominator_1",
                                "label": "차감전이익",
                                "concept": "profit_before_expense",
                                "period": "2023",
                                "raw_value": "11,623",
                                "raw_unit": "억원",
                                "normalized_value": 1_162_300_000_000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "11,623억원",
                                "source_row_id": "ev_table",
                                "source_row_ids": ["ev_table"],
                            },
                        },
                    },
                },
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_table",
                    "claim": "차감전이익 11,623억원; 비용항목 4,355억원",
                    "quote_span": "차감전이익 11,623억원; 비용항목 4,355억원",
                    "source_anchor": "[ACME | 2023 | Management Discussion]",
                    "metadata": {
                        "unit_hint": "억원",
                        "table_source_id": "management::profitability",
                        "table_value_labels_text": "차감전이익 11,623\n비용항목 4,355",
                        "table_row_labels_text": "차감전이익\n비용항목",
                    },
                }
            ],
        }

        rows = self.agent._build_dependency_operand_rows(state)
        numerator = next(row for row in rows if row["matched_operand_role"] == "numerator_1")

        self.assertEqual(numerator["raw_value"], "4,355")
        self.assertEqual(numerator["raw_unit"], "억원")
        self.assertIn("ev_table", numerator["source_row_ids"])

    def test_lookup_rejects_context_dependent_table_when_scope_not_requested(self) -> None:
        ambiguous_row = {
            "operand_id": "direct_lookup_001",
            "evidence_id": "ev_context_table",
            "source_row_id": "ev_context_table",
            "source_row_ids": ["ev_context_table"],
            "source_anchor": "[ACME | 2023 | Notes]",
            "label": "interest expense",
            "raw_value": "(1,180,096)",
            "raw_unit": "million",
            "normalized_value": -1_180_096_000_000.0,
            "normalized_unit": "KRW",
            "period": "2023",
            "matched_operand_label": "interest expense",
            "matched_operand_concept": "interest_expense",
            "matched_operand_role": "primary_value",
        }
        ambiguous_evidence = {
            "evidence_id": "ev_context_table",
            "claim": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million | segment / total (1,180,096) million",
            "quote_span": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million | segment / total (1,180,096) million",
            "raw_row_text": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million | segment / total (1,180,096) million",
            "metadata": {
                "table_view": "column_row_window",
                "unit_hint": "million",
                "statement_type": "notes",
                "structured_cells": [
                    {"column_headers": ["segment", "steel"], "value_text": "(718,937)", "unit_hint": "million"},
                    {"column_headers": ["segment", "trading"], "value_text": "(284,056)", "unit_hint": "million"},
                    {"column_headers": ["segment", "construction"], "value_text": "(105,102)", "unit_hint": "million"},
                    {"column_headers": ["segment", "total"], "value_text": "(1,180,096)", "unit_hint": "million"},
                ],
            },
        }
        state = {
            "query": "Calculate 2023 consolidated interest coverage ratio.",
            "active_subtask": {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "operation_family": "concept_lookup",
                "required_operands": [
                    {
                        "label": "interest expense",
                        "concept": "interest_expense",
                        "role": "primary_value",
                        "required": True,
                    }
                ],
            },
            "evidence_items": [ambiguous_evidence],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "reconciliation_result": {"status": "ready"},
            "calc_subtasks": [],
        }
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [dict(ambiguous_row)]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: [dict(ambiguous_evidence)]

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(trace["calculation_operands"], [])
        self.assertEqual(extracted["calculation_debug_trace"]["coverage"], "missing")

    def test_lookup_rejects_context_dependent_table_without_required_operands(self) -> None:
        ambiguous_row = {
            "operand_id": "direct_lookup_001",
            "evidence_id": "ev_context_table",
            "source_row_id": "ev_context_table",
            "source_row_ids": ["ev_context_table"],
            "source_anchor": "[ACME | 2023 | Notes]",
            "label": "interest expense",
            "raw_value": "(1,180,096)",
            "raw_unit": "million",
            "normalized_value": -1_180_096_000_000.0,
            "normalized_unit": "KRW",
            "period": "2023",
            "matched_operand_label": "interest expense",
            "matched_operand_concept": "interest_expense",
            "matched_operand_role": "primary_value",
        }
        ambiguous_evidence = {
            "evidence_id": "ev_context_table",
            "claim": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million | segment / total (1,180,096) million",
            "quote_span": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million | segment / total (1,180,096) million",
            "raw_row_text": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million | segment / total (1,180,096) million",
            "metadata": {
                "table_view": "column_row_window",
                "unit_hint": "million",
                "statement_type": "notes",
                "structured_cells": [
                    {"column_headers": ["segment", "steel"], "value_text": "(718,937)", "unit_hint": "million"},
                    {"column_headers": ["segment", "trading"], "value_text": "(284,056)", "unit_hint": "million"},
                    {"column_headers": ["segment", "construction"], "value_text": "(105,102)", "unit_hint": "million"},
                    {"column_headers": ["segment", "total"], "value_text": "(1,180,096)", "unit_hint": "million"},
                ],
            },
        }
        state = {
            "query": "Calculate 2023 consolidated interest coverage ratio.",
            "active_subtask": {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "metric_label": "interest expense",
            },
            "evidence_items": [ambiguous_evidence],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "reconciliation_result": {"status": "ready"},
            "calc_subtasks": [],
        }
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [dict(ambiguous_row)]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: [dict(ambiguous_evidence)]

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(trace["calculation_operands"], [])
        self.assertEqual(extracted["calculation_debug_trace"]["coverage"], "missing")

    def test_lookup_allows_context_dependent_table_when_scope_requested(self) -> None:
        scoped_row = {
            "operand_id": "direct_lookup_001",
            "evidence_id": "ev_context_table",
            "source_row_id": "ev_context_table",
            "source_row_ids": ["ev_context_table"],
            "source_anchor": "[ACME | 2023 | Notes]",
            "label": "interest expense",
            "raw_value": "(718,937)",
            "raw_unit": "million",
            "normalized_value": -718_937_000_000.0,
            "normalized_unit": "KRW",
            "period": "2023",
            "matched_operand_label": "interest expense",
            "matched_operand_concept": "interest_expense",
            "matched_operand_role": "primary_value",
        }
        scoped_evidence = {
            "evidence_id": "ev_context_table",
            "claim": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million",
            "quote_span": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million",
            "raw_row_text": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million",
            "metadata": {
                "table_view": "column_row_window",
                "unit_hint": "million",
                "statement_type": "notes",
                "structured_cells": [
                    {"column_headers": ["segment", "steel"], "value_text": "(718,937)", "unit_hint": "million"},
                    {"column_headers": ["segment", "trading"], "value_text": "(284,056)", "unit_hint": "million"},
                    {"column_headers": ["segment", "construction"], "value_text": "(105,102)", "unit_hint": "million"},
                    {"column_headers": ["segment", "total"], "value_text": "(1,180,096)", "unit_hint": "million"},
                ],
            },
        }
        state = {
            "query": "Calculate the 2023 steel segment interest expense.",
            "active_subtask": {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "required_operands": [
                    {
                        "label": "interest expense",
                        "concept": "interest_expense",
                        "role": "primary_value",
                        "required": True,
                    }
                ],
            },
            "evidence_items": [scoped_evidence],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "reconciliation_result": {"status": "ready"},
            "calc_subtasks": [],
        }
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [dict(scoped_row)]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: [dict(scoped_evidence)]

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(len(trace["calculation_operands"]), 1)
        self.assertEqual(trace["calculation_operands"][0]["raw_value"], "(718,937)")

    def test_ratio_rejects_context_dependent_table_operand_when_scope_not_requested(self) -> None:
        numerator_row = {
            "operand_id": "direct_ratio_001",
            "evidence_id": "ev_income",
            "source_row_id": "ev_income",
            "source_row_ids": ["ev_income"],
            "label": "operating income",
            "raw_value": "3,531,423",
            "raw_unit": "million",
            "normalized_value": 3_531_423_000_000.0,
            "normalized_unit": "KRW",
            "period": "2023",
            "matched_operand_label": "operating income",
            "matched_operand_concept": "operating_income",
            "matched_operand_role": "numerator_1",
        }
        ambiguous_denominator_row = {
            "operand_id": "direct_ratio_002",
            "evidence_id": "ev_context_table",
            "source_row_id": "ev_context_table",
            "source_row_ids": ["ev_context_table"],
            "label": "interest expense",
            "raw_value": "(1,180,096)",
            "raw_unit": "million",
            "normalized_value": -1_180_096_000_000.0,
            "normalized_unit": "KRW",
            "period": "2023",
            "matched_operand_label": "interest expense",
            "matched_operand_concept": "interest_expense",
            "matched_operand_role": "denominator_1",
        }
        income_evidence = {
            "evidence_id": "ev_income",
            "claim": "operating income 3,531,423 million",
            "quote_span": "operating income 3,531,423 million",
            "metadata": {
                "unit_hint": "million",
                "table_value_labels_text": "operating income 3,531,423",
            },
        }
        ambiguous_evidence = {
            "evidence_id": "ev_context_table",
            "claim": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million | segment / total (1,180,096) million",
            "quote_span": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million | segment / total (1,180,096) million",
            "raw_row_text": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million | segment / total (1,180,096) million",
            "metadata": {
                "table_view": "column_row_window",
                "unit_hint": "million",
                "statement_type": "notes",
                "structured_cells": [
                    {"column_headers": ["segment", "steel"], "value_text": "(718,937)", "unit_hint": "million"},
                    {"column_headers": ["segment", "trading"], "value_text": "(284,056)", "unit_hint": "million"},
                    {"column_headers": ["segment", "construction"], "value_text": "(105,102)", "unit_hint": "million"},
                    {"column_headers": ["segment", "total"], "value_text": "(1,180,096)", "unit_hint": "million"},
                ],
            },
        }
        state = {
            "query": "Calculate 2023 consolidated interest coverage ratio.",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "interest_coverage_ratio",
                "operation_family": "ratio",
                "required_operands": [
                    {
                        "label": "operating income",
                        "concept": "operating_income",
                        "role": "numerator_1",
                        "required": True,
                    },
                    {
                        "label": "interest expense",
                        "concept": "interest_expense",
                        "role": "denominator_1",
                        "required": True,
                    },
                ],
            },
            "evidence_items": [income_evidence, ambiguous_evidence],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "reconciliation_result": {"status": "ready"},
            "calc_subtasks": [],
        }
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [
            dict(numerator_row),
            dict(ambiguous_denominator_row),
        ]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: [
            dict(income_evidence),
            dict(ambiguous_evidence),
        ]

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)
        operands = list(trace.get("calculation_operands") or [])
        debug_operands = list((extracted.get("calculation_debug_trace") or {}).get("operands") or [])
        all_rows = operands + debug_operands

        self.assertFalse(any(row.get("raw_value") == "(1,180,096)" for row in all_rows))

    def test_ratio_rejects_direct_rows_when_consolidation_scope_conflicts(self) -> None:
        numerator_row = {
            "operand_id": "direct_ratio_001",
            "evidence_id": "ev_income",
            "source_row_id": "ev_income",
            "source_row_ids": ["ev_income"],
            "source_anchor": "[ACME | 2023 | III. Financial Statements > 4. Financial Statements]",
            "label": "operating income",
            "raw_value": "(11,526,297)",
            "raw_unit": "million",
            "normalized_value": -11_526_297_000_000.0,
            "normalized_unit": "KRW",
            "period": "2023",
            "consolidation_scope": "separate",
            "matched_operand_label": "operating income",
            "matched_operand_concept": "operating_income",
            "matched_operand_role": "numerator",
        }
        denominator_row = {
            "operand_id": "direct_ratio_002",
            "evidence_id": "ev_revenue",
            "source_row_id": "ev_revenue",
            "source_row_ids": ["ev_revenue"],
            "source_anchor": "[ACME | 2023 | III. Financial Statements > 4. Financial Statements]",
            "label": "revenue",
            "raw_value": "258,935,494",
            "raw_unit": "million",
            "normalized_value": 258_935_494_000_000.0,
            "normalized_unit": "KRW",
            "period": "2023",
            "consolidation_scope": "separate",
            "matched_operand_label": "revenue",
            "matched_operand_concept": "revenue",
            "matched_operand_role": "denominator",
        }
        income_evidence = {
            "evidence_id": "ev_income",
            "claim": "operating income (11,526,297) million",
            "metadata": {
                "consolidation_scope": "separate",
                "section_path": "III. Financial Statements > 4. Financial Statements",
            },
        }
        revenue_evidence = {
            "evidence_id": "ev_revenue",
            "claim": "revenue 258,935,494 million",
            "metadata": {
                "consolidation_scope": "separate",
                "section_path": "III. Financial Statements > 4. Financial Statements",
            },
        }
        state = {
            "query": "Calculate the 2023 consolidated operating margin.",
            "report_scope": {"company": "ACME", "year": "2023", "consolidation": "consolidated"},
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "operating_margin",
                "operation_family": "ratio",
                "required_operands": [
                    {
                        "label": "operating income",
                        "concept": "operating_income",
                        "role": "numerator",
                        "required": True,
                    },
                    {
                        "label": "revenue",
                        "concept": "revenue",
                        "role": "denominator",
                        "required": True,
                    },
                ],
            },
            "evidence_items": [income_evidence, revenue_evidence],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "reconciliation_result": {"status": "ready"},
            "calc_subtasks": [],
        }
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [
            dict(numerator_row),
            dict(denominator_row),
        ]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: [
            dict(income_evidence),
            dict(revenue_evidence),
        ]

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(trace["calculation_operands"], [])
        self.assertEqual(extracted["calculation_debug_trace"]["coverage"], "missing")

    def test_ratio_rejects_dependency_rows_when_consolidation_scope_conflicts(self) -> None:
        dependency_rows = [
            {
                "operand_id": "task_output_001",
                "source_row_id": "task_output:task_income",
                "source_row_ids": ["task_output:task_income", "ev_income"],
                "source_anchor": "[ACME | 2023 | III. Financial Statements > 4. Financial Statements]",
                "label": "operating income",
                "raw_value": "(11,526,297)",
                "raw_unit": "million",
                "normalized_value": -11_526_297_000_000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "consolidation_scope": "separate",
                "matched_operand_label": "operating income",
                "matched_operand_concept": "operating_income",
                "matched_operand_role": "numerator",
            },
            {
                "operand_id": "task_output_002",
                "source_row_id": "task_output:task_revenue",
                "source_row_ids": ["task_output:task_revenue", "ev_revenue"],
                "source_anchor": "[ACME | 2023 | III. Financial Statements > 4. Financial Statements]",
                "label": "revenue",
                "raw_value": "258,935,494",
                "raw_unit": "million",
                "normalized_value": 258_935_494_000_000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "consolidation_scope": "separate",
                "matched_operand_label": "revenue",
                "matched_operand_concept": "revenue",
                "matched_operand_role": "denominator",
            },
        ]
        state = {
            "query": "Calculate the 2023 consolidated operating margin.",
            "report_scope": {"company": "ACME", "year": "2023", "consolidation": "consolidated"},
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "operating_margin",
                "operation_family": "ratio",
                "required_operands": [
                    {
                        "label": "operating income",
                        "concept": "operating_income",
                        "role": "numerator",
                        "required": True,
                    },
                    {
                        "label": "revenue",
                        "concept": "revenue",
                        "role": "denominator",
                        "required": True,
                    },
                ],
            },
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "reconciliation_result": {"status": "ready"},
            "calc_subtasks": [],
        }
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: []
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []
        self.agent._dependency_binding_resolution_state = lambda _state: {
            "rows": [dict(row) for row in dependency_rows],
            "bindings": [],
            "resolved_keys": set(),
            "missing_bindings": [],
            "binding_keys": set(),
        }

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(trace["calculation_operands"], [])
        self.assertEqual(extracted["calculation_debug_trace"]["coverage"], "missing")

    def test_ratio_rejects_resolved_dependency_row_outside_producer_scope(self) -> None:
        dependency_row = {
            "operand_id": "task_output_001",
            "source_row_id": "task_output:task_income",
            "source_row_ids": ["task_output:task_income", "ev_income"],
            "source_anchor": "[ACME | 2023 | III. Financial Statements > Notes]",
            "label": "operating income",
            "raw_value": "12,746,074",
            "raw_unit": "million",
            "normalized_value": 12_746_074_000_000.0,
            "normalized_unit": "KRW",
            "period": "2023",
            "consolidation_scope": "consolidated",
            "statement_type": "income_statement",
            "matched_operand_label": "operating income",
            "matched_operand_concept": "operating_income",
            "matched_operand_role": "numerator",
        }
        binding = {
            "label": "operating income",
            "concept": "operating_income",
            "role": "numerator",
            "preferred_task_id": "task_income",
            "required": True,
        }
        state = {
            "query": "Calculate the 2023 consolidated operating margin.",
            "report_scope": {"company": "ACME", "year": "2023", "consolidation": "consolidated"},
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "operating_margin",
                "operation_family": "ratio",
                "required_operands": [
                    binding,
                    {
                        "label": "revenue",
                        "concept": "revenue",
                        "role": "denominator",
                        "required": True,
                    },
                ],
            },
            "calc_subtasks": [
                {
                    "task_id": "task_income",
                    "preferred_statement_types": ["income_statement", "summary_financials"],
                    "preferred_sections": ["Consolidated Financial Statements"],
                    "required_operands": [
                        {
                            "label": "operating income",
                            "concept": "operating_income",
                            "role": "numerator",
                            "preferred_statement_types": ["income_statement", "summary_financials"],
                            "required": True,
                        }
                    ],
                }
            ],
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "reconciliation_result": {"status": "ready"},
        }
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: []
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []
        self.agent._dependency_binding_resolution_state = lambda _state: {
            "rows": [dict(dependency_row)],
            "bindings": [dict(binding)],
            "resolved_keys": {("operating_income", "numerator")},
            "missing_bindings": [],
            "binding_keys": {("operating_income", "numerator")},
        }

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(trace["calculation_operands"], [])
        self.assertEqual(extracted["calculation_debug_trace"]["coverage"], "missing")

    def test_compact_ratio_answer_preserves_common_consolidation_scope(self) -> None:
        calculation_result = {
            "status": "ok",
            "rendered_value": "2.54%",
            "answer_slots": {
                "operation_family": "ratio",
                "metric_label": "operating margin",
                "primary_value": {"rendered_value": "2.54%"},
                "components_by_group": {
                    "numerator": [{"period": "2023", "consolidation_scope": "consolidated"}],
                    "denominator": [{"period": "2023", "consolidation_scope": "consolidated"}],
                },
            },
        }

        answer = self.agent._compact_ratio_answer(
            {"active_subtask": {"metric_label": "operating margin"}},
            calculation_result,
        )

        self.assertEqual(answer, "2023년 연결기준 operating margin은 2.54%입니다.")

    def test_ratio_operand_alignment_uses_shared_table_display_unit(self) -> None:
        display_units = tuple(CALCULATION_RENDER_POLICY.get("source_display_units") or ())
        scale_by_unit = dict(CALCULATION_RENDER_POLICY.get("krw_display_unit_scales") or {})
        smaller_unit = min(display_units, key=lambda unit: scale_by_unit.get(unit, 0.0))
        larger_unit = max(display_units, key=lambda unit: scale_by_unit.get(unit, 0.0))

        ordered_operands = [
            {
                "operand_id": "numerator",
                "label": "metric a",
                "matched_operand_role": "numerator",
                "period": "2023",
                "raw_value": "6,566,976",
                "raw_unit": larger_unit,
                "normalized_value": 6_566_976 * scale_by_unit[larger_unit],
                "normalized_unit": "KRW",
                "rendered_value": f"6,566,976{larger_unit}",
                "table_source_id": "report::table:2",
            },
            {
                "operand_id": "denominator",
                "label": "metric b",
                "matched_operand_role": "denominator",
                "period": "2023",
                "raw_value": "258,935,494",
                "raw_unit": smaller_unit,
                "normalized_value": 258_935_494 * scale_by_unit[smaller_unit],
                "normalized_unit": "KRW",
                "rendered_value": f"258,935,494{smaller_unit}",
                "table_source_id": "report::table:2",
            },
        ]

        aligned = self.agent._align_ratio_operands_with_sibling_table_context(ordered_operands, [])

        self.assertEqual(aligned[1]["raw_unit"], larger_unit)
        self.assertEqual(aligned[1]["original_raw_unit"], smaller_unit)
        self.assertEqual(aligned[1]["normalized_value"], 258_935_494 * scale_by_unit[larger_unit])
        self.assertTrue(aligned[1]["ratio_unit_aligned_from_sibling_table"])

    def test_ratio_operand_alignment_rejects_direct_candidate_with_conflicting_scope(self) -> None:
        ordered_operands = [
            {
                "operand_id": "numerator",
                "label": "target metric",
                "matched_operand_label": "target metric",
                "matched_operand_role": "numerator",
                "period": "2023",
                "raw_value": "120",
                "raw_unit": "unit",
                "normalized_value": 120.0,
                "normalized_unit": "COUNT",
                "consolidation_scope": "consolidated",
                "source_row_ids": ["task_output:numerator", "ev_consolidated_numerator"],
            },
            {
                "operand_id": "denominator",
                "label": "total metric",
                "matched_operand_label": "total metric",
                "matched_operand_role": "denominator",
                "period": "2023",
                "raw_value": "150",
                "raw_unit": "unit",
                "normalized_value": 150.0,
                "normalized_unit": "COUNT",
                "consolidation_scope": "consolidated",
                "source_row_ids": ["ev_consolidated_denominator"],
            },
        ]
        direct_slot = {
            "label": "target metric",
            "matched_operand_label": "target metric",
            "matched_operand_role": "numerator",
            "raw_value": "70",
            "raw_unit": "unit",
            "normalized_value": 70.0,
            "normalized_unit": "COUNT",
            "period": "2023",
            "source_row_id": "ev_separate_numerator",
            "source_row_ids": ["ev_separate_numerator"],
            "consolidation_scope": "separate",
        }
        evidence_items = [
            {
                "evidence_id": "ev_separate_numerator",
                "claim": "target metric 70; total metric 150",
                "raw_row_text": "target metric 70; total metric 150",
                "metadata": {
                    "table_value_labels_text": "target metric total metric",
                    "consolidation_scope": "separate",
                },
            }
        ]
        self.agent._best_direct_lookup_slot_from_evidence_pool = lambda _operand, _pool: (dict(direct_slot), 10.0)

        aligned = self.agent._align_ratio_operands_with_sibling_table_context(ordered_operands, evidence_items)

        self.assertEqual(aligned[0]["raw_value"], "120")
        self.assertEqual(aligned[0]["normalized_value"], 120.0)
        self.assertEqual(aligned[0]["source_row_ids"], ["task_output:numerator", "ev_consolidated_numerator"])
        self.assertNotIn("sibling_table_context_realigned", aligned[0])

    def test_best_direct_lookup_slot_rejects_ambiguous_context_table_without_scope(self) -> None:
        operand = {
            "label": "interest expense",
            "concept": "interest_expense",
            "role": "primary_value",
            "required": True,
        }
        context_evidence = {
            "evidence_id": "ev_context_table",
            "claim": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million | segment / total (1,180,096) million",
            "quote_span": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million | segment / total (1,180,096) million",
            "raw_row_text": "interest expense | segment / steel (718,937) million | segment / trading (284,056) million | segment / total (1,180,096) million",
            "metadata": {
                "table_view": "column_row_window",
                "row_label": "interest expense",
                "semantic_label": "interest expense",
                "unit_hint": "million",
                "statement_type": "notes",
                "structured_cells": [
                    {"column_headers": ["segment", "steel"], "value_text": "(718,937)", "unit_hint": "million"},
                    {"column_headers": ["segment", "trading"], "value_text": "(284,056)", "unit_hint": "million"},
                    {"column_headers": ["segment", "construction"], "value_text": "(105,102)", "unit_hint": "million"},
                    {"column_headers": ["segment", "total"], "value_text": "(1,180,096)", "unit_hint": "million"},
                ],
            },
        }
        state = {
            "query": "Find the 2023 consolidated interest expense.",
            "active_subtask": {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "required_operands": [operand],
            },
        }

        slot, score = self.agent._best_direct_lookup_slot_from_evidence_pool(
            operand,
            [context_evidence],
            state=state,
        )

        self.assertEqual(slot, {})
        self.assertEqual(score, 0.0)

    def test_aggregate_refreshes_stale_ratio_answer_from_projection(self) -> None:
        ratio_result = {
            "status": "ok",
            "result_value": 37.46881183859589,
            "result_unit": "%",
            "rendered_value": "37.47%",
            "formatted_result": "",
            "source_row_ids": ["ev_ratio"],
            "answer_slots": {
                "metric_label": "CIR",
                "operation_family": "ratio",
                "primary_value": {
                    "status": "ok",
                    "role": "primary_value",
                    "label": "CIR",
                    "raw_unit": "%",
                    "normalized_value": 37.46881183859589,
                    "normalized_unit": "PERCENT",
                    "rendered_value": "37.47%",
                    "source_row_id": "ev_ratio",
                    "source_row_ids": ["ev_ratio"],
                },
                "components_by_group": {
                    "numerator": [
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "selling expense",
                            "period": "2023",
                            "raw_value": "4,355",
                            "raw_unit": "hundred million",
                            "normalized_value": 435_500_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "4,355 hundred million",
                            "source_row_id": "ev_ratio",
                        }
                    ],
                    "denominator": [
                        {
                            "status": "ok",
                            "role": "denominator_1",
                            "label": "pre-expense profit",
                            "period": "2023",
                            "raw_value": "11,623",
                            "raw_unit": "hundred million",
                            "normalized_value": 1_162_300_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "11,623 hundred million",
                            "source_row_id": "ev_ratio",
                        }
                    ],
                },
            },
            "derived_metrics": {
                "operation_family": "ratio",
                "formula_result_value": 37.46881183859589,
            },
        }
        state = {
            "query": "Calculate 2023 CIR.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_ratio", "operation_family": "ratio"},
            ],
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "CIR",
                "operation_family": "ratio",
            },
            "active_subtask_index": 0,
            "answer": "CIR is 37.47%.",
            "calculation_result": ratio_result,
            "calculation_plan": {
                "status": "ok",
                "mode": "single_value",
                "operation": "ratio",
                "formula": "((A) / (B)) * 100",
                "result_unit": "%",
            },
            "calculation_operands": [
                {
                    "operand_id": "op_001",
                    "evidence_id": "ev_ratio",
                    "source_row_id": "ev_ratio",
                    "label": "selling expense",
                    "raw_value": "4,355",
                    "raw_unit": "hundred million",
                    "normalized_value": 435_500_000_000.0,
                    "normalized_unit": "KRW",
                    "matched_operand_role": "numerator_1",
                },
                {
                    "operand_id": "op_002",
                    "evidence_id": "ev_ratio",
                    "source_row_id": "ev_ratio",
                    "label": "pre-expense profit",
                    "raw_value": "11,623",
                    "raw_unit": "hundred million",
                    "normalized_value": 1_162_300_000_000.0,
                    "normalized_unit": "KRW",
                    "matched_operand_role": "denominator_1",
                },
            ],
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_ratio",
                    "operation_family": "ratio",
                    "answer": "CIR is 0.04%.",
                    "status": "ok",
                    "calculation_result": {
                        **ratio_result,
                        "result_value": 0.0374724253635034,
                        "rendered_value": "0.04%",
                        "formatted_result": "CIR is 0.04%.",
                        "answer_slots": {
                            **ratio_result["answer_slots"],
                            "primary_value": {
                                **ratio_result["answer_slots"]["primary_value"],
                                "normalized_value": 0.0374724253635034,
                                "rendered_value": "0.04%",
                            },
                        },
                    },
                }
            ],
            "evidence_items": [{"evidence_id": "ev_ratio", "claim": "CIR inputs 4,355 and 11,623"}],
            "artifacts": [],
            "tasks": [],
        }
        self.agent.llm = None

        updated = self.agent._aggregate_calculation_subtasks(state)

        trace = _resolve_runtime_calculation_trace(updated)
        self.assertIn("37.47%", updated["answer"])
        self.assertNotIn("0.04%", updated["answer"])
        self.assertIn("37.47%", trace["calculation_result"]["formatted_result"])
        self.assertIn("37.47%", trace["calculation_result"]["rendered_value"])
        self.assertNotIn("0.04%", trace["calculation_result"]["formatted_result"])
        trace_ratio_row = next(
            row for row in trace["calculation_result"]["subtask_results"] if row["task_id"] == "task_1"
        )
        self.assertIn("37.47%", trace_ratio_row["answer"])
        self.assertNotIn("0.04%", trace_ratio_row["answer"])

    def test_aggregate_recovers_ratio_from_retrieved_same_table_context(self) -> None:
        stale_lookup_rows = [
            {
                "task_id": "task_numerator",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 판매비와관리비",
                "operation_family": "lookup",
                "answer": "2023년 판매비와관리비는 435,542천원입니다.",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "lookup",
                    "rendered_value": "435,542천원",
                    "formatted_result": "2023년 판매비와관리비는 435,542천원입니다.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "2023년 판매비와관리비",
                            "concept": "selling_general_administrative_expense",
                            "period": "2023",
                            "raw_value": "435,542",
                            "raw_unit": "천원",
                            "normalized_value": 435_542_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "435,542천원",
                        },
                    },
                },
            },
            {
                "task_id": "task_denominator",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 경비차감전영업이익",
                "operation_family": "lookup",
                "answer": "2023년 경비차감전영업이익은 11,623백만원입니다.",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "lookup",
                    "rendered_value": "11,623백만원",
                    "formatted_result": "2023년 경비차감전영업이익은 11,623백만원입니다.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "denominator_1",
                            "label": "2023년 경비차감전영업이익",
                            "concept": "pre_expense_operating_profit",
                            "period": "2023",
                            "raw_value": "11,623",
                            "raw_unit": "백만원",
                            "normalized_value": 11_623_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "11,623백만원",
                        },
                    },
                },
            },
        ]
        retrieved_doc = Document(
            page_content=(
                "구분 | 2023년 | 2022년\n"
                "경비차감전영업이익 (A=B+C+D) | 11,623 | 9,199\n"
                "판매비와관리비 (E) | 4,355 | 3,935"
            ),
            metadata={
                "company": "Example",
                "year": 2023,
                "report_type": "사업보고서",
                "section_path": "MDA",
                "table_source_id": "mda::profitability",
                "table_context": "profitability",
                "table_header_context": "구분 | 2023년 | 2022년",
                "table_row_labels_text": "경비차감전영업이익 (A=B+C+D)\n판매비와관리비 (E)",
                "table_value_labels_text": (
                    "경비차감전영업이익 (A=B+C+D) 11,623\n"
                    "경비차감전영업이익 (A=B+C+D) 9,199\n"
                    "판매비와관리비 (E) 4,355\n"
                    "판매비와관리비 (E) 3,935"
                ),
                "unit_hint": "억원",
                "block_type": "table",
            },
        )
        state = {
            "query": "2023년 CIR을 계산해 줘. 여기서 CIR은 A 대비 E 비율을 의미한다.",
            "topic": "CIR",
            "report_scope": {"year": 2023},
            "calc_subtasks": [
                {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "CIR",
                    "operation_family": "ratio",
                    "required_operands": [
                        {
                            "role": "numerator_1",
                            "label": "2023년 판매비와관리비",
                            "concept": "selling_general_administrative_expense",
                            "period": "2023",
                        },
                        {
                            "role": "denominator_1",
                            "label": "2023년 경비차감전영업이익",
                            "concept": "pre_expense_operating_profit",
                            "period": "2023",
                        },
                    ],
                },
                {"task_id": "task_numerator", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_denominator", "metric_family": "concept_lookup", "operation_family": "lookup"},
            ],
            "subtask_results": stale_lookup_rows,
            "retrieved_docs": [(retrieved_doc, 0.1)],
            "seed_retrieved_docs": [],
        }

        prepared = self.agent._prepare_initial_aggregate_state(state)

        self.assertIn("37.47%", prepared.complete_numeric_answer)
        self.assertIn("37.47%", prepared.fallback_answer)
        self.assertIn("4,355억원", prepared.complete_numeric_answer)
        self.assertNotIn("435,542천원", prepared.complete_numeric_answer)
        self.assertNotIn("435,542천원", prepared.fallback_answer)
        projection = self.agent._rebuild_aggregate_projection(
            prepared.ordered_results,
            prepared.complete_numeric_answer,
        )
        projection_operands = projection["calculation_operands"]
        self.assertEqual(
            {(row["matched_operand_role"], row["raw_value"], row["raw_unit"]) for row in projection_operands},
            {("numerator_1", "4,355", "억원"), ("denominator_1", "11,623", "억원")},
        )

    def test_aggregate_keeps_complete_dependency_rows_when_retrieved_context_conflicts_same_unit(self) -> None:
        dependency_rows = [
            {
                "task_id": "task_numerator",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 자본화된 개발비",
                "operation_family": "lookup",
                "answer": "2023년 자본화된 개발비는 181,624,107천원입니다.",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "lookup",
                    "rendered_value": "181,624,107천원",
                    "formatted_result": "2023년 자본화된 개발비는 181,624,107천원입니다.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "2023년 자본화된 개발비",
                            "period": "2023",
                            "raw_value": "181,624,107",
                            "raw_unit": "천원",
                            "normalized_value": 181_624_107_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "181,624,107천원",
                        },
                    },
                },
            },
            {
                "task_id": "task_denominator",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 연구개발비용",
                "operation_family": "lookup",
                "answer": "2023년 연구개발비용은 342,736,271천원입니다.",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "lookup",
                    "rendered_value": "342,736,271천원",
                    "formatted_result": "2023년 연구개발비용은 342,736,271천원입니다.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "denominator_1",
                            "label": "2023년 연구개발비용",
                            "period": "2023",
                            "raw_value": "342,736,271",
                            "raw_unit": "천원",
                            "normalized_value": 342_736_271_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "342,736,271천원",
                        },
                    },
                },
            },
        ]
        conflicting_doc = Document(
            page_content=(
                "구분 | 2023년 | 2022년\n"
                "연구개발비용 | 12,966,955 | 10,000,000\n"
                "자본화된 개발비 | 259,611 | 200,000"
            ),
            metadata={
                "company": "Example",
                "year": 2023,
                "report_type": "사업보고서",
                "section_path": "R&D",
                "table_source_id": "rd::detail",
                "table_context": "research and development detail",
                "table_header_context": "구분 | 2023년 | 2022년",
                "table_row_labels_text": "연구개발비용\n자본화된 개발비",
                "table_value_labels_text": (
                    "연구개발비용 12,966,955\n"
                    "연구개발비용 10,000,000\n"
                    "자본화된 개발비 259,611\n"
                    "자본화된 개발비 200,000"
                ),
                "unit_hint": "천원",
                "block_type": "table",
            },
        )
        state = {
            "query": "2023년 전체 연구개발비용 중 자본화된 개발비 비율을 계산해 줘.",
            "topic": "capitalized development cost ratio",
            "report_scope": {"year": 2023},
            "calc_subtasks": [
                {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "capitalized development cost ratio",
                    "operation_family": "ratio",
                    "depends_on": ["task_numerator", "task_denominator"],
                    "inputs": [
                        {
                            "role": "numerator_1",
                            "label": "2023년 자본화된 개발비",
                            "period": "2023",
                            "source_slot": "primary_value",
                            "source_preference": ["task_output", "retrieval"],
                            "preferred_task_id": "task_numerator",
                        },
                        {
                            "role": "denominator_1",
                            "label": "2023년 연구개발비용",
                            "period": "2023",
                            "source_slot": "primary_value",
                            "source_preference": ["task_output", "retrieval"],
                            "preferred_task_id": "task_denominator",
                        },
                    ],
                    "required_operands": [
                        {
                            "role": "numerator_1",
                            "label": "2023년 자본화된 개발비",
                            "period": "2023",
                        },
                        {
                            "role": "denominator_1",
                            "label": "2023년 연구개발비용",
                            "period": "2023",
                        },
                    ],
                },
                {"task_id": "task_numerator", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_denominator", "metric_family": "concept_lookup", "operation_family": "lookup"},
            ],
            "subtask_results": dependency_rows,
            "retrieved_docs": [(conflicting_doc, 0.1)],
            "seed_retrieved_docs": [],
        }

        prepared = self.agent._prepare_initial_aggregate_state(state)

        self.assertNotIn("2%", prepared.complete_numeric_answer)
        self.assertFalse(
            any(row.get("recovered_from_retrieved_ratio_context") for row in prepared.ordered_results)
        )
        self.assertNotIn("259,611천원", prepared.complete_numeric_answer)

    def test_retrieved_ratio_projection_preserves_complete_existing_result_without_metric_surface(self) -> None:
        metric_label = "목표값 대비 기준값 비율"
        existing_row = {
            "task_id": "task_ratio",
            "metric_family": "concept_ratio",
            "operation_family": "ratio",
            "status": "ok",
            "metric_label": metric_label,
            "answer": "목표값 대비 기준값 비율은 25.00%입니다.",
            "calculation_result": {
                "status": "ok",
                "operation_family": "ratio",
                "result_value": 25.0,
                "result_unit": "%",
                "rendered_value": "25.00%",
                "answer_slots": {
                    "metric_label": metric_label,
                    "operation_family": "ratio",
                    "primary_value": {
                        "status": "ok",
                        "role": "primary_value",
                        "label": metric_label,
                        "raw_value": "25.00%",
                        "raw_unit": "%",
                        "normalized_value": 25.0,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "25.00%",
                    },
                    "components_by_group": {
                        "numerator": [
                            self._ratio_component(
                                role="numerator_1",
                                label="목표값",
                                raw_value="250",
                                normalized_value=250.0,
                                source_row_id="ev_existing_num",
                            )
                        ],
                        "denominator": [
                            self._ratio_component(
                                role="denominator_1",
                                label="기준값",
                                raw_value="1,000",
                                normalized_value=1000.0,
                                source_row_id="ev_existing_den",
                            )
                        ],
                    },
                },
            },
        }
        context_rows = [
            {
                "operand_id": "ctx_num",
                "evidence_id": "ev_ctx_num",
                "source_row_id": "ev_ctx_num",
                "label": "목표값",
                "matched_operand_label": "목표값",
                "matched_operand_role": "numerator_1",
                "raw_value": "100",
                "raw_unit": "백만원",
                "normalized_value": 100.0,
                "normalized_unit": "KRW",
            },
            {
                "operand_id": "ctx_den",
                "evidence_id": "ev_ctx_den",
                "source_row_id": "ev_ctx_den",
                "label": "기준값",
                "matched_operand_label": "기준값",
                "matched_operand_role": "denominator_1",
                "raw_value": "1,000",
                "raw_unit": "백만원",
                "normalized_value": 1000.0,
                "normalized_unit": "KRW",
            },
        ]
        context_evidence = [
            {
                "evidence_id": "ev_ctx_num",
                "claim": "목표값 100",
                "metadata": {"table_value_labels_text": "목표값 100\n기준값 1,000"},
            },
            {
                "evidence_id": "ev_ctx_den",
                "claim": "기준값 1,000",
                "metadata": {"table_value_labels_text": "목표값 100\n기준값 1,000"},
            },
        ]
        original_context_docs = self.agent._retrieval_context_docs
        original_context_evidence = self.agent._ratio_operand_context_evidence_from_docs
        original_build_context = self.agent._build_complete_ratio_operands_from_coherent_context
        self.agent._retrieval_context_docs = lambda *_args, **_kwargs: ["context-doc"]
        self.agent._ratio_operand_context_evidence_from_docs = lambda *_args, **_kwargs: context_evidence
        self.agent._build_complete_ratio_operands_from_coherent_context = lambda *_args, **_kwargs: context_rows
        try:
            base_state = {
                    "query": "목표값 대비 기준값 비율을 계산해 줘.",
                    "topic": metric_label,
                    "calc_subtasks": [
                        {
                            "task_id": "task_ratio",
                            "metric_family": "concept_ratio",
                            "metric_label": metric_label,
                            "operation_family": "ratio",
                            "required_operands": [
                                {"role": "numerator_1", "label": "목표값"},
                                {"role": "denominator_1", "label": "기준값"},
                            ],
                        }
                    ],
                    "retrieved_docs": [],
                    "seed_retrieved_docs": [],
            }
            updated = self.agent._append_ratio_result_from_retrieved_context(
                [existing_row],
                base_state,
            )
            artifact_updated = self.agent._append_ratio_result_from_retrieved_context(
                [],
                {
                    **base_state,
                    "artifacts": [
                        {
                            "artifact_id": "result:task_ratio:001",
                            "task_id": "task_ratio",
                            "kind": "calculation_result",
                            "status": "ok",
                            "payload": {
                                "calculation_result": {
                                    "status": "ok",
                                    "operation_family": "ratio",
                                    "result_value": 25.0,
                                    "result_unit": "%",
                                    "rendered_value": "25.00%",
                                }
                            },
                            "evidence_refs": ["ev_existing_num", "ev_existing_den"],
                        }
                    ],
                },
            )
        finally:
            self.agent._retrieval_context_docs = original_context_docs
            self.agent._ratio_operand_context_evidence_from_docs = original_context_evidence
            self.agent._build_complete_ratio_operands_from_coherent_context = original_build_context

        self.assertEqual(len(updated), 1)
        self.assertFalse(updated[0].get("recovered_from_retrieved_ratio_context"))
        self.assertEqual(updated[0]["calculation_result"]["result_value"], 25.0)
        self.assertEqual(artifact_updated, [])
        preferred_artifact_row = self.agent._preferred_ratio_artifact_row_for_conflicting_recalculation(
            {
                "artifacts": [
                    {
                        "artifact_id": "result:task_ratio:001",
                        "task_id": "task_ratio",
                        "kind": "calculation_result",
                        "status": "ok",
                        "summary": "25.00%",
                        "payload": {
                            "calculation_result": {
                                "status": "ok",
                                "operation_family": "ratio",
                                "result_value": 25.0,
                                "result_unit": "%",
                                "rendered_value": "25.00%",
                            }
                        },
                    }
                ]
            },
            {"task_id": "task_ratio", "metric_family": "concept_ratio", "metric_label": metric_label},
            {"status": "ok", "operation_family": "ratio", "result_value": 10.0},
        )
        self.assertTrue(preferred_artifact_row.get("artifact_ratio_result_preserved_over_alignment"))
        self.assertEqual(preferred_artifact_row["calculation_result"]["result_value"], 25.0)

    def test_aggregate_final_answer_refreshes_after_late_lookup_slot_alignment(self) -> None:
        state = {
            "query": "Calculate the margin drag from a numerator over revenue.",
            "calc_subtasks": [
                {"task_id": "task_num", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_den", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_ratio", "metric_family": "concept_ratio", "operation_family": "ratio"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_num",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "answer": "target numerator 180 million",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 180_000_000.0,
                        "result_unit": "million",
                        "rendered_value": "180 million",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "numerator",
                                "label": "target numerator",
                                "concept": "target_numerator",
                                "raw_value": "180",
                                "raw_unit": "million",
                                "normalized_value": 180_000_000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "180 million",
                                "source_row_id": "row_num_total",
                                "source_row_ids": ["row_num_total"],
                                "value_role": "aggregate",
                                "aggregation_stage": "final",
                            },
                        },
                    },
                    "source_row_ids": ["row_num_total"],
                },
                {
                    "task_id": "task_den",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "answer": "target denominator 2,000 million",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 2_000_000_000.0,
                        "result_unit": "million",
                        "rendered_value": "2,000 million",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "denominator",
                                "label": "target denominator",
                                "concept": "target_denominator",
                                "raw_value": "2,000",
                                "raw_unit": "million",
                                "normalized_value": 2_000_000_000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "2,000 million",
                                "source_row_id": "row_den",
                                "source_row_ids": ["row_den"],
                            },
                        },
                    },
                    "source_row_ids": ["row_den"],
                },
                {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "margin drag",
                    "operation_family": "ratio",
                    "answer": "margin drag is 7.50%p.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 7.5,
                        "result_unit": "%p",
                        "rendered_value": "7.50%p",
                        "formatted_result": "margin drag is 7.50%p.",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "metric_label": "margin drag",
                            "components_by_role": {
                                "numerator": [
                                    {
                                        "status": "ok",
                                        "role": "numerator",
                                        "label": "target numerator",
                                        "concept": "target_numerator",
                                        "raw_value": "150",
                                        "raw_unit": "million",
                                        "normalized_value": 150_000_000.0,
                                        "normalized_unit": "KRW",
                                        "rendered_value": "150 million",
                                        "source_row_id": "row_num_detail",
                                    }
                                ],
                                "denominator": [
                                    {
                                        "status": "ok",
                                        "role": "denominator",
                                        "label": "target denominator",
                                        "concept": "target_denominator",
                                        "raw_value": "2,000",
                                        "raw_unit": "million",
                                        "normalized_value": 2_000_000_000.0,
                                        "normalized_unit": "KRW",
                                        "rendered_value": "2,000 million",
                                        "source_row_id": "row_den",
                                    }
                                ],
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "artifacts": [],
            "tasks": [],
        }
        self.agent.llm = None

        updated = self.agent._aggregate_calculation_subtasks(state)
        trace = _resolve_runtime_calculation_trace(updated)

        self.assertIn("9.00%p", updated["answer"])
        self.assertNotIn("7.50%p", updated["answer"])
        self.assertIn("9.00%p", trace["calculation_result"]["formatted_result"])
        ratio_row = next(row for row in updated["subtask_results"] if row["task_id"] == "task_ratio")
        self.assertTrue(ratio_row.get("aligned_from_source_task_slots"))

    def test_aggregate_final_answer_refreshes_after_own_evidence_unit_alignment(self) -> None:
        state = {
            "query": "Calculate the margin drag from a numerator over revenue.",
            "calc_subtasks": [
                {"task_id": "task_num", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_den", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_ratio", "metric_family": "concept_ratio", "operation_family": "ratio"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_num",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "answer": "target numerator 180 thousand",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "180천원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "numerator",
                                "label": "target numerator",
                                "concept": "target_numerator",
                                "raw_value": "180",
                                "raw_unit": "천원",
                                "normalized_value": 180_000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "180천원",
                                "source_row_id": "ev_num",
                                "source_row_ids": ["ev_num"],
                            },
                        },
                    },
                },
                {
                    "task_id": "task_den",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "answer": "target denominator 2,000,000 thousand",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "2,000,000천원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "denominator",
                                "label": "target denominator",
                                "concept": "target_denominator",
                                "raw_value": "2,000,000",
                                "raw_unit": "천원",
                                "normalized_value": 2_000_000_000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "2,000,000천원",
                                "source_row_id": "ev_den",
                                "source_row_ids": ["ev_den"],
                            },
                        },
                    },
                },
                {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "margin drag",
                    "operation_family": "ratio",
                    "answer": "margin drag is 0.01%p.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 0.009,
                        "result_unit": "%p",
                        "rendered_value": "0.01%p",
                        "formatted_result": "margin drag is 0.01%p.",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "metric_label": "margin drag",
                            "components_by_group": {
                                "numerator": [
                                    {
                                        "status": "ok",
                                        "role": "numerator",
                                        "label": "target numerator",
                                        "concept": "target_numerator",
                                        "raw_value": "180",
                                        "raw_unit": "천원",
                                        "normalized_value": 180_000.0,
                                        "normalized_unit": "KRW",
                                        "rendered_value": "180천원",
                                        "source_row_id": "task_output:task_num",
                                        "source_row_ids": ["task_output:task_num", "ev_num"],
                                    }
                                ],
                                "denominator": [
                                    {
                                        "status": "ok",
                                        "role": "denominator",
                                        "label": "target denominator",
                                        "concept": "target_denominator",
                                        "raw_value": "2,000,000",
                                        "raw_unit": "천원",
                                        "normalized_value": 2_000_000_000.0,
                                        "normalized_unit": "KRW",
                                        "rendered_value": "2,000,000천원",
                                        "source_row_id": "task_output:task_den",
                                        "source_row_ids": ["task_output:task_den", "ev_den"],
                                    }
                                ],
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "runtime_evidence": [
                {
                    "evidence_id": "ev_den",
                    "claim": "target denominator 2,000,000 (원)",
                    "quote_span": "2,000,000",
                    "metadata": {"unit_hint": "천원"},
                }
            ],
            "artifacts": [],
            "tasks": [],
        }
        self.agent.llm = None

        updated = self.agent._aggregate_calculation_subtasks(state)
        trace = _resolve_runtime_calculation_trace(updated)

        self.assertIn("9.00%p", updated["answer"])
        self.assertNotIn("0.01%p", updated["answer"])
        self.assertIn("9.00%p", trace["calculation_result"]["formatted_result"])
        denominator_row = next(row for row in updated["subtask_results"] if row["task_id"] == "task_den")
        denominator_slot = denominator_row["calculation_result"]["answer_slots"]["primary_value"]
        self.assertEqual(denominator_slot["raw_unit"], "원")
        ratio_row = next(row for row in updated["subtask_results"] if row["task_id"] == "task_ratio")
        self.assertTrue(ratio_row.get("aligned_from_source_task_slots"))

    def test_aggregate_compact_ratio_preserves_uncovered_lookup_item(self) -> None:
        state = {
            "query": "Extract the target and peer metrics, then calculate the target share of total.",
            "calc_subtasks": [
                {"task_id": "task_target", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_peer", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_total", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_ratio", "metric_family": "concept_ratio", "operation_family": "ratio"},
            ],
            "subtask_results": [
                self._lookup_result_row(
                    task_id="task_target",
                    metric_label="target metric",
                    label="target metric",
                    concept="operating_metric",
                    raw_value="120",
                    raw_unit="백만원",
                    normalized_value=120_000_000.0,
                    rendered_value="120백만원",
                    source_row_id="ev_segment",
                    source_anchor="shared source table",
                    answer="target metric 120백만원",
                ),
                self._lookup_result_row(
                    task_id="task_peer",
                    metric_label="peer metric",
                    label="peer metric",
                    concept="operating_metric",
                    raw_value="30",
                    raw_unit="천원",
                    normalized_value=30_000.0,
                    rendered_value="30천원",
                    source_row_id="ev_segment",
                    source_anchor="shared source table",
                    answer="peer metric 30천원",
                ),
                self._lookup_result_row(
                    task_id="task_total",
                    metric_label="total metric",
                    label="total metric",
                    concept="operating_metric_total",
                    raw_value="150",
                    raw_unit="백만원",
                    normalized_value=150_000_000.0,
                    rendered_value="150백만원",
                    source_row_id="ev_total",
                    source_anchor="total source table",
                    answer="total metric 150백만원",
                ),
                {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "target share",
                    "operation_family": "ratio",
                    "answer": "target share is 80.00%.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 80.0,
                        "result_unit": "%",
                        "rendered_value": "80.00%",
                        "formatted_result": "target share is 80.00%.",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "metric_label": "target share",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "rendered_value": "80.00%",
                                "normalized_value": 80.0,
                                "normalized_unit": "PERCENT",
                            },
                            "components_by_group": {
                                "numerator": [
                                    {
                                        "status": "ok",
                                        "role": "numerator",
                                        "label": "target metric",
                                        "concept": "operating_metric",
                                        "raw_value": "120",
                                        "raw_unit": "백만원",
                                        "normalized_value": 120_000_000.0,
                                        "normalized_unit": "KRW",
                                        "rendered_value": "120백만원",
                                        "source_row_id": "task_output:task_target",
                                        "source_row_ids": ["task_output:task_target", "ev_segment"],
                                    }
                                ],
                                "denominator": [
                                    {
                                        "status": "ok",
                                        "role": "denominator",
                                        "label": "total metric",
                                        "concept": "operating_metric_total",
                                        "raw_value": "150",
                                        "raw_unit": "백만원",
                                        "normalized_value": 150_000_000.0,
                                        "normalized_unit": "KRW",
                                        "rendered_value": "150백만원",
                                        "source_row_id": "task_output:task_total",
                                        "source_row_ids": ["task_output:task_total", "ev_total"],
                                    }
                                ],
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "artifacts": [],
            "tasks": [],
        }
        self.agent.llm = None

        updated = self.agent._aggregate_calculation_subtasks(state)
        trace = _resolve_runtime_calculation_trace(updated)

        self.assertIn("80%", updated["answer"])
        self.assertIn("peer metric 30백만원", updated["answer"])
        self.assertNotIn("30천원", updated["answer"])
        peer_row = next(row for row in updated["subtask_results"] if row["task_id"] == "task_peer")
        peer_slot = peer_row["calculation_result"]["answer_slots"]["primary_value"]
        self.assertTrue(peer_slot.get("unit_aligned_from_peer_source_slot"))
        self.assertEqual(trace["calculation_result"]["formatted_result"], updated["answer"])

    def test_uncovered_lookup_preservation_skips_label_already_reanswered_in_final(self) -> None:
        lookup_row = self._lookup_result_row(
            task_id="task_gain",
            metric_label="translation gain",
            label="translation gain",
            concept="translation_gain",
            raw_value="0",
            raw_unit="백만원",
            normalized_value=0.0,
            rendered_value="0백만원",
            source_row_id="ev_stale_gain",
            answer="translation gain 0백만원",
        )
        difference_row = {
            "task_id": "task_net",
            "metric_family": "concept_difference",
            "metric_label": "translation net effect",
            "operation_family": "difference",
            "answer": "translation gain was 5,739억원 and net effect was -3,322억원.",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "-3,322억원",
                "result_value": -332_200_000_000.0,
                "answer_slots": {
                    "operation_family": "difference",
                    "primary_value": {
                        "status": "ok",
                        "label": "translation net effect",
                        "rendered_value": "-3,322억원",
                        "normalized_value": -332_200_000_000.0,
                        "normalized_unit": "KRW",
                    },
                },
            },
        }

        answer = self.agent._append_uncovered_lookup_numeric_items(
            "translation gain was 5,739억원 and net effect was -3,322억원.",
            [lookup_row, difference_row],
        )

        self.assertNotIn("0백만원", answer)
        self.assertIn("5,739억원", answer)

    def test_aggregate_trace_sync_replaces_stale_single_ratio_subtask_surface(self) -> None:
        stale_ratio_row = {
            "task_id": "task_ratio",
            "metric_family": "concept_ratio",
            "metric_label": "target share",
            "operation_family": "ratio",
            "answer": "target share is 400.00%.",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "result_value": 400.0,
                "result_unit": "%",
                "rendered_value": "400.00%",
                "formatted_result": "target share is 400.00%.",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "target share",
                    "primary_value": {
                        "status": "ok",
                        "role": "primary_value",
                        "normalized_value": 400.0,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "400.00%",
                    },
                },
            },
        }
        final_answer = "target share is 80.00%."
        projection = {
            "calculation_plan": {
                "mode": "aggregate_subtasks",
                "subtasks": [{"task_id": "task_ratio", "calculation_plan": {"operation": "ratio"}}],
            },
            "calculation_result": {
                "status": "ok",
                "formatted_result": final_answer,
                "rendered_value": final_answer,
                "subtask_results": [stale_ratio_row],
                "answer_slots": {
                    "operation_family": "aggregate_subtasks",
                    "subtask_results": [
                        {
                            "task_id": "task_ratio",
                            "operation_family": "ratio",
                            "answer": "target share is 400.00%.",
                            "rendered_value": "400.00%",
                        }
                    ],
                },
            },
        }

        ordered_results, synced_projection = self.agent._sync_aggregate_arithmetic_subtask_surfaces(
            [stale_ratio_row],
            projection,
            final_answer,
        )

        ratio_row = next(row for row in ordered_results if row["task_id"] == "task_ratio")
        projected_ratio_row = next(
            row
            for row in synced_projection["calculation_result"]["subtask_results"]
            if row["task_id"] == "task_ratio"
        )
        slot_ratio_row = next(
            row
            for row in synced_projection["calculation_result"]["answer_slots"]["subtask_results"]
            if row["task_id"] == "task_ratio"
        )
        self.assertEqual(ratio_row["answer"], "target share is 80.00%.")
        self.assertEqual(projected_ratio_row["calculation_result"]["rendered_value"], "80.00%")
        self.assertEqual(slot_ratio_row["rendered_value"], "80.00%")
        self.assertNotIn("400.00%", projected_ratio_row["answer"])

    def test_aggregate_trace_sync_updates_difference_scalar_from_final_answer(self) -> None:
        stale_difference_row = {
            "task_id": "task_net",
            "metric_family": "concept_difference",
            "metric_label": "translation net effect",
            "operation_family": "difference",
            "answer": "-906,120백만원",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "result_value": -906_120_000_000.0,
                "result_unit": "백만원",
                "rendered_value": "-906,120백만원",
                "formatted_result": "-906,120백만원",
                "answer_slots": {
                    "operation_family": "difference",
                    "components_by_role": {
                        "minuend": [
                            {
                                "status": "ok",
                                "role": "minuend",
                                "label": "translation gain",
                                "raw_value": "0",
                                "raw_unit": "백만원",
                                "normalized_value": 0.0,
                                "normalized_unit": "KRW",
                            }
                        ],
                        "subtrahend": [
                            {
                                "status": "ok",
                                "role": "subtrahend",
                                "label": "translation loss",
                                "raw_value": "906,120",
                                "raw_unit": "백만원",
                                "normalized_value": 906_120_000_000.0,
                                "normalized_unit": "KRW",
                            }
                        ],
                    },
                },
            },
        }
        final_answer = (
            "translation gain was 5,739억원, translation loss was 9,061억원, "
            "and translation net effect was -3,322억원."
        )
        projection = {
            "calculation_plan": {
                "mode": "aggregate_subtasks",
                "subtasks": [{"task_id": "task_net", "calculation_plan": {"operation": "subtract"}}],
            },
            "calculation_result": {
                "status": "ok",
                "formatted_result": final_answer,
                "rendered_value": final_answer,
                "subtask_results": [stale_difference_row],
                "answer_slots": {
                    "operation_family": "aggregate_subtasks",
                    "subtask_results": [
                        {
                            "task_id": "task_net",
                            "operation_family": "difference",
                            "answer": "-906,120백만원",
                            "rendered_value": "-906,120백만원",
                        }
                    ],
                },
            },
        }

        ordered_results, synced_projection = self.agent._sync_aggregate_arithmetic_subtask_surfaces(
            [stale_difference_row],
            projection,
            final_answer,
        )

        synced_row = next(row for row in ordered_results if row["task_id"] == "task_net")
        projected_row = next(
            row
            for row in synced_projection["calculation_result"]["subtask_results"]
            if row["task_id"] == "task_net"
        )
        self.assertEqual(synced_row["calculation_result"]["rendered_value"], "-3,322억원")
        self.assertEqual(synced_row["calculation_result"]["result_value"], -332_200_000_000.0)
        self.assertEqual(
            synced_row["calculation_result"]["answer_slots"]["primary_value"]["rendered_value"],
            "-3,322억원",
        )
        self.assertEqual(projected_row["calculation_result"]["result_value"], -332_200_000_000.0)

    def test_dedupe_prefers_ratio_candidate_coherent_with_source_task_scope(self) -> None:
        source_lookup = {
            "task_id": "task_num",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "primary_value": {
                        "status": "ok",
                        "label": "target numerator",
                        "raw_value": "120",
                        "raw_unit": "unit",
                        "normalized_value": 120.0,
                        "normalized_unit": "COUNT",
                        "rendered_value": "120unit",
                        "source_row_id": "ev_num",
                        "consolidation_scope": "consolidated",
                    }
                },
            },
        }
        coherent_ratio = {
            "task_id": "task_ratio",
            "metric_family": "concept_ratio",
            "metric_label": "target share",
            "operation_family": "ratio",
            "answer": "target share is 80.00%.",
            "status": "ok",
            "calculation_operands": [
                {
                    "operand_id": "num",
                    "label": "target numerator",
                    "matched_operand_role": "numerator_1",
                    "raw_value": "120",
                    "raw_unit": "unit",
                    "normalized_value": 120.0,
                    "normalized_unit": "COUNT",
                    "source_task_id": "task_num",
                    "source_row_id": "task_output:task_num",
                    "consolidation_scope": "consolidated",
                },
                {
                    "operand_id": "den",
                    "label": "target denominator",
                    "matched_operand_role": "denominator_1",
                    "raw_value": "150",
                    "raw_unit": "unit",
                    "normalized_value": 150.0,
                    "normalized_unit": "COUNT",
                },
            ],
            "calculation_result": {
                "status": "ok",
                "rendered_value": "80.00%",
                "formatted_result": "target share is 80.00%.",
                "source_row_ids": ["task_output:task_num", "ev_den"],
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "target share",
                    "primary_value": {"status": "ok", "rendered_value": "80.00%", "normalized_value": 80.0},
                },
            },
        }
        conflicting_ratio = {
            **dict(coherent_ratio),
            "answer": "target share is 46.67%.",
            "calculation_operands": [
                {
                    **dict(coherent_ratio["calculation_operands"][0]),
                    "raw_value": "70",
                    "normalized_value": 70.0,
                    "source_row_id": "ev_separate",
                    "source_row_ids": ["ev_separate"],
                    "consolidation_scope": "separate",
                    "sibling_table_context_realigned": True,
                },
                dict(coherent_ratio["calculation_operands"][1]),
            ],
            "calculation_result": {
                **dict(coherent_ratio["calculation_result"]),
                "rendered_value": "46.67%",
                "formatted_result": "target share is 46.67%.",
                "source_row_ids": ["ev_separate", "ev_den"],
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "target share",
                    "primary_value": {"status": "ok", "rendered_value": "46.67%", "normalized_value": 46.67},
                },
            },
        }

        deduped = self.agent._dedupe_aggregate_subtask_results([source_lookup, coherent_ratio, conflicting_ratio])

        ratio_row = next(row for row in deduped if row.get("task_id") == "task_ratio")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "80.00%")
        self.assertEqual(ratio_row["calculation_operands"][0]["consolidation_scope"], "consolidated")

    def test_collapsed_ratio_runtime_override_rejects_dependency_incoherent_trace(self) -> None:
        source_lookup = {
            "task_id": "task_num",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "primary_value": {
                        "status": "ok",
                        "label": "target numerator",
                        "raw_value": "120",
                        "raw_unit": "unit",
                        "normalized_value": 120.0,
                        "normalized_unit": "COUNT",
                        "rendered_value": "120unit",
                        "source_row_id": "ev_same",
                        "source_row_ids": ["ev_same"],
                        "source_anchor": "source A",
                    }
                },
            },
        }
        coherent_ratio = {
            "task_id": "task_ratio",
            "metric_family": "concept_ratio",
            "metric_label": "target share",
            "operation_family": "ratio",
            "answer": "target share is 80%.",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "80%",
                "formatted_result": "target share is 80%.",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "target share",
                    "primary_value": {"status": "ok", "rendered_value": "80%", "normalized_value": 80.0},
                },
            },
        }
        collapsed_ratio = {
            "task_id": "task_collapsed",
            "metric_family": "concept_ratio",
            "metric_label": "invalid self ratio",
            "operation_family": "ratio",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "operation_family": "ratio",
                    "components_by_group": {
                        "numerator": [
                            {
                                "status": "ok",
                                "label": "same",
                                "raw_value": "1",
                                "raw_unit": "unit",
                                "normalized_value": 1.0,
                                "source_row_id": "ev_same",
                            }
                        ],
                        "denominator": [
                            {
                                "status": "ok",
                                "label": "same",
                                "raw_value": "1",
                                "raw_unit": "unit",
                                "normalized_value": 1.0,
                                "source_row_id": "ev_same",
                            }
                        ],
                    },
                },
            },
        }
        aggregate_projection = self.agent._rebuild_aggregate_projection(
            [source_lookup, coherent_ratio, collapsed_ratio],
            "target share is 80%.",
        )
        stale_state = {
            "query": "target share",
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "matched_operand_role": "numerator_1",
                        "label": "target numerator",
                        "raw_value": "70",
                        "raw_unit": "unit",
                        "normalized_value": 70.0,
                        "normalized_unit": "COUNT",
                        "source_task_id": "task_num",
                        "source_row_id": "ev_same",
                        "source_row_ids": ["ev_same"],
                        "source_anchor": "source B",
                    },
                    {
                        "operand_id": "den",
                        "matched_operand_role": "denominator_1",
                        "label": "target denominator",
                        "raw_value": "150",
                        "raw_unit": "unit",
                        "normalized_value": 150.0,
                        "normalized_unit": "COUNT",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["num", "den"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "num"},
                        {"variable": "B", "operand_id": "den"},
                    ],
                    "formula": "(A / B) * 100",
                    "result_unit": "%",
                },
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "46.67%",
                    "formatted_result": "target share is 46.67%.",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "metric_label": "target share",
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "label": "target numerator",
                                    "raw_value": "70",
                                    "raw_unit": "unit",
                                    "normalized_value": 70.0,
                                    "source_task_id": "task_num",
                                    "source_row_id": "ev_same",
                                    "source_anchor": "source B",
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "label": "target denominator",
                                    "raw_value": "150",
                                    "raw_unit": "unit",
                                    "normalized_value": 150.0,
                                }
                            ],
                        },
                    },
                },
            },
        }

        projection, answer = self.agent._apply_runtime_ratio_projection_for_collapsed_rows(
            stale_state,
            aggregate_projection,
            [source_lookup, coherent_ratio, collapsed_ratio],
            "target share is 80%.",
        )

        self.assertEqual(answer, "target share is 80%.")
        self.assertEqual(projection["calculation_result"]["formatted_result"], "target share is 80%.")

    def test_stale_projection_repair_rejects_dependency_incoherent_operands(self) -> None:
        source_lookup = {
            "task_id": "task_num",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "primary_value": {
                        "status": "ok",
                        "label": "target numerator",
                        "raw_value": "120",
                        "raw_unit": "unit",
                        "normalized_value": 120.0,
                        "normalized_unit": "COUNT",
                        "rendered_value": "120unit",
                        "source_row_id": "ev_same",
                        "source_row_ids": ["ev_same"],
                        "source_anchor": "source A",
                    }
                },
            },
        }
        coherent_ratio = {
            "task_id": "task_ratio",
            "metric_family": "concept_ratio",
            "operation_family": "ratio",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "formatted_result": "target share is 80%.",
                "rendered_value": "80%",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "target share",
                    "primary_value": {"status": "ok", "rendered_value": "80%", "normalized_value": 80.0},
                },
            },
        }
        stale_projection = {
            "calculation_operands": [
                {
                    "operand_id": "num",
                    "matched_operand_role": "numerator_1",
                    "label": "target numerator",
                    "raw_value": "70",
                    "raw_unit": "unit",
                    "normalized_value": 70.0,
                    "normalized_unit": "COUNT",
                    "source_task_id": "task_num",
                    "source_row_id": "ev_same",
                    "source_row_ids": ["ev_same"],
                    "source_anchor": "source B",
                },
                {
                    "operand_id": "den",
                    "matched_operand_role": "denominator_1",
                    "label": "target denominator",
                    "raw_value": "150",
                    "raw_unit": "unit",
                    "normalized_value": 150.0,
                    "normalized_unit": "COUNT",
                },
            ],
            "calculation_plan": {
                "status": "ok",
                "mode": "single_value",
                "operation": "ratio",
                "ordered_operand_ids": ["num", "den"],
                "variable_bindings": [
                    {"variable": "A", "operand_id": "num"},
                    {"variable": "B", "operand_id": "den"},
                ],
                "formula": "(A / B) * 100",
                "result_unit": "%",
            },
            "calculation_result": {
                "status": "ok",
                "result_value": 80.0,
                "result_unit": "%",
                "rendered_value": "80%",
                "formatted_result": "target share is 80%.",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "target share",
                    "primary_value": {"status": "ok", "rendered_value": "80%", "normalized_value": 80.0},
                    "components_by_group": {
                        "numerator": [
                            {
                                "status": "ok",
                                "label": "target numerator",
                                "raw_value": "70",
                                "raw_unit": "unit",
                                "normalized_value": 70.0,
                                "normalized_unit": "COUNT",
                                "source_task_id": "task_num",
                                "source_row_id": "ev_same",
                                "source_anchor": "source B",
                            }
                        ],
                        "denominator": [
                            {
                                "status": "ok",
                                "label": "target denominator",
                                "raw_value": "150",
                                "raw_unit": "unit",
                                "normalized_value": 150.0,
                                "normalized_unit": "COUNT",
                            }
                        ],
                    },
                },
            },
        }
        aggregate_state = _AggregateSynthesisState(
            [source_lookup, coherent_ratio],
            stale_projection,
            "target share is 80%.",
            [],
        )

        repaired = self.agent._apply_stale_projection_repair_to_aggregate_state(
            state={"query": "target share"},
            aggregate_state=aggregate_state,
            evidence_items=[],
            prefer_compact_ratio_answer=True,
        )

        self.assertEqual(repaired.final_answer, "target share is 80%.")
        self.assertEqual(repaired.aggregate_projection["calculation_result"]["formatted_result"], "target share is 80%.")

    def test_stale_projection_repair_preserves_complete_multi_operand_ratio_answer(self) -> None:
        ratio_result = {
            "status": "ok",
            "result_value": 42.02,
            "result_unit": "%",
            "rendered_value": "42.02%",
            "formatted_result": "target share is 42.02%.",
            "answer_slots": {
                "operation_family": "ratio",
                "metric_label": "target share",
                "primary_value": {
                    "status": "ok",
                    "rendered_value": "42.02%",
                    "normalized_value": 42.02,
                    "normalized_unit": "PERCENT",
                },
                "components_by_group": {
                    "numerator": [
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "short component",
                            "raw_value": "4,146",
                            "raw_unit": "백만원",
                            "normalized_value": 4146000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "4,146백만원",
                            "source_row_id": "ev_short",
                        },
                        {
                            "status": "ok",
                            "role": "numerator_2",
                            "label": "long component",
                            "raw_value": "10,121",
                            "raw_unit": "백만원",
                            "normalized_value": 10121000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "10,121백만원",
                            "source_row_id": "ev_long",
                        },
                        {
                            "status": "ok",
                            "role": "numerator_3",
                            "label": "bond component",
                            "raw_value": "9,490",
                            "raw_unit": "백만원",
                            "normalized_value": 9490000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "9,490백만원",
                            "source_row_id": "ev_bond",
                        },
                    ],
                    "denominator": [
                        {
                            "status": "ok",
                            "role": "denominator_1",
                            "label": "tangible base",
                            "raw_value": "52,705",
                            "raw_unit": "백만원",
                            "normalized_value": 52705000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "52,705백만원",
                            "source_row_id": "ev_tangible",
                        },
                        {
                            "status": "ok",
                            "role": "denominator_2",
                            "label": "intangible base",
                            "raw_value": "3,835",
                            "raw_unit": "백만원",
                            "normalized_value": 3835000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,835백만원",
                            "source_row_id": "ev_intangible",
                        },
                    ],
                },
            },
        }
        ratio_row = {
            "task_id": "task_ratio",
            "metric_family": "concept_ratio",
            "metric_label": "target share",
            "operation_family": "ratio",
            "answer": "target share is 42.02%.",
            "status": "ok",
            "calculation_result": ratio_result,
            "calculation_operands": [
                slot
                for slots in ratio_result["answer_slots"]["components_by_group"].values()
                for slot in slots
            ],
        }
        stale_projection = {
            "calculation_operands": [
                {
                    "operand_id": "num",
                    "matched_operand_role": "numerator_1",
                    "label": "short component",
                    "raw_value": "4,146",
                    "raw_unit": "백만원",
                    "normalized_value": 4146000000.0,
                    "normalized_unit": "KRW",
                    "source_row_id": "ev_short",
                },
                {
                    "operand_id": "den",
                    "matched_operand_role": "denominator_1",
                    "label": "tangible base",
                    "raw_value": "52,705",
                    "raw_unit": "백만원",
                    "normalized_value": 52705000000.0,
                    "normalized_unit": "KRW",
                    "source_row_id": "ev_tangible",
                },
            ],
            "calculation_plan": {
                "status": "ok",
                "mode": "single_value",
                "operation": "ratio",
                "ordered_operand_ids": ["num", "den"],
                "variable_bindings": [
                    {"variable": "A", "operand_id": "num"},
                    {"variable": "B", "operand_id": "den"},
                ],
                "formula": "(A / B) * 100",
                "result_unit": "%",
            },
            "calculation_result": {
                "status": "ok",
                "result_value": 42.02,
                "result_unit": "%",
                "rendered_value": "42.02%",
                "formatted_result": "target share is 42.02%.",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "target share",
                    "primary_value": {"status": "ok", "rendered_value": "42.02%", "normalized_value": 42.02},
                },
            },
        }
        aggregate_state = _AggregateSynthesisState(
            [ratio_row],
            stale_projection,
            "target share is 42.02%.",
            [],
        )

        repaired = self.agent._apply_stale_projection_repair_to_aggregate_state(
            state={"query": "calculate target borrowing share"},
            aggregate_state=aggregate_state,
            evidence_items=[],
            prefer_compact_ratio_answer=True,
        )

        self.assertIn("42.02%", repaired.final_answer)
        self.assertNotIn("7.87%", repaired.final_answer)
        self.assertIn("42.02%", repaired.aggregate_projection["calculation_result"]["formatted_result"])

    def test_late_runtime_numeric_answer_rejects_dependency_incoherent_trace(self) -> None:
        source_lookup = {
            "task_id": "task_num",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "primary_value": {
                        "status": "ok",
                        "label": "target numerator",
                        "raw_value": "120",
                        "raw_unit": "unit",
                        "normalized_value": 120.0,
                        "normalized_unit": "COUNT",
                        "rendered_value": "120unit",
                        "source_row_id": "ev_same",
                        "source_row_ids": ["ev_same"],
                        "source_anchor": "source A",
                    }
                },
            },
        }
        state = {
            "query": "target share",
            "subtask_results": [source_lookup],
            "active_subtask": {"metric_label": "target share", "operation_family": "ratio"},
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "matched_operand_role": "numerator_1",
                        "label": "target numerator",
                        "raw_value": "70",
                        "raw_unit": "unit",
                        "normalized_value": 70.0,
                        "normalized_unit": "COUNT",
                        "source_task_id": "task_num",
                        "source_row_id": "ev_same",
                        "source_row_ids": ["ev_same"],
                        "source_anchor": "source B",
                    },
                    {
                        "operand_id": "den",
                        "matched_operand_role": "denominator_1",
                        "label": "target denominator",
                        "raw_value": "150",
                        "raw_unit": "unit",
                        "normalized_value": 150.0,
                        "normalized_unit": "COUNT",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["num", "den"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "num"},
                        {"variable": "B", "operand_id": "den"},
                    ],
                    "formula": "(A / B) * 100",
                    "result_unit": "%",
                },
                "calculation_result": {
                    "status": "ok",
                    "result_value": 46.6666666667,
                    "result_unit": "%",
                    "rendered_value": "46.67%",
                    "formatted_result": "target share is 46.67%.",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "metric_label": "target share",
                        "primary_value": {"status": "ok", "rendered_value": "46.67%", "normalized_value": 46.6666666667},
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "target numerator",
                                    "raw_value": "70",
                                    "raw_unit": "unit",
                                    "normalized_value": 70.0,
                                    "normalized_unit": "COUNT",
                                    "source_task_id": "task_num",
                                    "source_row_id": "ev_same",
                                    "source_anchor": "source B",
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "role": "denominator_1",
                                    "label": "target denominator",
                                    "raw_value": "150",
                                    "raw_unit": "unit",
                                    "normalized_value": 150.0,
                                    "normalized_unit": "COUNT",
                                }
                            ],
                        },
                    },
                },
            },
        }

        answer = self.agent._late_runtime_numeric_answer(state, "target share is 80%.")

        self.assertEqual(answer, "")

    def test_late_runtime_numeric_answer_accepts_structured_unit_realigned_dependency_trace(self) -> None:
        source_lookup = {
            "task_id": "task_den",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "primary_value": {
                        "status": "ok",
                        "label": "target denominator",
                        "raw_value": "100",
                        "raw_unit": "천원",
                        "normalized_value": 100000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "100천원",
                        "source_row_id": "ev_den",
                        "source_row_ids": ["ev_den"],
                        "source_anchor": "stale source projection",
                    }
                },
            },
        }
        state = {
            "query": "target coverage ratio",
            "subtask_results": [source_lookup],
            "active_subtask": {"metric_label": "target coverage", "operation_family": "ratio"},
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "matched_operand_role": "numerator_1",
                        "label": "target numerator",
                        "raw_value": "200",
                        "raw_unit": "백만원",
                        "normalized_value": 200000000.0,
                        "normalized_unit": "KRW",
                    },
                    {
                        "operand_id": "den",
                        "matched_operand_role": "denominator_1",
                        "label": "target denominator",
                        "raw_value": "100",
                        "raw_unit": "백만원",
                        "normalized_value": 100000000.0,
                        "normalized_unit": "KRW",
                        "source_task_id": "task_den",
                        "source_row_id": "task_output:task_den",
                        "source_row_ids": ["task_output:task_den", "ev_den", "graph_node_1"],
                        "source_anchor": "structured graph provenance",
                        "unit_realigned_from_structured_provenance": True,
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["num", "den"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "num"},
                        {"variable": "B", "operand_id": "den"},
                    ],
                    "formula": "A / B",
                    "result_unit": "배",
                },
                "calculation_result": {
                    "status": "ok",
                    "result_value": 2.0,
                    "result_unit": "배",
                    "rendered_value": "2배",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "metric_label": "target coverage",
                        "primary_value": {"status": "ok", "rendered_value": "2배", "normalized_value": 2.0},
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "target numerator",
                                    "raw_value": "200",
                                    "raw_unit": "백만원",
                                    "normalized_value": 200000000.0,
                                    "normalized_unit": "KRW",
                                    "rendered_value": "200백만원",
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "role": "denominator_1",
                                    "label": "target denominator",
                                    "raw_value": "100",
                                    "raw_unit": "백만원",
                                    "normalized_value": 100000000.0,
                                    "normalized_unit": "KRW",
                                    "rendered_value": "100백만원",
                                    "source_task_id": "task_den",
                                    "source_row_id": "task_output:task_den",
                                    "source_row_ids": ["task_output:task_den", "ev_den", "graph_node_1"],
                                    "source_anchor": "structured graph provenance",
                                    "unit_realigned_from_structured_provenance": True,
                                }
                            ],
                        },
                    },
                },
            },
        }

        answer = self.agent._late_runtime_numeric_answer(state, "target coverage is 0.002배.")

        self.assertIn("2배", answer)
        self.assertIn("200백만원", answer)
        self.assertIn("100백만원", answer)

    def test_lookup_recovery_keeps_requested_scope_evidence_over_unknown_scope_structured_row(self) -> None:
        current_row = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "metric_label": "target operating result",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "350백만원",
                "answer_slots": {
                    "primary_value": {
                        "status": "ok",
                        "role": "numerator_1",
                        "label": "target operating result",
                        "concept": "operating_income",
                        "raw_value": "350",
                        "raw_unit": "백만원",
                        "normalized_value": 350000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "350백만원",
                        "source_row_id": "ev_current",
                        "source_row_ids": ["ev_current"],
                        "source_anchor": "consolidated note",
                        "consolidation_scope": "consolidated",
                    }
                },
            },
        }
        state = {
            "query": "2023년 연결 기준 coverage ratio",
            "report_scope": {"consolidation": "consolidated"},
            "calc_subtasks": [
                {
                    "task_id": "task_lookup",
                    "operation_family": "lookup",
                    "metric_family": "concept_lookup",
                    "required_operands": [
                        {
                            "role": "numerator_1",
                            "label": "target operating result",
                            "concept": "operating_income",
                            "required": True,
                            "binding_policy": {"prefer_consolidation_scope": "consolidated"},
                        }
                    ],
                }
            ],
            "runtime_evidence": [
                {
                    "evidence_id": "ev_current",
                    "source_anchor": "consolidated note",
                    "claim": "target operating result 350 백만원",
                    "quote_span": "350 백만원",
                    "metadata": {
                        "consolidation_scope": "consolidated",
                        "statement_type": "notes",
                        "unit_hint": "백만원",
                    },
                },
                {
                    "evidence_id": "ev_unknown",
                    "source_anchor": "management discussion",
                    "claim": "target operating result 230 백만원",
                    "quote_span": "target operating result 230 백만원",
                    "metadata": {
                        "consolidation_scope": "unknown",
                        "statement_type": "mda",
                        "unit_hint": "백만원",
                        "table_source_id": "mda_table",
                        "table_value_labels_text": "target operating result 230",
                        "row_label": "target operating result",
                        "semantic_label": "target operating result",
                        "structured_cells": [{"value_text": "230", "unit_hint": "백만원"}],
                    },
                },
            ],
        }

        recovered = self.agent._recover_lookup_results_from_sibling_table_evidence([current_row], state)

        primary = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]
        self.assertEqual(primary["raw_value"], "350")
        self.assertEqual(primary["source_row_id"], "ev_current")

    def test_structured_subtask_projection_matches_public_answer(self) -> None:
        state = {
            "answer": "target coverage is 3.5배.",
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {"matched_operand_role": "numerator_1", "raw_value": "100", "raw_unit": "unit"},
                    {"matched_operand_role": "denominator_1", "raw_value": "20", "raw_unit": "unit"},
                ],
                "calculation_plan": {"operation": "ratio"},
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "5배",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {"rendered_value": "5배"},
                    },
                },
            },
            "structured_result": {
                "formatted_result": "target coverage is 3.5배.",
                "subtask_results": [
                    {
                        "task_id": "task_ratio",
                        "metric_family": "concept_ratio",
                        "operation_family": "ratio",
                        "answer": "target coverage is 3.5배.",
                        "status": "ok",
                        "calculation_result": {
                            "status": "ok",
                            "rendered_value": "3.5배",
                            "formatted_result": "target coverage is 3.5배.",
                            "answer_slots": {
                                "operation_family": "ratio",
                                "metric_label": "target coverage",
                                "primary_value": {"status": "ok", "rendered_value": "3.5배"},
                                "components_by_group": {
                                    "numerator": [
                                        {
                                            "status": "ok",
                                            "role": "numerator_1",
                                            "label": "target numerator",
                                            "raw_value": "350",
                                            "raw_unit": "unit",
                                            "normalized_value": 350.0,
                                            "normalized_unit": "COUNT",
                                            "rendered_value": "350unit",
                                        }
                                    ],
                                    "denominator": [
                                        {
                                            "status": "ok",
                                            "role": "denominator_1",
                                            "label": "target denominator",
                                            "raw_value": "100",
                                            "raw_unit": "unit",
                                            "normalized_value": 100.0,
                                            "normalized_unit": "COUNT",
                                            "rendered_value": "100unit",
                                        }
                                    ],
                                },
                            },
                        },
                    }
                ],
            },
        }

        trace = self.agent._structured_subtask_projection_for_public_answer(
            state,
            state["resolved_calculation_trace"],
        )

        self.assertEqual(trace["calculation_plan"]["mode"], "aggregate_subtasks")
        self.assertEqual(trace["calculation_result"]["formatted_result"], "target coverage is 3.5배.")
        self.assertEqual(
            trace["calculation_result"]["subtask_results"][0]["calculation_result"]["rendered_value"],
            "3.5배",
        )

    def test_dependency_recalculation_ignores_legacy_top_level_result(self) -> None:
        original_execute = self.agent._execute_calculation
        calls = []

        def _legacy_only_execute(state):
            calls.append(state)
            return {
                "calculation_operands": list(state.get("calculation_operands") or []),
                "calculation_plan": dict(state.get("calculation_plan") or {}),
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "999%",
                    "formatted_result": "legacy top-level result",
                },
            }

        self.agent._execute_calculation = _legacy_only_execute
        try:
            ordered = [
                {
                    "task_id": "task_numerator",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "selling expense",
                                "raw_value": "4,355",
                                "raw_unit": "hundred million",
                                "normalized_value": 435_500_000_000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "4,355 hundred million",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_denominator",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "pre-expense profit",
                                "raw_value": "11,623",
                                "raw_unit": "hundred million",
                                "normalized_value": 1_162_300_000_000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "11,623 hundred million",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "operation_family": "ratio",
                    "answer": "CIR is 0.04%.",
                    "status": "ok",
                    "calculation_operands": [
                        {
                            "operand_id": "op_001",
                            "label": "selling expense",
                            "raw_value": "4,355",
                            "raw_unit": "hundred million",
                            "normalized_value": 4_355_000_000.0,
                            "normalized_unit": "KRW",
                            "matched_operand_role": "numerator_1",
                            "source_task_id": "task_numerator",
                        },
                        {
                            "operand_id": "op_002",
                            "label": "pre-expense profit",
                            "raw_value": "11,623",
                            "raw_unit": "hundred million",
                            "normalized_value": 1_162_300_000_000.0,
                            "normalized_unit": "KRW",
                            "matched_operand_role": "denominator_1",
                            "source_task_id": "task_denominator",
                        },
                    ],
                    "calculation_plan": {
                        "status": "ok",
                        "mode": "single_value",
                        "operation": "ratio",
                        "ordered_operand_ids": ["op_001", "op_002"],
                        "variable_bindings": [
                            {"variable": "A", "operand_id": "op_001"},
                            {"variable": "B", "operand_id": "op_002"},
                        ],
                        "formula": "(A / B) * 100",
                        "result_unit": "%",
                    },
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "0.04%",
                        "formatted_result": "CIR is 0.04%.",
                        "answer_slots": {"operation_family": "ratio"},
                    },
                },
            ]
            state = {
                "query": "Calculate 2023 CIR.",
                "calc_subtasks": [
                    {"task_id": "task_numerator", "metric_family": "concept_lookup", "operation_family": "lookup"},
                    {"task_id": "task_denominator", "metric_family": "concept_lookup", "operation_family": "lookup"},
                    {"task_id": "task_ratio", "metric_family": "concept_ratio", "operation_family": "ratio"},
                ],
            }
            projection = {
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "source_row_ids": ["task_output:task_numerator"],
                    },
                    {
                        "operand_id": "op_002",
                        "source_row_ids": ["task_output:task_denominator"],
                    },
                ],
            }

            aligned = self.agent._align_lookup_results_with_dependency_projection(ordered, state, projection)
        finally:
            self.agent._execute_calculation = original_execute

        ratio_row = aligned[-1]
        self.assertTrue(calls)
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "0.04%")
        self.assertNotEqual(ratio_row.get("answer"), "legacy top-level result")
        self.assertNotIn("aligned_from_source_task_slots", ratio_row)

    def test_ratio_recalculation_binds_lookup_slots_by_prefixed_roles(self) -> None:
        lookup_numerator = {
            "task_id": "task_numerator",
            "metric_family": "concept_lookup",
            "metric_label": "operating profit",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {
                        "status": "ok",
                        "role": "numerator_1",
                        "label": "operating profit",
                        "concept": "operating_profit",
                        "period": "2023",
                        "raw_value": "3,531,422,506,439",
                        "raw_unit": "won",
                        "normalized_value": 3_531_422_506_439.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "3,531,422,506,439won",
                        "source_row_id": "ev_numerator",
                    },
                },
            },
        }
        lookup_denominator = {
            "task_id": "task_denominator",
            "metric_family": "concept_lookup",
            "metric_label": "interest expense",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {
                        "status": "ok",
                        "role": "denominator_1",
                        "label": "interest expense",
                        "concept": "interest_expense",
                        "period": "2023",
                        "raw_value": "1,001,290",
                        "raw_unit": "백만원",
                        "normalized_value": 1_001_290_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "1,001,290백만원",
                        "source_row_id": "ev_denominator",
                    },
                },
            },
        }
        stale_ratio = {
            "task_id": "task_ratio",
            "metric_family": "concept_ratio",
            "metric_label": "coverage ratio",
            "operation_family": "ratio",
            "status": "ok",
            "calculation_plan": {
                "status": "ok",
                "mode": "single_value",
                "operation": "ratio",
                "formula": "A / B",
                "result_unit": "배",
                "ordered_operand_ids": ["numerator", "denominator"],
                "variable_bindings": [
                    {"variable": "A", "operand_id": "numerator"},
                    {"variable": "B", "operand_id": "denominator"},
                ],
            },
            "calculation_operands": [
                {
                    "operand_id": "numerator",
                    "label": "operating profit",
                    "matched_operand_label": "operating profit",
                    "matched_operand_concept": "operating_profit",
                    "matched_operand_role": "numerator_1",
                    "raw_value": "3,531,422,506,439",
                    "raw_unit": "won",
                    "normalized_value": 3_531_422_506_439.0,
                    "normalized_unit": "KRW",
                    "source_row_id": "ev_numerator",
                },
                {
                    "operand_id": "denominator",
                    "label": "interest expense",
                    "matched_operand_label": "interest expense",
                    "matched_operand_concept": "interest_expense",
                    "matched_operand_role": "denominator_1",
                    "raw_value": "1,180,096",
                    "raw_unit": "백만원",
                    "normalized_value": 1_180_096_000_000.0,
                    "normalized_unit": "KRW",
                    "source_row_id": "ev_stale_denominator",
                },
            ],
            "calculation_result": {
                "status": "ok",
                "result_value": 2.9924874810515414,
                "result_unit": "배",
                "rendered_value": "2.9925배",
                "formatted_result": "coverage ratio is 2.9925배.",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "coverage ratio",
                    "components_by_role": {
                        "numerator_1": [
                            {
                                "status": "ok",
                                "role": "numerator_1",
                                "label": "operating profit",
                                "concept": "operating_profit",
                                "period": "2023",
                                "raw_value": "3,531,422,506,439",
                                "raw_unit": "won",
                                "normalized_value": 3_531_422_506_439.0,
                                "normalized_unit": "KRW",
                                "source_row_id": "ev_numerator",
                            }
                        ],
                        "denominator_1": [
                            {
                                "status": "ok",
                                "role": "denominator_1",
                                "label": "interest expense",
                                "concept": "interest_expense",
                                "period": "2023",
                                "raw_value": "1,180,096",
                                "raw_unit": "백만원",
                                "normalized_value": 1_180_096_000_000.0,
                                "normalized_unit": "KRW",
                                "source_row_id": "ev_stale_denominator",
                            }
                        ],
                    },
                },
            },
        }

        aligned = self.agent._align_lookup_results_with_dependency_projection(
            [lookup_numerator, lookup_denominator, stale_ratio],
            {
                "query": "calculate coverage ratio",
                "calc_subtasks": [
                    {"task_id": "task_numerator", "operation_family": "lookup"},
                    {"task_id": "task_denominator", "operation_family": "lookup"},
                    {"task_id": "task_ratio", "operation_family": "ratio", "metric_label": "coverage ratio"},
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = aligned[-1]
        self.assertTrue(ratio_row.get("aligned_from_source_task_slots"))
        self.assertIn("3.5269배", ratio_row["answer"])
        denominator = ratio_row["calculation_operands"][1]
        self.assertEqual(denominator["raw_value"], "1,001,290")
        self.assertIn("task_output:task_denominator", denominator["source_row_ids"])

    def test_nested_aggregate_promotes_stronger_same_task_rows(self) -> None:
        weak_current = {
            "task_id": "task_current",
            "metric_family": "concept_lookup",
            "metric_label": "2023 allowance expense",
            "operation_family": "lookup",
            "answer": "(303) million",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "(303)million",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {
                        "status": "ok",
                        "label": "allowance expense",
                        "period": "2023",
                        "raw_value": "(303)",
                        "raw_unit": "million",
                        "normalized_value": -303_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "(303)million",
                    },
                },
            },
        }
        strong_current = {
            **weak_current,
            "answer": "(3,146,409) million",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "(3,146,409)million",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {
                        "status": "ok",
                        "label": "allowance expense",
                        "period": "2023",
                        "raw_value": "(3,146,409)",
                        "raw_unit": "million",
                        "normalized_value": -3_146_409_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "(3,146,409)million",
                    },
                },
            },
        }
        aggregate_row = {
            "task_id": "task_summary",
            "metric_family": "narrative_summary",
            "metric_label": "summary",
            "operation_family": "aggregate_subtasks",
            "answer": "2023 allowance expense was (3,146,409) million.",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "2023 allowance expense was (3,146,409) million.",
                "subtask_results": [strong_current],
            },
        }

        promoted = self.agent._promote_stronger_nested_aggregate_results([weak_current, aggregate_row])

        self.assertTrue(promoted[0]["promoted_from_nested_aggregate"])
        self.assertEqual(
            promoted[0]["calculation_result"]["answer_slots"]["primary_value"]["raw_value"],
            "(3,146,409)",
        )

    def test_nested_aggregate_does_not_promote_conflicting_direct_growth_row(self) -> None:
        current_growth = {
            "task_id": "task_growth",
            "metric_family": "concept_growth_rate",
            "metric_label": "segment profit growth",
            "operation_family": "growth_rate",
            "answer": "Segment profit decreased by 84.3%.",
            "status": "ok",
            "source_row_ids": ["row_current", "row_prior"],
            "calculation_result": {
                "status": "ok",
                "rendered_value": "-84.3%",
                "formatted_result": "-84.3%",
                "source_row_ids": ["row_current", "row_prior"],
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {
                        "status": "ok",
                        "label": "segment profit growth",
                        "normalized_value": -84.3,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "-84.3%",
                    },
                    "current_value": {
                        "status": "ok",
                        "label": "segment profit",
                        "period": "2023",
                        "raw_value": "409,219",
                        "raw_unit": "million",
                        "normalized_value": 409_219_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "409,219 million",
                    },
                    "prior_value": {
                        "status": "ok",
                        "label": "segment profit",
                        "period": "2022",
                        "raw_value": "2,600,786",
                        "raw_unit": "million",
                        "normalized_value": 2_600_786_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "2,600,786 million",
                    },
                },
            },
        }
        conflicting_nested_growth = {
            **current_growth,
            "answer": "Segment profit decreased by 76.08%.",
            "source_row_ids": ["task_output:lookup_current", "task_output:lookup_prior", "row_context"],
            "calculation_result": {
                "status": "ok",
                "rendered_value": "-76.08%",
                "formatted_result": "-76.08%",
                "source_row_ids": ["task_output:lookup_current", "task_output:lookup_prior", "row_context"],
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {
                        "status": "ok",
                        "label": "segment profit growth",
                        "normalized_value": -76.08,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "-76.08%",
                    },
                    "current_value": {
                        "status": "ok",
                        "label": "segment profit",
                        "period": "2023",
                        "raw_value": "810,900",
                        "raw_unit": "million",
                        "normalized_value": 810_900_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "810,900 million",
                    },
                    "prior_value": {
                        "status": "ok",
                        "label": "segment profit",
                        "period": "2022",
                        "raw_value": "3,390,092",
                        "raw_unit": "million",
                        "normalized_value": 3_390_092_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "3,390,092 million",
                    },
                },
            },
        }
        aggregate_row = {
            "task_id": "task_summary",
            "metric_family": "narrative_summary",
            "metric_label": "summary",
            "operation_family": "aggregate_subtasks",
            "answer": "Segment profit decreased by 76.08%.",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "Segment profit decreased by 76.08%.",
                "subtask_results": [conflicting_nested_growth],
            },
        }

        promoted = self.agent._promote_stronger_nested_aggregate_results([current_growth, aggregate_row])

        self.assertFalse(promoted[0].get("promoted_from_nested_aggregate"))
        self.assertIn("84.3%", promoted[0]["answer"])
        self.assertNotIn("76.08%", promoted[0]["answer"])

    def test_period_comparison_rows_detect_same_source_value_collapse(self) -> None:
        current_row = {
            "matched_operand_role": "current_period",
            "source_row_id": "row_income",
            "source_row_ids": ["row_income"],
            "raw_value": "1,000",
            "normalized_value": 1000.0,
            "period": "2023",
        }
        stale_prior_row = {
            "matched_operand_role": "prior_period",
            "source_row_id": "row_income",
            "source_row_ids": ["row_income"],
            "raw_value": "1,000",
            "normalized_value": 1000.0,
            "period": "2022",
        }
        real_prior_row = {
            **stale_prior_row,
            "raw_value": "700",
            "normalized_value": 700.0,
        }

        self.assertTrue(
            self.agent._period_comparison_operand_rows_collapse_to_same_slot([current_row, stale_prior_row])
        )
        self.assertFalse(
            self.agent._period_comparison_operand_rows_collapse_to_same_slot([current_row, real_prior_row])
        )

    def test_nested_aggregate_does_not_promote_material_gap_growth_row(self) -> None:
        current_growth = {
            "task_id": "task_growth",
            "metric_family": "concept_growth_rate",
            "metric_label": "segment revenue growth",
            "operation_family": "growth_rate",
            "answer": "Segment revenue increased by 41.4%.",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "41.4%",
                "source_row_ids": ["row_current", "row_prior"],
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {
                        "status": "ok",
                        "label": "segment revenue growth",
                        "normalized_value": 41.4,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "41.4%",
                    },
                    "current_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "period": "2023",
                        "raw_value": "11,621.3",
                        "raw_unit": "hundred million",
                        "normalized_value": 1_162_130_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "11,621 hundred million",
                    },
                    "prior_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "period": "2022",
                        "raw_value": "8,220.1",
                        "raw_unit": "hundred million",
                        "normalized_value": 822_010_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "8,220 hundred million",
                    },
                },
            },
        }
        gap_growth = {
            **current_growth,
            "answer": "Segment revenue increased by 17.65%.",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "17.65%",
                "source_row_ids": ["row_current", "row_prior"],
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {
                        "status": "ok",
                        "label": "segment revenue growth",
                        "normalized_value": 17.65,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "17.65%",
                    },
                    "current_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "period": "2023",
                        "raw_value": "9,670.6",
                        "raw_unit": "hundred million",
                        "normalized_value": 967_060_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "9,671 hundred million",
                    },
                    "prior_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "period": "2023",
                        "raw_value": "8,220.1",
                        "raw_unit": "hundred million",
                        "normalized_value": 822_010_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "8,220 hundred million",
                    },
                },
            },
        }
        aggregate_row = {
            "task_id": "task_summary",
            "metric_family": "narrative_summary",
            "metric_label": "summary",
            "operation_family": "aggregate_subtasks",
            "answer": "Segment revenue increased by 17.65%.",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "Segment revenue increased by 17.65%.",
                "subtask_results": [gap_growth],
            },
        }

        promoted = self.agent._promote_stronger_nested_aggregate_results([current_growth, aggregate_row])

        self.assertFalse(promoted[0].get("promoted_from_nested_aggregate"))
        self.assertIn("41.4%", promoted[0]["answer"])
        self.assertNotIn("17.65%", promoted[0]["answer"])

    def test_quantitative_impact_retrieval_adds_relation_query(self) -> None:
        self.agent.k = 8
        self.agent.vsm = _RecordingVectorStore()
        state = {
            "query": "2023년 주석에서 평가손실 규모를 찾고 이것이 영업비용에 미친 영향을 분석해 줘.",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "topic": "평가손실 영업비용 영향",
            "companies": ["ACME"],
            "years": [2023],
            "report_scope": {"company": "ACME", "year": 2023, "report_type": "사업보고서"},
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "operation_family": "narrative_summary",
                "query": "평가손실이 영업비용에 미친 영향 설명",
                "retrieval_queries": ["평가손실 영업비용 영향"],
            },
        }

        result = self.agent._retrieve(state)
        query_bundle = result["retrieval_debug_trace"]["query_bundle"]

        self.assertTrue(any("평가손실" in query and "포함" in query for query in query_bundle))

    def test_retrieve_surfaces_trace_only_cache_consumer_assessment_without_bypass(self) -> None:
        self.agent.k = 4
        self.agent.vsm = _RecordingVectorStore()
        key = {
            "company": "ACME",
            "report_type": "annual",
            "rcept_no": "r1",
            "year": "2023",
            "metric_label": "metric",
            "period": "2023",
            "consolidation_scope": "consolidated",
            "statement_type": "statement",
            "source_section": "section",
            "source_table_id": "section::table:1",
        }
        state = {
            "query": "metric query",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "topic": "metric",
            "companies": ["ACME"],
            "years": [2023],
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "metric",
                "operation_family": "lookup",
                "query": "metric query",
            },
            "resolved_calculation_trace": {
                "calculation_operands": [{"label": "metric"}],
                "calculation_plan": {"operation": "lookup"},
                "calculation_result": {"status": "ok", "rendered_value": "123"},
                "report_cache_candidate": {
                    "status": "reusable",
                    "reasons": [],
                    "key": key,
                    "key_id": report_cache_key_id(key),
                    "read_only": True,
                },
            },
        }

        result = self.agent._retrieve(state)
        assessment = result["retrieval_debug_trace"]["report_cache_consumer_assessment"]

        self.assertTrue(self.agent.vsm.queries)
        self.assertEqual(assessment["status"], "eligible")
        self.assertTrue(assessment["eligible"])
        self.assertFalse(assessment["enabled"])
        self.assertEqual(assessment["mode"], "trace_only")
        self.assertTrue(assessment["normal_retrieval_executed"])
        self.assertGreaterEqual(assessment["executed_query_count"], 1)

    def test_retrieve_records_blocked_cache_consumer_assessment_and_still_searches(self) -> None:
        self.agent.k = 4
        self.agent.vsm = _RecordingVectorStore()
        state = {
            "query": "metric query",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "topic": "metric",
            "companies": ["ACME"],
            "years": [2023],
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "metric",
                "operation_family": "lookup",
                "query": "metric query",
            },
            "resolved_calculation_trace": {
                "calculation_operands": [{"label": "metric"}],
                "calculation_plan": {"operation": "lookup"},
                "calculation_result": {"status": "ok", "rendered_value": "123"},
                "report_cache_candidate": {
                    "status": "requires_evidence_verification",
                    "reasons": ["missing_scope:statement_type"],
                    "key": {
                        "company": "ACME",
                        "report_type": "annual",
                        "rcept_no": "r1",
                        "year": "2023",
                        "metric_label": "metric",
                        "period": "2023",
                    },
                    "read_only": True,
                },
            },
        }

        result = self.agent._retrieve(state)
        assessment = result["retrieval_debug_trace"]["report_cache_consumer_assessment"]

        self.assertTrue(self.agent.vsm.queries)
        self.assertEqual(assessment["status"], "blocked")
        self.assertFalse(assessment["eligible"])
        self.assertFalse(assessment["enabled"])
        self.assertIn("candidate_not_reusable", assessment["reasons"])
        self.assertIn("candidate_has_reasons", assessment["reasons"])
        self.assertTrue(assessment["normal_retrieval_executed"])

    def test_retrieve_records_not_configured_cache_index_diagnostics_and_still_searches(self) -> None:
        self.agent.k = 4
        self.agent.vsm = _RecordingVectorStore()
        self.agent.report_cache_index_path = ""
        state = {
            "query": "metric query",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "topic": "metric",
            "companies": ["ACME"],
            "years": [2023],
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "metric",
                "operation_family": "lookup",
                "query": "metric query",
            },
        }

        result = self.agent._retrieve(state)
        diagnostics = result["retrieval_debug_trace"]["report_cache_index_diagnostics"]

        self.assertTrue(self.agent.vsm.queries)
        self.assertEqual(diagnostics["status"], "not_configured")
        self.assertFalse(diagnostics["enabled"])
        self.assertFalse(diagnostics["serving_enabled"])
        self.assertFalse(diagnostics["lookup_attempted"])
        self.assertTrue(diagnostics["normal_retrieval_executed"])

    def test_retrieve_records_cache_index_lookup_diagnostics_and_still_searches(self) -> None:
        self.agent.k = 4
        self.agent.vsm = _RecordingVectorStore()
        key = {
            "company": "ACME",
            "report_type": "annual",
            "rcept_no": "r1",
            "year": "2023",
            "metric_label": "metric",
            "period": "2023",
            "consolidation_scope": "consolidated",
            "statement_type": "statement",
            "source_section": "section",
            "source_table_id": "section::table:1",
        }
        entry = {
            "entry_version": REPORT_CACHE_ENTRY_VERSION,
            "source": CACHE_ENTRY_SOURCE_LOCAL_INDEX,
            "key": key,
            "key_id": report_cache_key_id(key),
            "value": {"kind": "calculation_result", "rendered_value": "123"},
            "provenance": {"source_row_ids": ["row-1"], "evidence_refs": ["ev-1"]},
        }
        state = {
            "query": "metric query",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "topic": "metric",
            "companies": ["ACME"],
            "years": [2023],
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "metric",
                "operation_family": "lookup",
                "query": "metric query",
            },
            "resolved_calculation_trace": {
                "calculation_operands": [{"label": "metric"}],
                "calculation_plan": {"operation": "lookup"},
                "calculation_result": {"status": "ok", "rendered_value": "123"},
                "report_cache_candidate": {
                    "status": "reusable",
                    "reasons": [],
                    "key": key,
                    "key_id": report_cache_key_id(key),
                    "read_only": True,
                },
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report_cache_index.json"
            path.write_text(json.dumps([entry], ensure_ascii=False), encoding="utf-8")
            self.agent.report_cache_index_path = str(path)

            result = self.agent._retrieve(state)

        diagnostics = result["retrieval_debug_trace"]["report_cache_index_diagnostics"]

        self.assertTrue(self.agent.vsm.queries)
        self.assertEqual(diagnostics["status"], "trace_only")
        self.assertFalse(diagnostics["enabled"])
        self.assertFalse(diagnostics["serving_enabled"])
        self.assertTrue(diagnostics["lookup_attempted"])
        self.assertEqual(diagnostics["match_count"], 1)
        self.assertEqual(diagnostics["readable_match_count"], 1)
        self.assertTrue(diagnostics["normal_retrieval_executed"])

    def test_synthesis_retry_strategy_blocks_broad_fallback_for_ratio_task(self) -> None:
        state = {
            "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "report_scope": {"company": "네이버", "year": 2023},
            "topic": "종업원급여 비중",
            "retry_strategy": "synthesize_from_task_outputs",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "종업원급여 비중",
                "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "종업원급여", "concept": "employee_benefits_expense", "role": "numerator_1"},
                    {"label": "영업비용", "concept": "operating_expense_total", "role": "denominator_1"},
                ],
                "depends_on": ["task_2", "task_3"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "employee_benefits_expense",
                        "period": "2023",
                        "label": "종업원급여",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_expense_total",
                        "period": "2023",
                        "label": "영업비용",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 종업원급여",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 1701418940000.0,
                        "result_unit": "천원",
                        "rendered_value": "1조 7,014억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 종업원급여",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2023년 종업원급여",
                                "concept": "employee_benefits_expense",
                                "period": "2023",
                                "raw_value": "1,701,418,940",
                                "raw_unit": "천원",
                                "normalized_value": 1701418940000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "1조 7,014억원",
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "retry_retrieval", "retry_strategy": "synthesize_from_task_outputs"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(extracted["calculation_debug_trace"]["source"], "dependency_binding_guard")
        self.assertEqual(extracted["calculation_debug_trace"]["retry_strategy"], "synthesize_from_task_outputs")
        self.assertEqual(len(trace["calculation_operands"]), 1)
        self.assertEqual(trace["calculation_operands"][0]["matched_operand_role"], "numerator_1")
        self.assertTrue(trace["calculation_operands"][0]["dependency_resolved"])

    def test_synthesis_retry_strategy_uses_resolved_task_output_operands(self) -> None:
        state = {
            "query": "calculate the ratio from completed lookup tasks",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "retry_strategy": "synthesize_from_task_outputs",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "ratio",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "numerator", "role": "numerator_1"},
                    {"label": "denominator", "role": "denominator_1"},
                ],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "period": "2023",
                        "label": "numerator",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "period": "2023",
                        "label": "denominator",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "numerator",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "numerator",
                                "period": "2023",
                                "raw_value": "10",
                                "raw_unit": "원",
                                "normalized_value": 10.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "10원",
                                "source_row_id": "ev_numerator",
                                "source_row_ids": ["ev_numerator"],
                            },
                        },
                    },
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "denominator",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "denominator",
                                "period": "2023",
                                "raw_value": "20",
                                "raw_unit": "원",
                                "normalized_value": 20.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "20원",
                                "source_row_id": "ev_denominator",
                                "source_row_ids": ["ev_denominator"],
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "retry_retrieval", "retry_strategy": "synthesize_from_task_outputs"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertIn(
            extracted["calculation_debug_trace"]["source"],
            {"structured_row_direct", "dependency_synthesis_only"},
        )
        self.assertEqual(len(trace["calculation_operands"]), 2)
        self.assertEqual(
            [row["matched_operand_role"] for row in trace["calculation_operands"]],
            ["numerator_1", "denominator_1"],
        )
        self.assertEqual(extracted["artifacts"][0]["kind"], "operand_set")

    def test_partial_dependency_rows_are_preserved_when_llm_extraction_is_empty(self) -> None:
        state = {
            "query": "calculate the change from completed task output and a missing prior value",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_change",
                "metric_label": "change",
                "operation_family": "difference",
                "required_operands": [
                    {"label": "current value", "role": "minuend", "required": True},
                    {"label": "prior value", "role": "subtrahend", "required": True},
                ],
                "inputs": [
                    {
                        "role": "minuend",
                        "period": "current",
                        "label": "current value",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "current value",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "current value",
                                "period": "current",
                                "raw_value": "10",
                                "raw_unit": "원",
                                "normalized_value": 10.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "10원",
                                "source_row_id": "ev_current",
                                "source_row_ids": ["ev_current"],
                            },
                        },
                    },
                },
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_context",
                    "claim": "completed task output should remain available for downstream arithmetic.",
                    "support_level": "context",
                    "metadata": {},
                }
            ],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(extracted["evidence_status"], "partial")
        self.assertEqual(len(trace["calculation_operands"]), 1)
        self.assertEqual(trace["calculation_operands"][0]["matched_operand_role"], "minuend")
        self.assertEqual(extracted["artifacts"][0]["payload"]["calculation_operands"][0]["raw_value"], "10")

    def test_route_after_reconcile_plan_uses_operand_extractor_for_synthesis_strategy(self) -> None:
        route = self.agent._route_after_reconcile_plan(
            {
                "reconciliation_result": {
                    "status": "retry_retrieval",
                    "retry_strategy": "synthesize_from_task_outputs",
                }
            }
        )

        self.assertEqual(route, "operand_extractor")

    def test_dependency_guard_blocks_direct_rows_for_unresolved_ratio_binding(self) -> None:
        state = {
            "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "report_scope": {"company": "네이버", "year": 2023},
            "topic": "종업원급여 비중",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "종업원급여 비중",
                "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "종업원급여", "concept": "employee_benefits_expense", "role": "numerator_1"},
                    {"label": "영업비용", "concept": "operating_expense_total", "role": "denominator_1"},
                ],
                "depends_on": ["task_2", "task_3"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "employee_benefits_expense",
                        "period": "2023",
                        "label": "종업원급여",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_expense_total",
                        "period": "2023",
                        "label": "영업비용",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 종업원급여",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 1701418940000.0,
                        "result_unit": "천원",
                        "rendered_value": "1조 7,014억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 종업원급여",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2023년 종업원급여",
                                "concept": "employee_benefits_expense",
                                "period": "2023",
                                "raw_value": "1,701,418,940",
                                "raw_unit": "천원",
                                "normalized_value": 1701418940000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "1조 7,014억원",
                            },
                        },
                    },
                }
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [
            {
                "operand_id": "op_001",
                "evidence_id": "value:employee",
                "label": "2023 종업원급여",
                "raw_value": "1,701,418,940",
                "raw_unit": "천원",
                "normalized_value": 1701418940000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "matched_operand_label": "종업원급여",
                "matched_operand_concept": "employee_benefits_expense",
                "matched_operand_role": "numerator_1",
            },
            {
                "operand_id": "op_002",
                "evidence_id": "value:expense",
                "label": "2023 영업비용",
                "raw_value": "6,915,414,298",
                "raw_unit": "천원",
                "normalized_value": 6915414298000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "matched_operand_label": "영업비용",
                "matched_operand_concept": "operating_expense_total",
                "matched_operand_role": "denominator_1",
            },
        ]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(extracted["calculation_debug_trace"]["source"], "dependency_binding_guard")
        self.assertEqual(len(trace["calculation_operands"]), 1)
        self.assertEqual(trace["calculation_operands"][0]["matched_operand_role"], "numerator_1")
        self.assertTrue(trace["calculation_operands"][0]["dependency_resolved"])
        self.assertEqual(
            extracted["calculation_debug_trace"]["missing_dependency_bindings"][0]["role"],
            "denominator_1",
        )

    def test_direct_structured_operands_enrich_reconciliation_artifact_refs(self) -> None:
        state = {
            "query": "Return the requested value.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "Example", "year": 2023},
            "topic": "requested value",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "requested value",
                "operation_family": "lookup",
            },
            "reconciliation_result": {"status": "ready"},
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "reconciliation",
                    "label": "reconcile requested value",
                    "status": "completed",
                    "artifact_ids": ["reconcile:task_1:001"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "reconcile:task_1:001",
                    "task_id": "task_1",
                    "kind": "reconciliation_result",
                    "status": "ok",
                    "payload": {"reconciliation_result": {"status": "ready", "matched_operands": []}},
                    "evidence_refs": [],
                }
            ],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [
            {
                "operand_id": "op_001",
                "evidence_id": "ev_source",
                "source_row_ids": ["row_source"],
                "label": "Requested value",
                "raw_value": "100",
                "normalized_value": 100.0,
                "matched_operand_label": "Requested value",
                "matched_operand_role": "value",
            }
        ]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []

        extracted = self.agent._extract_calculation_operands(state)
        reconcile_artifact = next(
            artifact
            for artifact in extracted["artifacts"]
            if artifact["artifact_id"] == "reconcile:task_1:001"
        )

        self.assertEqual(reconcile_artifact["evidence_refs"], ["ev_source", "row_source"])

    def test_ratio_missing_dependency_binding_can_fall_back_to_retrieved_docs(self) -> None:
        state = {
            "query": "Calculate employee benefits as a share of 2023 operating expense.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "NAVER", "year": 2023},
            "topic": "employee benefits ratio",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "employee benefits ratio",
                "query": "Calculate employee benefits as a share of 2023 operating expense.",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "employee benefits", "concept": "employee_benefits_expense", "role": "numerator_1"},
                    {"label": "operating expense", "concept": "operating_expense_total", "role": "denominator_1"},
                ],
                "depends_on": ["task_2", "task_3"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "employee_benefits_expense",
                        "period": "2023",
                        "label": "employee benefits",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_expense_total",
                        "period": "2023",
                        "label": "operating expense",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 employee benefits",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "employee benefits",
                                "concept": "employee_benefits_expense",
                                "period": "2023",
                                "raw_value": "1,701,418,940",
                                "raw_unit": "thousand KRW",
                                "normalized_value": 1701418940000.0,
                                "normalized_unit": "KRW",
                            }
                        },
                    },
                }
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [
                (
                    Document(
                        page_content="operating expense | 8,181,823,307",
                        metadata={"block_type": "table", "table_source_id": "naver-op-expense"},
                    ),
                    1.0,
                )
            ],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        self.agent.llm = _StubLLM(
            OperandExtraction(
                coverage="sufficient",
                operands=[
                    CalculationOperand(
                        operand_id="op_001",
                        evidence_id="ev_doc_001",
                        source_anchor="[NAVER | 2023]",
                        label="operating expense",
                        raw_value="8,181,823,307",
                        raw_unit="thousand KRW",
                        normalized_value=8181823307000.0,
                        normalized_unit="KRW",
                        period="2023",
                    )
                ],
            )
        )
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: []
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertNotEqual(extracted["calculation_debug_trace"].get("source"), "dependency_binding_guard")
        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertEqual(len(trace["calculation_operands"]), 2)
        self.assertEqual(
            [row.get("matched_operand_role") for row in trace["calculation_operands"]],
            ["numerator_1", "denominator_1"],
        )

    def test_llm_operand_extraction_can_return_retrieved_doc_ratio_operand(self) -> None:
        table_object = {
            "table_id": "example-table",
            "statement_type": "mda",
            "consolidation_scope": "unknown",
            "unit_hint": "원",
            "period_labels": ["2023", "2022"],
            "rows": [
                {
                    "row_label": "operating profit",
                    "row_headers": ["operating profit"],
                    "cells": [
                        {
                            "column_headers": ["2023"],
                            "value_text": "1,000",
                            "unit_hint": "원",
                        },
                        {
                            "column_headers": ["2022"],
                            "value_text": "900",
                            "unit_hint": "원",
                        },
                    ],
                }
            ],
        }
        state = {
            "query": "Calculate expense as a share of 2023 operating profit.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "ExampleCo", "year": 2023},
            "topic": "expense ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "expense ratio",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "expense", "concept": "expense", "role": "numerator_1"},
                    {"label": "operating profit", "concept": "operating_profit", "role": "denominator_1"},
                ],
                "depends_on": ["task_expense", "task_profit"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "expense",
                        "period": "2023",
                        "label": "expense",
                        "preferred_task_id": "task_expense",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_profit",
                        "period": "2023",
                        "label": "operating profit",
                        "preferred_task_id": "task_profit",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_expense",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 expense",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "expense",
                                "concept": "expense",
                                "period": "2023",
                                "raw_value": "250",
                                "raw_unit": "원",
                                "normalized_value": 250.0,
                                "normalized_unit": "KRW",
                            }
                        },
                    },
                }
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [
                (
                    Document(
                        page_content="Metric | 2023 | 2022\noperating profit | 1,000 | 900",
                        metadata={
                            "block_type": "paragraph",
                            "table_source_id": "example-table",
                            "table_object_json": json.dumps(table_object),
                            "unit_hint": "원",
                        },
                    ),
                    1.0,
                )
            ],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        self.agent.llm = _StubLLM(
            OperandExtraction(
                coverage="sufficient",
                operands=[
                    CalculationOperand(
                        operand_id="op_001",
                        evidence_id="task_output:task_expense",
                        source_anchor="[task_expense]",
                        label="expense",
                        raw_value="250",
                        raw_unit="원",
                        normalized_value=250.0,
                        normalized_unit="KRW",
                        period="2023",
                    ),
                    CalculationOperand(
                        operand_id="op_002",
                        evidence_id="ev_doc_001",
                        source_anchor="[ExampleCo | 2023]",
                        label="operating profit",
                        raw_value="1,000",
                        raw_unit="원",
                        normalized_value=1000.0,
                        normalized_unit="KRW",
                        period="2023",
                    ),
                ],
            )
        )
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: []
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []
        self.agent._llm_lookup_operand_has_direct_support = lambda *_args, **_kwargs: True

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertEqual(
            len({row.get("operand_id") for row in trace["calculation_operands"]}),
            2,
        )
        denominator = next(
            row
            for row in trace["calculation_operands"]
            if row.get("label") == "operating profit"
        )
        self.assertEqual(denominator["raw_value"], "1,000")

    def test_ratio_missing_dependency_binding_can_use_active_reconciliation_evidence(self) -> None:
        state = {
            "query": "Calculate expense as a share of operating profit.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "ExampleCo", "year": 2023},
            "topic": "expense ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "expense ratio",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "expense", "concept": "expense", "role": "numerator_1"},
                    {"label": "operating profit", "concept": "operating_profit", "role": "denominator_1"},
                ],
                "depends_on": ["task_expense", "task_profit"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "expense",
                        "period": "2023",
                        "label": "expense",
                        "preferred_task_id": "task_expense",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_profit",
                        "period": "2023",
                        "label": "operating profit",
                        "preferred_task_id": "task_profit",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "ready",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        self.agent.llm = _StubLLM(
            OperandExtraction(
                coverage="sufficient",
                operands=[
                    CalculationOperand(
                        operand_id="op_001",
                        evidence_id="ev_expense",
                        source_anchor="[ExampleCo | 2023]",
                        label="expense",
                        raw_value="250",
                        raw_unit="",
                        normalized_value=250.0,
                        normalized_unit="UNKNOWN",
                        period="2023",
                    ),
                    CalculationOperand(
                        operand_id="op_002",
                        evidence_id="ev_profit",
                        source_anchor="[ExampleCo | 2023]",
                        label="operating profit",
                        raw_value="1,000",
                        raw_unit="",
                        normalized_value=1000.0,
                        normalized_unit="UNKNOWN",
                        period="2023",
                    ),
                ],
            )
        )
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: []
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: [
            {
                "evidence_id": "ev_profit",
                "source_anchor": "[ExampleCo | 2023]",
                "claim": "operating profit | 1,000",
                "raw_row_text": "operating profit | 1,000",
                "metadata": {"statement_type": "income_statement"},
            },
            {
                "evidence_id": "ev_expense",
                "source_anchor": "[ExampleCo | 2023]",
                "claim": "expense | 250",
                "raw_row_text": "expense | 250",
                "metadata": {"statement_type": "income_statement"},
            },
        ]
        self.agent._llm_lookup_operand_has_direct_support = lambda *_args, **_kwargs: True

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertNotEqual(extracted["calculation_debug_trace"].get("source"), "dependency_binding_guard")
        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertEqual(len(trace["calculation_operands"]), 2)

    def test_ratio_dependency_fallback_rejects_rows_outside_producer_statement_scope(self) -> None:
        state = {
            "query": "Calculate the ratio using values from the income statement.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "ExampleCo", "year": 2023},
            "topic": "expense ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "expense ratio",
                "query": "Calculate the ratio using values from the income statement.",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "cost", "concept": "cost_of_sales", "role": "numerator_1"},
                    {"label": "revenue", "concept": "revenue", "role": "denominator_1"},
                ],
                "depends_on": ["task_cost", "task_revenue"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "cost_of_sales",
                        "period": "2023",
                        "label": "cost",
                        "preferred_task_id": "task_cost",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "revenue",
                        "period": "2023",
                        "label": "revenue",
                        "preferred_task_id": "task_revenue",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "calc_subtasks": [
                {
                    "task_id": "task_cost",
                    "operation_family": "lookup",
                    "preferred_statement_types": ["income_statement"],
                    "required_operands": [
                        {
                            "label": "cost",
                            "concept": "cost_of_sales",
                            "role": "numerator_1",
                            "preferred_statement_types": ["income_statement"],
                        }
                    ],
                },
                {
                    "task_id": "task_revenue",
                    "operation_family": "lookup",
                    "preferred_statement_types": ["income_statement"],
                    "required_operands": [
                        {
                            "label": "revenue",
                            "concept": "revenue",
                            "role": "denominator_1",
                            "preferred_statement_types": ["income_statement"],
                        }
                    ],
                },
                {
                    "task_id": "task_ratio",
                    "operation_family": "ratio",
                },
            ],
            "subtask_results": [
                {
                    "task_id": "task_revenue",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 revenue",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "revenue",
                                "concept": "revenue",
                                "period": "2023",
                                "raw_value": "1,000",
                                "raw_unit": "백만원",
                                "normalized_value": 1000000000.0,
                                "normalized_unit": "KRW",
                            }
                        },
                    },
                }
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [
                (
                    Document(
                        page_content="cost | 100\nrevenue | 1,000",
                        metadata={"block_type": "table", "statement_type": "notes"},
                    ),
                    1.0,
                )
            ],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [
            {
                "operand_id": "op_001",
                "evidence_id": "value:cost",
                "label": "2023 cost",
                "raw_value": "100",
                "raw_unit": "백만원",
                "normalized_value": 100000000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "statement_type": "income_statement",
                "source_anchor": "[ExampleCo | 2023 | Financial statement notes]",
                "matched_operand_label": "cost",
                "matched_operand_concept": "cost_of_sales",
                "matched_operand_role": "numerator_1",
            },
            {
                "operand_id": "op_002",
                "evidence_id": "value:revenue",
                "label": "2023 revenue",
                "raw_value": "1,000",
                "raw_unit": "백만원",
                "normalized_value": 1000000000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "statement_type": "income_statement",
                "matched_operand_label": "revenue",
                "matched_operand_concept": "revenue",
                "matched_operand_role": "denominator_1",
            },
        ]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(extracted["calculation_debug_trace"]["source"], "dependency_binding_guard")
        self.assertEqual(len(trace["calculation_operands"]), 1)
        self.assertEqual(trace["calculation_operands"][0]["matched_operand_role"], "denominator_1")
        rejected = extracted["calculation_debug_trace"]["rejected_dependency_scope_rows"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["reject_reason"], "section_scope")

    def test_ratio_complete_active_reconciliation_rows_override_dependency_scope_filter(self) -> None:
        state = {
            "query": "Calculate the ratio from the management discussion table.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "ExampleCo", "year": 2023},
            "topic": "expense ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "expense ratio",
                "query": "Calculate the ratio from the management discussion table.",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "expense input", "concept": "expense_input", "role": "numerator_1"},
                    {"label": "profit base", "concept": "profit_base", "role": "denominator_1"},
                ],
                "depends_on": ["task_expense", "task_profit"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "expense_input",
                        "period": "2023",
                        "label": "expense input",
                        "preferred_task_id": "task_expense",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "profit_base",
                        "period": "2023",
                        "label": "profit base",
                        "preferred_task_id": "task_profit",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "calc_subtasks": [
                {
                    "task_id": "task_expense",
                    "operation_family": "lookup",
                    "preferred_statement_types": ["income_statement"],
                    "preferred_sections": ["Income Statement"],
                    "required_operands": [
                        {
                            "label": "expense input",
                            "concept": "expense_input",
                            "role": "numerator_1",
                            "preferred_statement_types": ["income_statement"],
                        }
                    ],
                },
                {
                    "task_id": "task_profit",
                    "operation_family": "lookup",
                    "preferred_statement_types": ["income_statement"],
                    "preferred_sections": ["Income Statement"],
                    "required_operands": [
                        {
                            "label": "profit base",
                            "concept": "profit_base",
                            "role": "denominator_1",
                            "preferred_statement_types": ["income_statement"],
                        }
                    ],
                },
            ],
            "subtask_results": [
                {
                    "task_id": "task_expense",
                    "metric_family": "concept_lookup",
                    "metric_label": "expense input",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "expense input",
                                "concept": "expense_input",
                                "period": "2023",
                                "raw_value": "435,542",
                                "raw_unit": "백만원",
                                "normalized_value": 435542000000.0,
                                "normalized_unit": "KRW",
                            }
                        },
                    },
                }
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }
        direct_rows = [
            {
                "operand_id": "op_001",
                "evidence_id": "value:expense",
                "label": "expense input",
                "raw_value": "4,355",
                "raw_unit": "억원",
                "normalized_value": 435500000000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "statement_type": "mda",
                "source_anchor": "[ExampleCo | 2023 | Management Discussion Notes]",
                "matched_operand_label": "expense input",
                "matched_operand_concept": "expense_input",
                "matched_operand_role": "numerator_1",
            },
            {
                "operand_id": "op_002",
                "evidence_id": "value:profit",
                "label": "profit base",
                "raw_value": "11,623",
                "raw_unit": "억원",
                "normalized_value": 1162300000000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "statement_type": "mda",
                "source_anchor": "[ExampleCo | 2023 | Management Discussion Notes]",
                "matched_operand_label": "profit base",
                "matched_operand_concept": "profit_base",
                "matched_operand_role": "denominator_1",
            },
        ]
        reconciliation_evidence = [
            {
                "evidence_id": "value:ratio_table",
                "source_anchor": "[ExampleCo | 2023 | Management Discussion Notes]",
                "claim": "expense input 4,355억원; profit base 11,623억원",
                "raw_row_text": "expense input 4,355억원; profit base 11,623억원",
                "metadata": {"statement_type": "mda"},
            }
        ]
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [dict(row) for row in direct_rows]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: [dict(item) for item in reconciliation_evidence]

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertEqual(extracted["calculation_debug_trace"]["source"], "structured_row_direct")
        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertEqual(len(trace["calculation_operands"]), 2)
        self.assertEqual(
            {row["matched_operand_role"] for row in trace["calculation_operands"]},
            {"numerator_1", "denominator_1"},
        )

    def test_growth_rate_direct_rows_can_fill_missing_task_output_binding(self) -> None:
        state = {
            "query": "2023년 시설투자(CAPEX) 총액의 전년 대비 증감률을 계산해 줘.",
            "query_type": "trend",
            "intent": "trend",
            "report_scope": {"company": "삼성전자", "year": 2023},
            "topic": "시설투자(CAPEX) 총액 증감률",
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "concept_growth_rate",
                "metric_label": "시설투자(CAPEX) 총액 증감률",
                "query": "2023년 시설투자(CAPEX) 총액의 전년 대비 증감률을 계산해 줘.",
                "operation_family": "growth_rate",
                "required_operands": [
                    {"label": "시설투자(CAPEX)", "concept": "capital_expenditure_total", "role": "current_period", "period": "2023"},
                    {"label": "시설투자(CAPEX)", "concept": "capital_expenditure_total", "role": "prior_period", "period": "2022"},
                ],
                "depends_on": ["task_1", "task_3"],
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "capital_expenditure_total",
                        "period": "2023",
                        "label": "시설투자(CAPEX)",
                        "preferred_task_id": "task_1",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "prior_period",
                        "concept": "capital_expenditure_total",
                        "period": "2022",
                        "label": "시설투자(CAPEX)",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 시설투자(CAPEX) 총액",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 53113900000000.0,
                        "result_unit": "억원",
                        "rendered_value": "53조 1,139억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 시설투자(CAPEX) 총액",
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
                            },
                        },
                    },
                }
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [
            {
                "operand_id": "op_001",
                "evidence_id": "value:capex:2023",
                "label": "2023 시설투자(CAPEX)",
                "raw_value": "531,139",
                "raw_unit": "억원",
                "normalized_value": 53113900000000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "matched_operand_label": "시설투자(CAPEX)",
                "matched_operand_concept": "capital_expenditure_total",
                "matched_operand_role": "current_period",
            },
            {
                "operand_id": "op_002",
                "evidence_id": "value:capex:2022",
                "label": "2022 시설투자(CAPEX)",
                "raw_value": "531,153",
                "raw_unit": "억원",
                "normalized_value": 53115300000000.0,
                "normalized_unit": "KRW",
                "period": "2022",
                "matched_operand_label": "시설투자(CAPEX)",
                "matched_operand_concept": "capital_expenditure_total",
                "matched_operand_role": "prior_period",
            },
        ]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertNotEqual(extracted["calculation_debug_trace"]["source"], "dependency_binding_guard")
        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertEqual(len(trace["calculation_operands"]), 2)
        self.assertEqual(
            {row["matched_operand_role"] for row in trace["calculation_operands"]},
            {"current_period", "prior_period"},
        )

    def test_growth_rate_partial_direct_rows_use_reconciliation_fallback(self) -> None:
        state = {
            "query": "2023년 target metric의 전년 대비 증가율을 계산해 줘.",
            "query_type": "trend",
            "intent": "trend",
            "report_scope": {"company": "Example", "year": 2023},
            "topic": "target metric growth",
            "active_subtask": {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "target metric growth",
                "operation_family": "growth_rate",
                "required_operands": [
                    {"label": "target metric", "concept": "target_metric", "role": "current_period", "period": "2023"},
                    {"label": "target metric", "concept": "target_metric", "role": "prior_period", "period": "2022"},
                ],
                "depends_on": ["task_current", "task_prior"],
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "target_metric",
                        "period": "2023",
                        "label": "target metric",
                        "preferred_task_id": "task_current",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "prior_period",
                        "concept": "target_metric",
                        "period": "2022",
                        "label": "target metric",
                        "preferred_task_id": "task_prior",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 target metric",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "target metric",
                                "concept": "target_metric",
                                "period": "2023",
                                "raw_value": "200",
                                "normalized_value": 200.0,
                                "normalized_unit": "UNKNOWN",
                                "rendered_value": "200",
                            },
                        },
                    },
                }
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [
            {
                "operand_id": "op_current",
                "evidence_id": "recon_current",
                "label": "2023 target metric",
                "raw_value": "200",
                "normalized_value": 200.0,
                "normalized_unit": "UNKNOWN",
                "period": "2023",
                "matched_operand_label": "target metric",
                "matched_operand_concept": "target_metric",
                "matched_operand_role": "current_period",
            }
        ]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: [
            {
                "evidence_id": "recon_prior",
                "source_anchor": "[Example | 2023 | table]",
                "claim": "target metric | 2023 200 | 2022 100",
                "raw_row_text": "target metric | 2023 200 | 2022 100",
                "metadata": {"block_type": "table"},
            }
        ]
        self.agent.llm = _StubLLM(
            OperandExtraction(
                coverage="sufficient",
                operands=[
                    CalculationOperand(
                        operand_id="op_current",
                        evidence_id="recon_current",
                        source_anchor="[Example | 2023 | table]",
                        label="target metric",
                        raw_value="200",
                        raw_unit="",
                        normalized_value=200.0,
                        normalized_unit="UNKNOWN",
                        period="2023",
                    ),
                    CalculationOperand(
                        operand_id="op_prior",
                        evidence_id="recon_prior",
                        source_anchor="[Example | 2023 | table]",
                        label="target metric",
                        raw_value="100",
                        raw_unit="",
                        normalized_value=100.0,
                        normalized_unit="UNKNOWN",
                        period="2022",
                    ),
                ],
            )
        )

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)

        self.assertNotEqual(extracted["calculation_debug_trace"].get("source"), "dependency_binding_guard")
        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertEqual(len(trace["calculation_operands"]), 2)
        self.assertEqual(
            {row["period"] for row in trace["calculation_operands"]},
            {"2023", "2022"},
        )

    def test_growth_rate_prefers_complete_reconciliation_rows_over_dependency_outputs(self) -> None:
        state = {
            "query": "2023년 target metric의 전년 대비 증가율을 계산해 줘.",
            "query_type": "trend",
            "intent": "trend",
            "report_scope": {"company": "Example", "year": 2023},
            "topic": "target metric growth",
            "active_subtask": {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "target metric growth",
                "operation_family": "growth_rate",
                "required_operands": [
                    {"label": "target metric", "concept": "target_metric", "role": "current_period", "period": "2023"},
                    {"label": "target metric", "concept": "target_metric", "role": "prior_period", "period": "2022"},
                ],
                "depends_on": ["task_current", "task_prior"],
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "target_metric",
                        "period": "2023",
                        "label": "target metric",
                        "preferred_task_id": "task_current",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output"],
                    },
                    {
                        "role": "prior_period",
                        "concept": "target_metric",
                        "period": "2022",
                        "label": "target metric",
                        "preferred_task_id": "task_prior",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 target metric",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "target metric",
                                "concept": "target_metric",
                                "period": "2023",
                                "raw_value": "200",
                                "raw_unit": "",
                                "normalized_value": 200.0,
                                "normalized_unit": "UNKNOWN",
                                "rendered_value": "200",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_prior",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022 target metric",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "target metric",
                                "concept": "target_metric",
                                "period": "2022",
                                "raw_value": "3",
                                "raw_unit": "",
                                "normalized_value": 3.0,
                                "normalized_unit": "UNKNOWN",
                                "rendered_value": "3",
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [
            {
                "operand_id": "op_current",
                "evidence_id": "recon_current",
                "source_anchor": "[Example | 2023 | table]",
                "label": "target metric",
                "raw_value": "200",
                "raw_unit": "",
                "normalized_value": 200.0,
                "normalized_unit": "UNKNOWN",
                "period": "2023",
                "matched_operand_label": "target metric",
                "matched_operand_concept": "target_metric",
                "matched_operand_role": "current_period",
            },
            {
                "operand_id": "op_prior",
                "evidence_id": "recon_prior",
                "source_anchor": "[Example | 2023 | table]",
                "label": "target metric",
                "raw_value": "100",
                "raw_unit": "",
                "normalized_value": 100.0,
                "normalized_unit": "UNKNOWN",
                "period": "2022",
                "matched_operand_label": "target metric",
                "matched_operand_concept": "target_metric",
                "matched_operand_role": "prior_period",
            },
        ]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: [
            {
                "evidence_id": "recon_current",
                "source_anchor": "[Example | 2023 | table]",
                "claim": "target metric | 2023 200 | 2022 100",
                "quote_span": "2023 200",
                "raw_row_text": "target metric | 2023 200 | 2022 100",
                "metadata": {"block_type": "table"},
            },
            {
                "evidence_id": "recon_prior",
                "source_anchor": "[Example | 2023 | table]",
                "claim": "target metric | 2023 200 | 2022 100",
                "quote_span": "2022 100",
                "raw_row_text": "target metric | 2023 200 | 2022 100",
                "metadata": {"block_type": "table"},
            },
        ]

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)
        operands_by_role = {
            row["matched_operand_role"]: row
            for row in trace["calculation_operands"]
        }

        self.assertEqual(extracted["calculation_debug_trace"].get("source"), "structured_row_direct")
        self.assertEqual(operands_by_role["current_period"]["raw_value"], "200")
        self.assertEqual(operands_by_role["prior_period"]["raw_value"], "100")
        self.assertNotEqual(operands_by_role["prior_period"]["raw_value"], "3")

    def test_period_comparison_dependency_outputs_block_conflicting_direct_context(self) -> None:
        state = {
            "query": "2023년 target metric의 전년 대비 증가액을 계산해 줘.",
            "query_type": "trend",
            "intent": "trend",
            "report_scope": {"company": "Example", "year": 2023},
            "topic": "target metric difference",
            "active_subtask": {
                "task_id": "task_difference",
                "metric_family": "concept_difference",
                "metric_label": "target metric difference",
                "operation_family": "difference",
                "required_operands": [
                    {"label": "target metric", "concept": "target_metric", "role": "current_period", "period": "2023"},
                    {"label": "target metric", "concept": "target_metric", "role": "prior_period", "period": "2022"},
                ],
                "depends_on": ["task_current", "task_prior"],
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "target_metric",
                        "period": "2023",
                        "label": "target metric",
                        "preferred_task_id": "task_current",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "prior_period",
                        "concept": "target_metric",
                        "period": "2022",
                        "label": "target metric",
                        "preferred_task_id": "task_prior",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 target metric",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "target metric",
                                "concept": "target_metric",
                                "period": "2023",
                                "raw_value": "200",
                                "raw_unit": "",
                                "normalized_value": 200.0,
                                "normalized_unit": "UNKNOWN",
                                "rendered_value": "200",
                                "source_row_id": "ev_current",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_prior",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022 target metric",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "target metric",
                                "concept": "target_metric",
                                "period": "2022",
                                "raw_value": "100",
                                "raw_unit": "",
                                "normalized_value": 100.0,
                                "normalized_unit": "UNKNOWN",
                                "rendered_value": "100",
                                "source_row_id": "ev_prior",
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [
            {
                "operand_id": "op_current",
                "evidence_id": "direct_current",
                "source_row_id": "direct_current",
                "table_source_id": "direct_table",
                "label": "target metric",
                "raw_value": "200",
                "raw_unit": "",
                "normalized_value": 200.0,
                "normalized_unit": "UNKNOWN",
                "period": "2023",
                "matched_operand_label": "target metric",
                "matched_operand_concept": "target_metric",
                "matched_operand_role": "current_period",
            },
            {
                "operand_id": "op_prior",
                "evidence_id": "direct_prior",
                "source_row_id": "direct_prior",
                "table_source_id": "direct_table",
                "label": "target metric",
                "raw_value": "30",
                "raw_unit": "",
                "normalized_value": 30.0,
                "normalized_unit": "UNKNOWN",
                "period": "2022",
                "matched_operand_label": "target metric",
                "matched_operand_concept": "target_metric",
                "matched_operand_role": "prior_period",
            },
        ]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []

        extracted = self.agent._extract_calculation_operands(state)
        trace = _resolve_runtime_calculation_trace(extracted)
        operands_by_role = {
            row["matched_operand_role"]: row
            for row in trace["calculation_operands"]
        }

        self.assertEqual(operands_by_role["current_period"]["raw_value"], "200")
        self.assertEqual(operands_by_role["prior_period"]["raw_value"], "100")
        self.assertNotEqual(operands_by_role["prior_period"]["raw_value"], "30")
        self.assertIn("task_output:task_prior", operands_by_role["prior_period"]["source_row_ids"])

    def test_compact_ratio_answer_includes_component_slots(self) -> None:
        calculation_result = {
            "status": "ok",
            "rendered_value": "37.47%",
            "answer_slots": {
                "operation_family": "ratio",
                "metric_label": "target ratio",
                "primary_value": {
                    "status": "ok",
                    "role": "primary_value",
                    "label": "target ratio",
                    "rendered_value": "37.47%",
                },
                "components_by_group": {
                    "numerator": [
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "expense input",
                            "period": "2023년",
                            "raw_value": "4,355",
                            "raw_unit": "억원",
                            "rendered_value": "4,355억원",
                        }
                    ],
                    "denominator": [
                        {
                            "status": "ok",
                            "role": "denominator_1",
                            "label": "profit base",
                            "period": "2023",
                            "raw_value": "11,623",
                            "raw_unit": "억원",
                            "rendered_value": "11,623억원",
                        }
                    ],
                },
            },
        }

        answer = self.agent._compact_ratio_answer(
            {
                "active_subtask": {"metric_label": "target ratio"},
                "resolved_calculation_trace": {
                    "calculation_result": calculation_result,
                    "calculation_operands": [],
                    "calculation_plan": {"operation": "ratio"},
                },
            },
            calculation_result,
        )

        self.assertIn("2023년 target ratio은 37.47%입니다.", answer)
        self.assertIn("expense input 4,355억원", answer)
        self.assertIn("profit base 11,623억원", answer)

    def test_compact_ratio_answer_uses_shared_krw_component_unit(self) -> None:
        calculation_result = {
            "status": "ok",
            "rendered_value": "37.47%",
            "answer_slots": {
                "operation_family": "ratio",
                "metric_label": "target ratio",
                "primary_value": {
                    "status": "ok",
                    "role": "primary_value",
                    "label": "target ratio",
                    "rendered_value": "37.47%",
                },
                "components_by_group": {
                    "numerator": [
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "expense input",
                            "period": "2023",
                            "raw_value": "435,542",
                            "raw_unit": "백만원",
                            "normalized_value": 435542000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "435,542백만원",
                        }
                    ],
                    "denominator": [
                        {
                            "status": "ok",
                            "role": "denominator_1",
                            "label": "profit base",
                            "period": "2023",
                            "raw_value": "11,623",
                            "raw_unit": "억원",
                            "normalized_value": 1162300000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "11,623억원",
                        }
                    ],
                },
            },
        }

        answer = self.agent._compact_ratio_answer(
            {
                "active_subtask": {"metric_label": "target ratio"},
                "resolved_calculation_trace": {
                    "calculation_result": calculation_result,
                    "calculation_operands": [],
                    "calculation_plan": {"operation": "ratio"},
                },
            },
            calculation_result,
        )

        self.assertIn("expense input 4,355.42억원", answer)
        self.assertIn("profit base 11,623억원", answer)
        self.assertNotIn("435,542백만원 /", answer)

    def test_ratio_render_prefers_complete_component_slots_over_llm_text(self) -> None:
        self.agent.llm = _StubLLM(
            CalculationRenderOutput(
                final_answer=(
                    "2023년 target ratio은 37.47%입니다. "
                    "계산: expense input 435,542백만원 / profit base 11,623억원."
                )
            )
        )
        calculation_result = {
            "status": "ok",
            "result_value": 37.4688,
            "result_unit": "%",
            "rendered_value": "37.47%",
            "answer_slots": {
                "operation_family": "ratio",
                "metric_label": "target ratio",
                "primary_value": {
                    "status": "ok",
                    "role": "primary_value",
                    "label": "target ratio",
                    "rendered_value": "37.47%",
                },
                "components_by_group": {
                    "numerator": [
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "expense input",
                            "period": "2023",
                            "raw_value": "4,355",
                            "raw_unit": "억원",
                            "rendered_value": "4,355억원",
                        }
                    ],
                    "denominator": [
                        {
                            "status": "ok",
                            "role": "denominator_1",
                            "label": "profit base",
                            "period": "2023",
                            "raw_value": "11,623",
                            "raw_unit": "억원",
                            "rendered_value": "11,623억원",
                        }
                    ],
                },
            },
        }

        rendered = self.agent._render_calculation_answer(
            {
                "query": "2023년 target ratio를 계산해 줘.",
                "active_subtask": {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "target ratio",
                    "operation_family": "ratio",
                },
                "resolved_calculation_trace": {
                    "calculation_result": calculation_result,
                    "calculation_plan": {"operation": "ratio"},
                    "calculation_operands": [],
                },
            }
        )

        self.assertIn("expense input 4,355억원", rendered["answer"])
        self.assertNotIn("435,542백만원", rendered["answer"])

    def test_ratio_full_required_candidate_rows_override_stale_dependency_numerator(self) -> None:
        state = {
            "query": "2023년 target ratio를 계산해 줘.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "Example", "year": 2023},
            "topic": "target ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "target ratio",
                "operation_family": "ratio",
                "required_operands": [
                    {
                        "label": "expense input",
                        "concept": "expense_input",
                        "role": "numerator_1",
                        "period": "2023",
                    },
                    {
                        "label": "profit base",
                        "concept": "profit_base",
                        "role": "denominator_1",
                        "period": "2023",
                    },
                ],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "expense_input",
                        "period": "2023",
                        "label": "expense input",
                        "preferred_task_id": "task_expense",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "profit_base",
                        "period": "2023",
                        "label": "profit base",
                        "preferred_task_id": "task_profit",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_expense",
                    "metric_family": "concept_lookup",
                    "metric_label": "expense input",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "expense input",
                                "concept": "expense_input",
                                "period": "2023",
                                "raw_value": "435,542",
                                "raw_unit": "백만원",
                                "normalized_value": 435542000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "435,542백만원",
                                "source_row_id": "task_output:task_expense",
                            },
                        },
                    },
                }
            ],
            "evidence_items": [
                {
                    "evidence_id": "table_ratio",
                    "source_anchor": "[Example | 2023 | table]",
                    "claim": "expense input | 2023 4,355 억원 | profit base | 2023 11,623 억원",
                    "raw_row_text": "expense input | 2023 4,355 억원 | profit base | 2023 11,623 억원",
                    "metadata": {"block_type": "table"},
                }
            ],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "partial",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
        }
        fallback_rows = [
            {
                "operand_id": "fallback_numerator",
                "evidence_id": "table_ratio",
                "source_anchor": "[Example | 2023 | table]",
                "label": "expense input",
                "concept": "expense_input",
                "raw_value": "4,355",
                "raw_unit": "억원",
                "normalized_value": 435500000000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "matched_operand_label": "expense input",
                "matched_operand_concept": "expense_input",
                "matched_operand_role": "numerator_1",
            },
            {
                "operand_id": "fallback_denominator",
                "evidence_id": "table_ratio",
                "source_anchor": "[Example | 2023 | table]",
                "label": "profit base",
                "concept": "profit_base",
                "raw_value": "11,623",
                "raw_unit": "억원",
                "normalized_value": 1162300000000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "matched_operand_label": "profit base",
                "matched_operand_concept": "profit_base",
                "matched_operand_role": "denominator_1",
            },
        ]
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: []
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: list(state["evidence_items"])
        self.agent._build_required_operands_from_candidates = lambda *_args, **_kwargs: list(fallback_rows)
        self.agent.llm = _StubLLM(OperandExtraction(coverage="missing", operands=[]))

        extracted = self.agent._extract_calculation_operands(state)
        rows = list(_resolve_runtime_calculation_trace(extracted)["calculation_operands"])
        rows_by_role = {row["matched_operand_role"]: row for row in rows}
        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertEqual(rows_by_role["numerator_1"]["raw_value"], "4,355")
        self.assertEqual(rows_by_role["denominator_1"]["raw_value"], "11,623")

    def test_ratio_complete_retrieved_context_replaces_partial_dependency_operand(self) -> None:
        state = {
            "query": "Calculate the 2023 target ratio.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "Example", "year": 2023},
            "topic": "target ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "target ratio",
                "operation_family": "ratio",
                "required_operands": [
                    {
                        "label": "expense input",
                        "concept": "expense_input",
                        "role": "numerator_1",
                        "period": "2023",
                    },
                    {
                        "label": "profit base",
                        "concept": "profit_base",
                        "role": "denominator_1",
                        "period": "2023",
                    },
                ],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "expense_input",
                        "period": "2023",
                        "label": "expense input",
                        "preferred_task_id": "task_expense",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "profit_base",
                        "period": "2023",
                        "label": "profit base",
                        "preferred_task_id": "task_profit",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_expense",
                    "metric_family": "concept_lookup",
                    "metric_label": "expense input",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "expense input",
                                "concept": "expense_input",
                                "period": "2023",
                                "raw_value": "435,542",
                                "raw_unit": "백만원",
                                "normalized_value": 435542000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "435,542백만원",
                                "source_row_id": "task_output:task_expense",
                            },
                        },
                    },
                }
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [
                (
                    Document(
                        page_content=(
                            "expense input | 2023 4,355 억원\n"
                            "profit base | 2023 11,623 억원"
                        ),
                        metadata={
                            "block_type": "table",
                            "table_source_id": "ratio-table",
                            "unit_hint": "억원",
                            "year": 2023,
                        },
                    ),
                    1.0,
                )
            ],
            "seed_retrieved_docs": [],
            "evidence_status": "partial",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
        }
        fallback_rows = [
            {
                "operand_id": "fallback_numerator",
                "evidence_id": "ev_doc_001",
                "source_anchor": "[Example | 2023 | table]",
                "label": "expense input",
                "concept": "expense_input",
                "raw_value": "4,355",
                "raw_unit": "억원",
                "normalized_value": 435500000000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "matched_operand_label": "expense input",
                "matched_operand_concept": "expense_input",
                "matched_operand_role": "numerator_1",
                "table_source_id": "ratio-table",
            },
            {
                "operand_id": "fallback_denominator",
                "evidence_id": "ev_doc_001",
                "source_anchor": "[Example | 2023 | table]",
                "label": "profit base",
                "concept": "profit_base",
                "raw_value": "11,623",
                "raw_unit": "억원",
                "normalized_value": 1162300000000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "matched_operand_label": "profit base",
                "matched_operand_concept": "profit_base",
                "matched_operand_role": "denominator_1",
                "table_source_id": "ratio-table",
            },
        ]
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: []
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []
        self.agent._build_required_operands_from_candidates = lambda *_args, **_kwargs: list(fallback_rows)
        self.agent.llm = _StubLLM(OperandExtraction(coverage="missing", operands=[]))

        extracted = self.agent._extract_calculation_operands(state)
        rows = list(_resolve_runtime_calculation_trace(extracted)["calculation_operands"])
        rows_by_role = {row["matched_operand_role"]: row for row in rows}
        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertEqual(rows_by_role["numerator_1"]["raw_value"], "4,355")
        self.assertEqual(rows_by_role["denominator_1"]["raw_value"], "11,623")

    def test_ratio_complete_retrieved_context_replaces_complete_dependency_operands(self) -> None:
        state = {
            "query": "Calculate the 2023 target ratio.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "Example", "year": 2023},
            "topic": "target ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "target ratio",
                "operation_family": "ratio",
                "required_operands": [
                    {
                        "label": "expense input",
                        "concept": "expense_input",
                        "role": "numerator_1",
                        "period": "2023",
                    },
                    {
                        "label": "profit base",
                        "concept": "profit_base",
                        "role": "denominator_1",
                        "period": "2023",
                    },
                ],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "expense_input",
                        "period": "2023",
                        "label": "expense input",
                        "preferred_task_id": "task_expense",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "profit_base",
                        "period": "2023",
                        "label": "profit base",
                        "preferred_task_id": "task_profit",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_expense",
                    "metric_family": "concept_lookup",
                    "metric_label": "expense input",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "expense input",
                                "concept": "expense_input",
                                "period": "2023",
                                "raw_value": "435,542",
                                "raw_unit": "백만원",
                                "normalized_value": 435542000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "435,542백만원",
                                "source_row_id": "task_output:task_expense",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_profit",
                    "metric_family": "concept_lookup",
                    "metric_label": "profit base",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "profit base",
                                "concept": "profit_base",
                                "period": "2023",
                                "raw_value": "11,623",
                                "raw_unit": "백만원",
                                "normalized_value": 11623000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "11,623백만원",
                                "source_row_id": "task_output:task_profit",
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [
                (
                    Document(
                        page_content=(
                            "expense input | 2023 4,355 억원\n"
                            "profit base | 2023 11,623 억원"
                        ),
                        metadata={
                            "block_type": "table",
                            "table_source_id": "ratio-table",
                            "unit_hint": "억원",
                            "year": 2023,
                        },
                    ),
                    1.0,
                )
            ],
            "seed_retrieved_docs": [],
            "evidence_status": "partial",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
        }
        fallback_rows = [
            {
                "operand_id": "fallback_numerator",
                "evidence_id": "ev_doc_001",
                "source_anchor": "[Example | 2023 | table]",
                "label": "expense input",
                "concept": "expense_input",
                "raw_value": "4,355",
                "raw_unit": "억원",
                "normalized_value": 435500000000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "matched_operand_label": "expense input",
                "matched_operand_concept": "expense_input",
                "matched_operand_role": "numerator_1",
                "table_source_id": "ratio-table",
            },
            {
                "operand_id": "fallback_denominator",
                "evidence_id": "ev_doc_001",
                "source_anchor": "[Example | 2023 | table]",
                "label": "profit base",
                "concept": "profit_base",
                "raw_value": "11,623",
                "raw_unit": "억원",
                "normalized_value": 1162300000000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "matched_operand_label": "profit base",
                "matched_operand_concept": "profit_base",
                "matched_operand_role": "denominator_1",
                "table_source_id": "ratio-table",
            },
        ]
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: []
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []
        self.agent._build_required_operands_from_candidates = lambda *_args, **_kwargs: list(fallback_rows)
        self.agent.llm = _StubLLM(OperandExtraction(coverage="missing", operands=[]))

        extracted = self.agent._extract_calculation_operands(state)
        rows = list(_resolve_runtime_calculation_trace(extracted)["calculation_operands"])
        rows_by_role = {row["matched_operand_role"]: row for row in rows}

        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertEqual(rows_by_role["numerator_1"]["raw_value"], "4,355")
        self.assertEqual(rows_by_role["denominator_1"]["raw_value"], "11,623")
        self.assertEqual(rows_by_role["numerator_1"]["raw_unit"], "억원")
        self.assertEqual(rows_by_role["denominator_1"]["raw_unit"], "억원")

    def test_ratio_coherent_table_context_overrides_mixed_table_operands(self) -> None:
        required_operands = [
            {
                "label": "expense input",
                "concept": "expense_input",
                "role": "numerator_1",
                "period": "2023",
            },
            {
                "label": "profit base",
                "concept": "profit_base",
                "role": "denominator_1",
                "period": "2023",
            },
        ]
        state = {
            "query": "Calculate the 2023 target ratio.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "Example", "year": 2023},
            "topic": "target ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "target ratio",
                "operation_family": "ratio",
                "required_operands": required_operands,
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "expense_input",
                        "period": "2023",
                        "label": "expense input",
                        "preferred_task_id": "task_expense",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    }
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_expense",
                    "metric_family": "concept_lookup",
                    "metric_label": "expense input",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "expense input",
                                "concept": "expense_input",
                                "period": "2023",
                                "raw_value": "435,542",
                                "raw_unit": "백만원",
                                "normalized_value": 435542000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "435,542백만원",
                                "source_row_id": "task_output:task_expense",
                            },
                        },
                    },
                }
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "partial",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
        }
        stale_numerator = {
            "operand_id": "stale_numerator",
            "evidence_id": "financial_table",
            "source_anchor": "[Example | 2023 | financial table]",
            "label": "expense input",
            "concept": "expense_input",
            "raw_value": "435,542",
            "raw_unit": "백만원",
            "normalized_value": 435542000000.0,
            "normalized_unit": "KRW",
            "period": "2023",
            "matched_operand_label": "expense input",
            "matched_operand_concept": "expense_input",
            "matched_operand_role": "numerator_1",
            "table_source_id": "financial-table",
        }
        ratio_numerator = {
            "operand_id": "ratio_numerator",
            "evidence_id": "ratio_table_num",
            "source_anchor": "[Example | 2023 | ratio table]",
            "label": "expense input",
            "concept": "expense_input",
            "raw_value": "4,355",
            "raw_unit": "억원",
            "normalized_value": 435500000000.0,
            "normalized_unit": "KRW",
            "period": "2023",
            "matched_operand_label": "expense input",
            "matched_operand_concept": "expense_input",
            "matched_operand_role": "numerator_1",
            "table_source_id": "ratio-table",
        }
        ratio_denominator = {
            "operand_id": "ratio_denominator",
            "evidence_id": "ratio_table_den",
            "source_anchor": "[Example | 2023 | ratio table]",
            "label": "profit base",
            "concept": "profit_base",
            "raw_value": "11,623",
            "raw_unit": "억원",
            "normalized_value": 1162300000000.0,
            "normalized_unit": "KRW",
            "period": "2023",
            "matched_operand_label": "profit base",
            "matched_operand_concept": "profit_base",
            "matched_operand_role": "denominator_1",
            "table_source_id": "ratio-table",
        }
        evidence_items = [
            {
                "evidence_id": "financial_table",
                "source_anchor": "[Example | 2023 | financial table]",
                "claim": "expense input | 2023 435,542 백만원",
                "raw_row_text": "expense input | 2023 435,542 백만원",
                "metadata": {"table_source_id": "financial-table"},
            },
            {
                "evidence_id": "ratio_table_num",
                "source_anchor": "[Example | 2023 | ratio table]",
                "claim": "expense input | 2023 4,355 억원",
                "raw_row_text": "expense input | 2023 4,355 억원",
                "metadata": {"table_source_id": "ratio-table"},
            },
            {
                "evidence_id": "ratio_table_den",
                "source_anchor": "[Example | 2023 | ratio table]",
                "claim": "profit base | 2023 11,623 억원",
                "raw_row_text": "profit base | 2023 11,623 억원",
                "metadata": {"table_source_id": "ratio-table"},
            },
        ]

        def build_required(candidate_items, **_kwargs):
            table_ids = {
                ((item.get("metadata") or {}).get("table_source_id") or "")
                for item in candidate_items
            }
            if table_ids == {"ratio-table"}:
                return [dict(ratio_numerator), dict(ratio_denominator)]
            return [dict(stale_numerator), dict(ratio_denominator)]

        self.agent._extract_structured_operands_from_reconciliation = lambda _state: []
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: list(evidence_items)
        self.agent._build_required_operands_from_candidates = build_required
        self.agent.llm = _StubLLM(OperandExtraction(coverage="missing", operands=[]))

        extracted = self.agent._extract_calculation_operands(state)
        rows = list(_resolve_runtime_calculation_trace(extracted)["calculation_operands"])
        rows_by_role = {row["matched_operand_role"]: row for row in rows}

        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertEqual(rows_by_role["numerator_1"]["raw_value"], "4,355")
        self.assertEqual(rows_by_role["denominator_1"]["raw_value"], "11,623")

    def test_growth_prior_recovery_skips_parenthesized_current_value(self) -> None:
        recovered = self.agent._recover_growth_prior_material_from_evidence(
            current_slot={
                "label": "target metric",
                "period": "2023",
                "raw_value": "(3,146,409)",
                "raw_unit": "백만원",
                "normalized_value": -3_146_409_000_000.0,
            },
            prior_slot={
                "label": "target metric",
                "period": "2022",
                "raw_value": "3,146,409",
                "raw_unit": "백만원",
                "normalized_value": 3_146_409_000_000.0,
            },
            evidence_items=[
                {
                    "claim": (
                        "2023년 target metric은 3,146,409백만원으로, "
                        "전년(2022년 1,847,775백만원) 대비 70.28% 증가했습니다."
                    ),
                    "quote_span": "",
                    "raw_row_text": "",
                }
            ],
        )

        self.assertEqual(recovered["raw_value"], "1,847,775")
        self.assertEqual(recovered["display"], "1,847,775백만원")

    def test_aggregate_subtasks_blocks_narrative_numeric_when_growth_gap_unresolved(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 target metric은 전년 대비 70.23% 증가했습니다.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 target metric 증가율을 계산하고 원인을 요약해 줘.",
            "calc_subtasks": [
                {"task_id": "task_current", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_growth", "metric_family": "concept_growth_rate", "operation_family": "growth_rate"},
                {"task_id": "task_summary", "metric_family": "narrative_summary", "operation_family": "narrative_summary"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 target metric",
                    "operation_family": "lookup",
                    "answer": "2023 target metric은 200입니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "200",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "target metric",
                                "period": "2023",
                                "raw_value": "200",
                                "normalized_value": 200.0,
                                "rendered_value": "200",
                                "source_row_id": "ev_current",
                                "source_row_ids": ["ev_current"],
                            },
                        },
                    },
                },
                {
                    "task_id": "task_growth",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "target metric growth",
                    "operation_family": "growth_rate",
                    "answer": "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다.",
                    "status": "insufficient_operands",
                    "calculation_result": {
                        "status": "insufficient_operands",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {"status": "missing", "label": "target metric growth"},
                            "current_value": {"status": "missing", "label": "target metric", "period": "2023"},
                            "prior_value": {"status": "missing", "label": "target metric", "period": "2022"},
                        },
                    },
                },
                {
                    "task_id": "task_summary",
                    "metric_family": "narrative_summary",
                    "metric_label": "summary",
                    "operation_family": "narrative_summary",
                    "answer": "2023년 target metric은 전년 대비 70.23% 증가했습니다.",
                    "status": "ok",
                    "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                },
            ],
            "evidence_items": [],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("200", updated["answer"])
        self.assertNotIn("70.23%", updated["answer"])

    def test_sum_task_consumes_sibling_lookup_outputs_before_retrieval(self) -> None:
        state = {
            "query": "삼성전자 2024 사업보고서에서 SDC와 Harman 부문의 매출 합계는 얼마인가요?",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "삼성전자", "year": 2024},
            "topic": "SDC와 Harman 부문 매출 합계",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_sum",
                "metric_label": "SDC 및 Harman 부문 매출 합계",
                "query": "삼성전자 2024 사업보고서에서 SDC와 Harman 부문의 매출 합계는 얼마인가요?",
                "operation_family": "sum",
                "required_operands": [
                    {"label": "SDC 매출액", "concept": "revenue", "role": "addend_1"},
                    {"label": "Harman 매출액", "concept": "revenue", "role": "addend_2"},
                ],
                "depends_on": ["task_2", "task_3"],
                "inputs": [
                    {
                        "role": "addend_1",
                        "concept": "revenue",
                        "period": "2024",
                        "label": "SDC 매출액",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                        "segment_label": "SDC",
                    },
                    {
                        "role": "addend_2",
                        "concept": "revenue",
                        "period": "2024",
                        "label": "Harman 매출액",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                        "segment_label": "Harman",
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2024년 SDC 매출액",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 29157800000000.0,
                        "result_unit": "억원",
                        "rendered_value": "29조 1,578억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2024년 SDC 매출액",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2024년 SDC 매출액",
                                "concept": "revenue",
                                "period": "2024",
                                "raw_value": "291,578",
                                "raw_unit": "억원",
                                "normalized_value": 29157800000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "29조 1,578억원",
                                "source_anchor": "segment_sdc_revenue",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2024년 Harman 매출액",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 14274900000000.0,
                        "result_unit": "억원",
                        "rendered_value": "14조 2,749억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2024년 Harman 매출액",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2024년 Harman 매출액",
                                "concept": "revenue",
                                "period": "2024",
                                "raw_value": "142,749",
                                "raw_unit": "억원",
                                "normalized_value": 14274900000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "14조 2,749억원",
                                "source_anchor": "segment_harman_revenue",
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        extracted = self.agent._extract_calculation_operands(state)
        merged_state = {**state, **extracted}
        trace = _resolve_runtime_calculation_trace(merged_state)
        self.assertEqual(
            [row["matched_operand_role"] for row in trace["calculation_operands"]],
            ["addend_1", "addend_2"],
        )

        planned = self.agent._plan_formula_calculation(merged_state)
        plan_trace = _resolve_runtime_calculation_trace(planned)
        self.assertEqual(plan_trace["calculation_plan"]["status"], "ok")
        self.assertEqual(plan_trace["calculation_plan"]["operation"], "add")
        self.assertEqual(len(plan_trace["calculation_plan"]["ordered_operand_ids"]), 2)

    def test_advance_subtask_records_result_and_rotates(self) -> None:
        state = {
            "query": "2023년 연결기준 부채비율과 유동비율을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "debt_ratio", "metric_label": "부채비율", "query": "2023년 연결기준 부채비율을 계산해 줘."},
                {"task_id": "task_2", "metric_family": "current_ratio", "metric_label": "유동비율", "query": "2023년 연결기준 유동비율을 계산해 줘."},
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "debt_ratio", "metric_label": "부채비율", "query": "2023년 연결기준 부채비율을 계산해 줘."},
            "subtask_results": [],
            "subtask_debug_trace": {},
            "answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "compressed_answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "selected_claim_ids": ["ev_001"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "부채비율",
                    "status": "completed",
                    "artifact_ids": ["artifact:001", "artifact:002", "artifact:003", "artifact:004"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:001",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "row_1", "label_kr": "부채총계", "value": "92228115"},
                            {"row_id": "row_2", "label_kr": "자본총계", "value": "363677865"},
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:002",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {
                            "status": "ok",
                            "operation": "divide",
                            "ordered_operand_ids": ["row_1", "row_2"],
                        }
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
                {
                    "artifact_id": "artifact:004",
                    "task_id": "task_1",
                    "kind": "reconciliation_result",
                    "payload": {"reconciliation_result": {"status": "ready"}},
                },
            ],
            "calculation_result": {"status": "stale", "rendered_value": "999%"},
            "reconciliation_result": {"status": "stale"},
        }
        updated = self.agent._advance_calculation_subtask(state)
        self.assertEqual(updated["active_subtask_index"], 1)
        self.assertEqual(updated["active_subtask"]["task_id"], "task_2")
        self.assertFalse(updated["subtask_loop_complete"])
        self.assertEqual(len(updated["subtask_results"]), 1)
        self.assertEqual(updated["subtask_results"][0]["task_id"], "task_1")
        self.assertEqual(updated["subtask_results"][0]["answer"], "2023년 연결기준 부채비율은 25.4%입니다.")
        self.assertEqual(updated["subtask_results"][0]["artifact_ids"], ["artifact:001", "artifact:002", "artifact:003", "artifact:004"])
        self.assertEqual(len(updated["subtask_results"][0]["calculation_operands"]), 2)
        self.assertEqual(updated["subtask_results"][0]["calculation_plan"]["operation"], "divide")
        self.assertEqual(updated["subtask_results"][0]["calculation_result"]["rendered_value"], "25.4%")
        self.assertEqual(updated["answer"], "")
        self.assertEqual(updated["resolved_calculation_trace"]["calculation_operands"], [])
        self.assertEqual(updated["structured_result"], {})

    def test_capture_active_subtask_does_not_reuse_sibling_aggregate_projection(self) -> None:
        state = {
            "query": "2023년 두 개념의 비율을 계산해 줘.",
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 두 번째 개념",
                "operation_family": "lookup",
                "query": "2023년 두 번째 개념을 찾아줘.",
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 첫 번째 개념",
                    "answer": "첫 번째 개념은 100억원입니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "첫 번째 개념",
                                "raw_value": "100",
                                "raw_unit": "억원",
                                "normalized_value": 10000000000,
                                "normalized_unit": "KRW",
                            },
                        },
                    },
                }
            ],
            "calculation_result": {
                "answer_slots": {
                    "operation_family": "aggregate_subtasks",
                    "subtask_results": [
                        {
                            "task_id": "task_1",
                            "metric_label": "2023년 첫 번째 개념",
                            "rendered_value": "100억원",
                        }
                    ],
                },
                "status": "partial",
            },
            "resolved_calculation_trace": {
                "calculation_operands": [],
                "calculation_plan": {"mode": "aggregate_subtasks"},
                "calculation_result": {
                    "answer_slots": {
                        "operation_family": "aggregate_subtasks",
                        "subtask_results": [
                            {
                                "task_id": "task_1",
                                "metric_label": "2023년 첫 번째 개념",
                                "rendered_value": "100억원",
                            }
                        ],
                    },
                    "status": "partial",
                },
            },
            "answer": "",
            "compressed_answer": "",
            "tasks": [],
            "artifacts": [],
        }

        captured = self.agent._capture_current_subtask_result(state)

        self.assertEqual(captured["task_id"], "task_2")
        self.assertEqual(captured["calculation_result"], {})
        self.assertEqual(captured["calculation_operands"], [])

    def test_complete_numeric_projection_replaces_stale_lookup_prefixed_ratio_answer(self) -> None:
        lookup_row = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "answer": "long component 10,121백만원",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "primary_value": {
                        "status": "ok",
                        "label": "long component",
                        "raw_value": "10,121",
                        "raw_unit": "백만원",
                        "normalized_value": 10121000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "10,121백만원",
                        "source_row_id": "ev_long",
                    }
                },
            },
        }
        ratio_result = {
            "status": "ok",
            "result_value": 42.02,
            "result_unit": "%",
            "rendered_value": "42.02%",
            "formatted_result": "target share is 42.02%.",
            "answer_slots": {
                "operation_family": "ratio",
                "metric_label": "target share",
                "primary_value": {
                    "status": "ok",
                    "rendered_value": "42.02%",
                    "normalized_value": 42.02,
                    "normalized_unit": "PERCENT",
                },
                "components_by_group": {
                    "numerator": [
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "short component",
                            "raw_value": "4,146",
                            "raw_unit": "백만원",
                            "normalized_value": 4146000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "4,146백만원",
                            "source_row_id": "ev_short",
                        },
                        {
                            "status": "ok",
                            "role": "numerator_2",
                            "label": "long component",
                            "raw_value": "10,121",
                            "raw_unit": "백만원",
                            "normalized_value": 10121000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "10,121백만원",
                            "source_row_id": "ev_long",
                        },
                        {
                            "status": "ok",
                            "role": "numerator_3",
                            "label": "bond component",
                            "raw_value": "9,490",
                            "raw_unit": "백만원",
                            "normalized_value": 9490000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "9,490백만원",
                            "source_row_id": "ev_bond",
                        },
                    ],
                    "denominator": [
                        {
                            "status": "ok",
                            "role": "denominator_1",
                            "label": "tangible base",
                            "raw_value": "52,705",
                            "raw_unit": "백만원",
                            "normalized_value": 52705000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "52,705백만원",
                            "source_row_id": "ev_tangible",
                        },
                        {
                            "status": "ok",
                            "role": "denominator_2",
                            "label": "intangible base",
                            "raw_value": "3,835",
                            "raw_unit": "백만원",
                            "normalized_value": 3835000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,835백만원",
                            "source_row_id": "ev_intangible",
                        },
                    ],
                },
            },
        }
        ratio_row = {
            "task_id": "task_ratio",
            "metric_family": "concept_ratio",
            "metric_label": "target share",
            "operation_family": "ratio",
            "answer": "target share is 42.02%.",
            "status": "ok",
            "calculation_result": ratio_result,
            "calculation_operands": [
                slot
                for slots in ratio_result["answer_slots"]["components_by_group"].values()
                for slot in slots
            ],
        }

        replacement = self.agent._complete_numeric_projection_replacement_answer(
            final_answer=(
                "long component 10,121백만원. bond component 9,490백만원. "
                "target share is 7.87%. 계산: short component / tangible base."
            ),
            ordered_results=[lookup_row, ratio_row],
            query="calculate target borrowing share",
            evidence_items=[],
        )

        self.assertIn("42.02%", replacement)
        self.assertNotIn("7.87%", replacement)

    def test_compact_ratio_answer_syncs_stale_display_from_result_value(self) -> None:
        calculation_result = {
            "status": "ok",
            "result_value": 42.01863054131083,
            "result_unit": "%",
            "rendered_value": "7.87%",
            "answer_slots": {
                "operation_family": "ratio",
                "metric_label": "target share",
                "primary_value": {
                    "status": "ok",
                    "normalized_value": 42.01863054131083,
                    "normalized_unit": "PERCENT",
                    "rendered_value": "7.87%",
                },
                "components_by_group": {
                    "numerator": [
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "short component",
                            "rendered_value": "4,146백만원",
                            "normalized_value": 4146000000.0,
                            "normalized_unit": "KRW",
                        },
                        {
                            "status": "ok",
                            "role": "numerator_2",
                            "label": "long component",
                            "rendered_value": "10,121백만원",
                            "normalized_value": 10121000000.0,
                            "normalized_unit": "KRW",
                        },
                    ],
                    "denominator": [
                        {
                            "status": "ok",
                            "role": "denominator_1",
                            "label": "tangible base",
                            "rendered_value": "52,705백만원",
                            "normalized_value": 52705000000.0,
                            "normalized_unit": "KRW",
                        },
                        {
                            "status": "ok",
                            "role": "denominator_2",
                            "label": "intangible base",
                            "rendered_value": "3,835백만원",
                            "normalized_value": 3835000000.0,
                            "normalized_unit": "KRW",
                        },
                    ],
                },
            },
        }

        answer = self.agent._compact_ratio_answer(
            {"active_subtask": {"metric_label": "target share"}},
            calculation_result,
        )

        self.assertIn("42.02%", answer)
        self.assertNotIn("7.87%", answer)
        self.assertEqual(calculation_result["rendered_value"], "42.02%")
        self.assertEqual(
            calculation_result["answer_slots"]["primary_value"]["rendered_value"],
            "42.02%",
        )

    def test_ordered_ratio_result_display_sync_updates_subtask_answer(self) -> None:
        ratio_row = {
            "task_id": "task_ratio",
            "metric_family": "concept_ratio",
            "metric_label": "target share",
            "operation_family": "ratio",
            "answer": "target share is 7.87%.",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "result_value": 42.01863054131083,
                "result_unit": "%",
                "rendered_value": "7.87%",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "target share",
                    "primary_value": {
                        "status": "ok",
                        "normalized_value": 42.01863054131083,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "7.87%",
                    },
                    "components_by_group": {
                        "numerator": [
                            {
                                "status": "ok",
                                "role": "numerator_1",
                                "label": "short component",
                                "rendered_value": "4,146백만원",
                                "normalized_value": 4146000000.0,
                                "normalized_unit": "KRW",
                            }
                        ],
                        "denominator": [
                            {
                                "status": "ok",
                                "role": "denominator_1",
                                "label": "tangible base",
                                "rendered_value": "52,705백만원",
                                "normalized_value": 52705000000.0,
                                "normalized_unit": "KRW",
                            }
                        ],
                    },
                },
            },
        }

        updated = self.agent._sync_ratio_result_displays_in_ordered_results([ratio_row])

        self.assertIn("42.02%", updated[0]["answer"])
        self.assertNotIn("7.87%", updated[0]["answer"])
        self.assertEqual(updated[0]["calculation_result"]["rendered_value"], "42.02%")
        self.assertEqual(updated[0]["calculation_result"]["formatted_result"], updated[0]["answer"])

    def test_aggregate_subtasks_joins_answers_in_task_order(self) -> None:
        state = {
            "query": "2023년 연결기준 부채비율과 유동비율을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "debt_ratio", "metric_label": "부채비율", "query": "2023년 연결기준 부채비율을 계산해 줘."},
                {"task_id": "task_2", "metric_family": "current_ratio", "metric_label": "유동비율", "query": "2023년 연결기준 유동비율을 계산해 줘."},
            ],
            "active_subtask_index": 1,
            "active_subtask": {"task_id": "task_2", "metric_family": "current_ratio", "metric_label": "유동비율", "query": "2023년 연결기준 유동비율을 계산해 줘."},
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "debt_ratio",
                    "metric_label": "부채비율",
                    "query": "2023년 연결기준 부채비율을 계산해 줘.",
                    "answer": "2023년 연결기준 부채비율은 25.4%입니다.",
                    "status": "ok",
                    "artifact_ids": ["artifact:001", "artifact:002", "artifact:003"],
                    "selected_claim_ids": ["ev_001"],
                    "runtime_evidence": [
                        {
                            "evidence_id": "ev_001",
                            "source_anchor": "[삼성전자 | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
                            "raw_row_text": "부채총계 | 92,228,115",
                        }
                    ],
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
                            "primary_value": {"rendered_value": "25.4%", "role": "primary_value"},
                        },
                    },
                    "reconciliation_result": {"status": "ready"},
                }
            ],
            "answer": "2023년 연결기준 유동비율은 258.8%입니다.",
            "compressed_answer": "2023년 연결기준 유동비율은 258.8%입니다.",
            "selected_claim_ids": ["ev_002"],
            "evidence_items": [
                {
                    "evidence_id": "ev_002",
                    "source_anchor": "[삼성전자 | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
                    "raw_row_text": "유동자산 | 137,621,922",
                }
            ],
            "tasks": [
                {
                    "task_id": "task_2",
                    "kind": "calculation",
                    "label": "유동비율",
                    "status": "completed",
                    "artifact_ids": ["artifact:011", "artifact:012", "artifact:013", "artifact:014"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:011",
                    "task_id": "task_2",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "current_assets", "label_kr": "유동자산", "value": "137621922"},
                            {"row_id": "current_liabilities", "label_kr": "유동부채", "value": "53186439"},
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:012",
                    "task_id": "task_2",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "divide"}
                    },
                },
                {
                    "artifact_id": "artifact:013",
                    "task_id": "task_2",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {"status": "ok", "rendered_value": "258.8%"}
                    },
                },
                {
                    "artifact_id": "artifact:014",
                    "task_id": "task_2",
                    "kind": "reconciliation_result",
                    "payload": {"reconciliation_result": {"status": "ready"}},
                },
            ],
            "calculation_result": {"status": "stale", "rendered_value": "999%"},
            "reconciliation_result": {"status": "stale"},
        }
        updated = self.agent._aggregate_calculation_subtasks(state)
        self.assertTrue(updated["subtask_loop_complete"])
        self.assertEqual(len(updated["subtask_results"]), 2)
        self.assertEqual(
            updated["answer"],
            "2023년 연결기준 부채비율은 25.4%입니다. 2023년 연결기준 유동비율은 258.8%입니다.",
        )
        self.assertEqual(updated["selected_claim_ids"], ["ev_001", "ev_002"])
        trace = _resolve_runtime_calculation_trace(updated)
        self.assertEqual(len(trace["calculation_operands"]), 4)
        self.assertEqual(trace["calculation_plan"]["mode"], "aggregate_subtasks")
        self.assertEqual(trace["calculation_plan"]["subtask_count"], 2)
        self.assertEqual(trace["calculation_result"]["formatted_result"], updated["answer"])
        self.assertEqual(len(updated["evidence_items"]), 2)
        self.assertEqual(
            [row["evidence_id"] for row in updated["evidence_items"]],
            ["ev_001", "ev_002"],
        )
        self.assertEqual(
            trace["calculation_result"]["derived_metrics"]["subtask_ids"],
            ["task_1", "task_2"],
        )
        self.assertEqual(
            trace["calculation_result"]["answer_slots"]["operation_family"],
            "aggregate_subtasks",
        )
        self.assertEqual(
            len(trace["calculation_result"]["answer_slots"]["subtask_results"]),
            2,
        )
        self.assertNotIn("calculation_operands", updated)
        self.assertNotIn("calculation_plan", updated)
        self.assertNotIn("calculation_result", updated)

    def test_aggregate_synthesis_prompt_uses_compact_projection_rows(self) -> None:
        capturing_llm = _CapturingLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 대상 지표는 100억원입니다.",
                    "planner_feedback": "",
                }
            )
        )
        self.agent.llm = capturing_llm
        large_claim = "supporting evidence " * 200
        state = {
            "query": "2023년 대상 지표를 알려줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"}
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"},
            "subtask_results": [],
            "answer": "2023년 대상 지표는 100억원입니다.",
            "compressed_answer": "2023년 대상 지표는 100억원입니다.",
            "selected_claim_ids": ["ev_001"],
            "evidence_items": [
                {
                    "evidence_id": "ev_001",
                    "claim": "대상 지표는 100억원입니다.",
                    "source_anchor": "source",
                }
            ],
            "calculation_operands": [
                {
                    "operand_id": "primary_value",
                    "label": "대상 지표",
                    "raw_value": "100",
                    "raw_unit": "억원",
                    "source_row_id": "ev_001",
                }
            ],
            "calculation_plan": {"status": "ok", "operation": "lookup"},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "100억원",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {
                        "status": "ok",
                        "role": "primary_value",
                        "rendered_value": "100억원",
                    },
                },
            },
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "primary_value",
                        "label": "대상 지표",
                        "raw_value": "100",
                        "raw_unit": "억원",
                        "source_row_id": "ev_001",
                    }
                ],
                "calculation_plan": {"status": "ok", "operation": "lookup"},
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "100억원",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "rendered_value": "100억원",
                        },
                    },
                },
            },
            "retrieval_debug_trace": {"large_debug_payload": large_claim},
            "runtime_evidence": [{"claim": large_claim}],
            "tasks": [],
            "artifacts": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)
        prompt_json = capturing_llm.prompt_text.split("Subtask Results JSON:\n", 1)[1]
        prompt_rows = json.loads(prompt_json)

        self.assertEqual(len(prompt_rows), 1)
        self.assertEqual(prompt_rows[0]["task_id"], "task_1")
        self.assertIn("answer_slots", prompt_rows[0]["calculation_result"])
        self.assertIn("calculation_operands", prompt_rows[0])
        self.assertNotIn("runtime_evidence", prompt_rows[0])
        self.assertNotIn("retrieval_debug_trace", capturing_llm.prompt_text)
        self.assertNotIn(large_claim, capturing_llm.prompt_text)
        self.assertLess(
            updated["subtask_debug_trace"]["aggregate_synthesis_prompt"]["input_json_chars"],
            len(json.dumps([state], ensure_ascii=False)),
        )

    def test_aggregate_subtasks_dedupes_nested_operand_mirrors(self) -> None:
        projection = self.agent._build_aggregate_calculation_projection(
            [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 연구개발비용 총액",
                    "answer": "2023년 연결 연구개발비용 총액은 28,352,769 백만원입니다.",
                    "status": "ok",
                    "calculation_operands": [
                        {
                            "operand_id": "primary_value",
                            "label": "연구개발비용",
                            "raw_value": "28,352,769",
                            "raw_unit": "백만원",
                            "source_row_id": "ev_001",
                            "source_row_ids": ["ev_001"],
                        }
                    ],
                    "calculation_plan": {"status": "ok", "operation": "lookup"},
                    "calculation_result": {"status": "ok", "rendered_value": "28,352,769백만원"},
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "질문 관련 배경/영향 설명",
                    "answer": "Harman은 SDV 전환에 대응합니다.",
                    "status": "ok",
                    "calculation_operands": [
                        {
                            "task_id": "task_1",
                            "metric_family": "concept_lookup",
                            "metric_label": "2023년 연구개발비용 총액",
                            "operand_id": "primary_value",
                            "label": "연구개발비용",
                            "raw_value": "28,352,769",
                            "raw_unit": "백만원",
                            "source_row_id": "ev_001",
                            "source_row_ids": ["ev_001"],
                        }
                    ],
                    "calculation_plan": {"status": "ok", "mode": "aggregate_subtasks"},
                    "calculation_result": {"status": "ok", "rendered_value": "Harman은 SDV 전환에 대응합니다."},
                },
            ],
            "2023년 연결 연구개발비용 총액은 28,352,769백만원입니다. Harman은 SDV 전환에 대응합니다.",
        )

        self.assertEqual(len(projection["calculation_operands"]), 1)
        self.assertEqual(projection["calculation_result"]["source_row_ids"], ["ev_001"])

    def test_aggregate_projection_drops_null_source_id_surfaces(self) -> None:
        projection = self.agent._build_aggregate_calculation_projection(
            [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 커머스 매출액",
                    "answer": "2023년 커머스 매출액은 2,546,649백만원입니다.",
                    "status": "ok",
                    "calculation_operands": [
                        {
                            "operand_id": "primary_value",
                            "label": "커머스 매출액",
                            "raw_value": "2,546,649",
                            "raw_unit": "백만원",
                            "source_row_id": None,
                            "source_row_ids": [None, "None", "ev_001"],
                        }
                    ],
                    "calculation_plan": {"status": "ok", "operation": "lookup"},
                    "calculation_result": {"status": "ok", "rendered_value": "2,546,649백만원"},
                }
            ],
            "2023년 커머스 매출액은 2,546,649백만원입니다.",
        )

        self.assertEqual(projection["calculation_result"]["source_row_ids"], ["ev_001"])

    def test_aggregate_growth_narrative_replaces_stale_missing_context(self) -> None:
        self.agent.llm = None
        state = {
            "query": (
                "2023년 지역 시장 판매대수의 전년 대비 성장률을 계산하고, "
                "정책 대응 필요성을 요약해 줘."
            ),
            "calc_subtasks": [
                {
                    "task_id": "task_1",
                    "metric_family": "generic_numeric",
                    "metric_label": "지역 시장 판매대수",
                    "operation_family": "growth_rate",
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "질문 관련 배경/영향 설명",
                    "operation_family": "narrative_summary",
                },
            ],
            "active_subtask_index": 1,
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "metric_label": "질문 관련 배경/영향 설명",
                "operation_family": "narrative_summary",
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "generic_numeric",
                    "metric_label": "지역 시장 판매대수",
                    "answer": (
                        "2023년 지역 시장 판매대수는 2022년 78.1만 대에서 2023년 87.0만 대로 증가하여 "
                        "전년 대비 11.5% 증가했습니다. 정책 대응 필요성에 대한 정보는 제공되지 않았습니다."
                    ),
                    "status": "ok",
                    "calculation_plan": {"status": "ok", "operation": "growth_rate"},
                    "calculation_result": {
                        "status": "ok",
                        "formatted_result": (
                            "2023년 지역 시장 판매대수는 2022년 78.1만 대에서 2023년 87.0만 대로 증가하여 "
                            "전년 대비 11.5% 증가했습니다. 정책 대응 필요성에 대한 정보는 제공되지 않았습니다."
                        ),
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "지역 시장 판매대수",
                                "normalized_value": 11.5,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "11.5%",
                            },
                            "current_value": {
                                "status": "ok",
                                "role": "current_value",
                                "label": "2023년 지역 시장 판매대수",
                                "period": "2023년",
                                "raw_value": "87.0",
                                "raw_unit": "만 대",
                                "normalized_value": 870000.0,
                                "normalized_unit": "COUNT",
                                "rendered_value": "87.0만 대",
                            },
                            "prior_value": {
                                "status": "ok",
                                "role": "prior_value",
                                "label": "2022년 지역 시장 판매대수",
                                "period": "2023년",
                                "raw_value": "87.0",
                                "raw_unit": "만 대",
                                "normalized_value": 870000.0,
                                "normalized_unit": "COUNT",
                                "rendered_value": "87.0만 대",
                            },
                        },
                    },
                }
            ],
            "answer": "정책 변화에 적극적인 대응이 필요한 상황입니다.",
            "compressed_answer": "정책 변화에 적극적인 대응이 필요한 상황입니다.",
            "selected_claim_ids": ["ev_policy"],
            "evidence_items": [
                {
                    "evidence_id": "ev_prior_sales",
                    "claim": "2022년 지역 시장 판매대수는 78.1만 대였습니다.",
                    "quote_span": "2022년 지역 시장 판매대수는 78.1만 대",
                    "support_level": "direct",
                },
                {
                    "evidence_id": "ev_policy",
                    "claim": "정책 변화에 적극적인 대응이 필요한 상황입니다.",
                    "support_level": "direct",
                }
            ],
            "tasks": [],
            "artifacts": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("11.5%", updated["answer"])
        self.assertIn("78.1", updated["answer"])
        self.assertIn("지역 시장 판매대수는 87.0만 대", updated["answer"])
        self.assertIn("정책 변화에 적극적인 대응이 필요한 상황", updated["answer"])
        self.assertNotIn("제공되지 않았", updated["answer"])

    def test_aggregate_subtasks_does_not_use_narrative_text_for_numeric_gaps(self) -> None:
        self.agent.llm = None
        state = {
            "query": "2023년 총 영업비용과 영업비용률을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_3", "metric_family": "concept_lookup", "metric_label": "2023년 매출원가"},
                {"task_id": "task_4", "metric_family": "concept_lookup", "metric_label": "2023년 판매비와관리비"},
                {"task_id": "task_1", "metric_family": "concept_ratio", "metric_label": "영업비용률"},
                {"task_id": "task_2", "metric_family": "narrative_summary", "metric_label": "질문 관련 배경/영향 설명"},
            ],
            "active_subtask_index": 3,
            "active_subtask": {"task_id": "task_2", "metric_family": "narrative_summary", "metric_label": "질문 관련 배경/영향 설명"},
            "subtask_results": [
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 매출원가",
                    "answer": "2023년 매출원가 계산에 필요한 값(2023년 매출원가)을 문서 근거에서 충분히 확인하지 못해 계산할 수 없습니다.",
                    "status": "partial",
                    "calculation_result": {"status": "partial", "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []}},
                },
                {
                    "task_id": "task_4",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 판매비와관리비",
                    "answer": "2023년 판매비와관리비 계산에 필요한 값(2023년 판매비와관리비)을 문서 근거에서 충분히 확인하지 못해 계산할 수 없습니다.",
                    "status": "partial",
                    "calculation_result": {"status": "partial", "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []}},
                },
                {
                    "task_id": "task_1",
                    "metric_family": "concept_ratio",
                    "metric_label": "영업비용률",
                    "answer": "",
                    "status": "insufficient_operands",
                    "calculation_result": {
                        "status": "insufficient_operands",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "metric_label": "영업비용률",
                            "primary_value": {"status": "missing", "role": "primary_value", "label": "영업비용률"},
                        },
                    },
                },
            ],
            "answer": "매출원가는 129,179,183 백만원입니다. 판매비와관리비는 18,357,495 백만원입니다. 총 영업비용은 147,536,678 백만원입니다. 매출액 대비 영업비용률은 약 90.70%입니다.",
            "compressed_answer": "매출원가는 129,179,183 백만원입니다. 판매비와관리비는 18,357,495 백만원입니다. 총 영업비용은 147,536,678 백만원입니다. 매출액 대비 영업비용률은 약 90.70%입니다.",
            "plan_loop_count": 2,
            "selected_claim_ids": ["ev_001"],
            "tasks": [],
            "artifacts": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)
        self.assertEqual(updated["answer"], "질문에 필요한 수치를 끝내 충분히 확보하지 못했습니다.")
        self.assertIn("매출원가", updated["planner_feedback"])
        self.assertNotIn("90.70%", updated["answer"])

    def test_aggregate_subtasks_prefers_complete_numeric_result_over_narrative_summary(self) -> None:
        self.agent.llm = None
        state = {
            "query": "2023년 연결기준 판매비와관리비를 포함한 비용률을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_ratio", "metric_label": "비용률", "operation_family": "ratio"},
                {"task_id": "task_2", "metric_family": "narrative_summary", "metric_label": "질문 관련 배경/영향 설명", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 1,
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "metric_label": "질문 관련 배경/영향 설명",
                "operation_family": "narrative_summary",
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_ratio",
                    "metric_label": "비용률",
                    "answer": "90.7%",
                    "status": "ok",
                    "calculation_plan": {"status": "ok", "operation": "ratio"},
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "90.7%",
                        "formatted_result": "90.7%",
                        "source_row_ids": ["task_output:task_3", "task_output:task_4", "task_output:task_5"],
                        "answer_slots": {
                            "operation_family": "ratio",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "rendered_value": "90.7%",
                                "normalized_value": 90.7,
                                "normalized_unit": "PERCENT",
                            },
                        },
                    },
                }
            ],
            "answer": "서술형 근거 문장이 277.94%를 잘못 말합니다.",
            "compressed_answer": "서술형 근거 문장이 277.94%를 잘못 말합니다.",
            "selected_claim_ids": ["narrative_ev"],
            "tasks": [],
            "artifacts": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        trace = _resolve_runtime_calculation_trace(updated)
        self.assertEqual(updated["answer"], "90.7%")
        self.assertEqual(trace["calculation_result"]["formatted_result"], "90.7%")
        self.assertNotIn("277.94%", updated["answer"])

    def test_supported_aggregate_answer_ignores_narrative_summary_projection(self) -> None:
        answer = self.agent._supported_aggregate_subtask_answer(
            [
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "질문 관련 배경/영향 설명",
                    "answer": "서술형 보존 문장이 5,037,579 백만원을 말합니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "서술형 보존 문장이 5,037,579 백만원을 말합니다.",
                        "formatted_result": "서술형 보존 문장이 5,037,579 백만원을 말합니다.",
                        "answer_slots": {"operation_family": "aggregate_subtasks"},
                    },
                }
            ]
        )

        self.assertEqual(answer, "")

    def test_aggregate_answer_refreshes_when_supported_row_answer_is_stale(self) -> None:
        self.agent.llm = None
        ratio_result = {
            "status": "ok",
            "result_value": 13.771463862847872,
            "result_unit": "%",
            "rendered_value": "13.77%",
            "answer_slots": {
                "operation_family": "ratio",
                "metric_label": "segment revenue ratio",
                "primary_value": {"status": "ok", "rendered_value": "13.77%"},
                "components_by_group": {
                    "numerator": [
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "segment revenue",
                            "raw_value": "22,401",
                            "raw_unit": "million",
                            "normalized_value": 22401.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "22,401 million",
                            "source_row_id": "row_segment",
                        }
                    ],
                    "denominator": [
                        {
                            "status": "ok",
                            "role": "denominator_1",
                            "label": "total revenue",
                            "raw_value": "162,664",
                            "raw_unit": "million",
                            "normalized_value": 162664.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "162,664 million",
                            "source_row_id": "row_total",
                        }
                    ],
                },
            },
        }
        state = {
            "query": "Calculate segment revenue ratio.",
            "calc_subtasks": [
                {"task_id": "task_ratio", "metric_family": "concept_ratio", "operation_family": "ratio"},
                {"task_id": "aggregate", "metric_family": "aggregate", "operation_family": "aggregate_subtasks"},
            ],
            "subtask_results": [
                {
                    "task_id": "aggregate",
                    "metric_family": "aggregate",
                    "operation_family": "aggregate_subtasks",
                    "answer": "segment revenue ratio is 100%.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "segment revenue ratio is 100%.",
                        "formatted_result": "segment revenue ratio is 100%.",
                        "subtask_results": [
                            {
                                "task_id": "task_ratio",
                                "metric_family": "concept_ratio",
                                "operation_family": "ratio",
                                "answer": "segment revenue ratio is 100%.",
                                "status": "ok",
                                "calculation_result": ratio_result,
                            }
                        ],
                        "answer_slots": {"operation_family": "aggregate_subtasks"},
                    },
                },
                {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "segment revenue ratio",
                    "operation_family": "ratio",
                    "answer": "segment revenue ratio is 100%.",
                    "status": "ok",
                    "calculation_plan": {"status": "ok", "operation": "ratio"},
                    "calculation_result": ratio_result,
                },
            ],
            "evidence_items": [],
            "runtime_evidence": [],
            "tasks": [],
            "artifacts": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)
        trace = _resolve_runtime_calculation_trace(updated)

        self.assertIn("13.77%", updated["answer"])
        self.assertNotIn("100%", updated["answer"])
        self.assertIn("13.77%", trace["calculation_result"]["formatted_result"])

    def test_aggregate_subtasks_prefers_lookup_list_over_raw_narrative_table(self) -> None:
        self.agent.llm = None
        state = {
            "query": "2023년 여러 금액을 찾아 요약해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "항목 A", "operation_family": "lookup"},
                {"task_id": "task_2", "metric_family": "concept_lookup", "metric_label": "항목 B", "operation_family": "lookup"},
                {"task_id": "task_3", "metric_family": "narrative_summary", "metric_label": "질문 관련 배경/영향 설명", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 2,
            "active_subtask": {
                "task_id": "task_3",
                "metric_family": "narrative_summary",
                "metric_label": "질문 관련 배경/영향 설명",
                "operation_family": "narrative_summary",
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "항목 A",
                    "answer": "100천원",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "100천원",
                        "formatted_result": "100천원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "항목 A",
                                "rendered_value": "100천원",
                                "normalized_value": 100000.0,
                                "normalized_unit": "KRW",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "항목 B",
                    "answer": "(200)천원",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "(200)천원",
                        "formatted_result": "(200)천원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "항목 B",
                                "rendered_value": "(200)천원",
                                "normalized_value": 200000.0,
                                "normalized_unit": "KRW",
                            },
                        },
                    },
                },
            ],
            "answer": "원문 표 전체 999천원 888천원",
            "compressed_answer": "원문 표 전체 999천원 888천원",
            "selected_claim_ids": ["narrative_ev"],
            "tasks": [],
            "artifacts": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["answer"], "항목 A 100천원, 항목 B 200천원입니다.")
        self.assertNotIn("999천원", updated["answer"])

    def test_aggregate_subtasks_recovers_failed_lookup_from_sibling_table_evidence(self) -> None:
        self.agent.llm = None
        state = {
            "query": "2023년 재고자산평가손실, 환입, 폐기손실 금액을 찾아 요약해 줘.",
            "calc_subtasks": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "재고자산평가손실",
                    "operation_family": "lookup",
                    "sibling_lookup_surfaces": ["재고자산평가손실환입", "재고자산폐기손실"],
                    "required_operands": [
                        {
                            "label": "재고자산평가손실",
                            "concept": "inventory_valuation_loss",
                            "role": "operand",
                            "aliases": [],
                            "surface_contract": {"positive": ["재고자산평가손실"]},
                        }
                    ],
                },
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "재고자산평가손실환입",
                    "operation_family": "lookup",
                    "sibling_lookup_surfaces": ["재고자산평가손실", "재고자산폐기손실"],
                    "required_operands": [
                        {
                            "label": "재고자산평가손실환입",
                            "concept": "inventory_valuation_loss_reversal",
                            "role": "operand",
                            "aliases": [],
                            "surface_contract": {"positive": ["재고자산평가손실환입"]},
                        }
                    ],
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "재고자산폐기손실",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "재고자산폐기손실",
                            "concept": "inventory_disposal_loss",
                            "role": "operand",
                        }
                    ],
                },
            ],
            "active_subtask_index": 2,
            "active_subtask": {"task_id": "task_3", "operation_family": "lookup"},
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "재고자산평가손실",
                    "operation_family": "lookup",
                    "status": "insufficient_operands",
                    "answer": "재고자산평가손실 계산에 필요한 값을 확인하지 못했습니다.",
                    "calculation_result": {},
                },
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "재고자산평가손실환입",
                    "operation_family": "lookup",
                    "status": "insufficient_operands",
                    "answer": "재고자산평가손실환입 계산에 필요한 값을 확인하지 못했습니다.",
                    "calculation_result": {},
                },
            ],
            "calculation_result": {
                "status": "ok",
                "rendered_value": "25,163,510천원",
                "formatted_result": "재고자산폐기손실 25,163,510천원",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {
                        "status": "ok",
                        "label": "재고자산폐기손실",
                        "concept": "inventory_disposal_loss",
                        "raw_value": "25,163,510",
                        "raw_unit": "천원",
                        "normalized_value": 25163510000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "25,163,510천원",
                    },
                },
            },
            "answer": "재고자산폐기손실 25,163,510천원",
            "evidence_items": [
                {
                    "evidence_id": "ev_table",
                    "source_anchor": "[셀트리온 | 2023 | 주석]",
                    "metadata": {
                        "year": 2023,
                        "statement_type": "notes",
                        "unit_hint": "천원",
                        "table_value_labels_text": (
                            "재고자산평가손실 2,526,280\n"
                            "재고자산평가손실환입 (48,885,812)\n"
                            "재고자산폐기손실 25,163,510"
                        ),
                    },
                }
            ],
            "tasks": [],
            "artifacts": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(
            updated["answer"],
            "재고자산평가손실 2,526,280천원, 재고자산평가손실환입 48,885,812천원, 재고자산폐기손실 25,163,510천원입니다.",
        )

    def test_lookup_gap_check_handles_aggregate_wrapped_lookup_rows(self) -> None:
        rows = [
            {
                "task_id": "task_2",
                "metric_family": "concept_lookup",
                "metric_label": "재고자산평가손실환입",
                "status": "partial",
                "answer": "재고자산평가손실환입 계산에 필요한 값(재고자산평가손실환입)을 문서 근거에서 충분히 확인하지 못했습니다.",
                "calculation_result": {
                    "status": "partial",
                    "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []},
                },
            },
            {
                "task_id": "task_6",
                "metric_family": "concept_ratio",
                "metric_label": "매출원가 대비 재고자산평가손실(환입) 비중",
                "status": "ok",
                "answer": "재고자산평가손실(환입) 등은 5,037,579백만원입니다.",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "매출원가 대비 재고자산평가손실(환입) 비중",
                            "normalized_value": 2.79,
                            "normalized_unit": "PERCENT",
                            "rendered_value": "2.79%",
                        },
                        "components_by_role": {
                            "numerator_1": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "재고자산평가손실(환입) 등",
                                    "period": "2023",
                                    "raw_value": "5,037,579",
                                    "raw_unit": "백만원",
                                    "normalized_value": 5037579000000.0,
                                    "normalized_unit": "KRW",
                                    "rendered_value": "5,037,579백만원",
                                }
                            ]
                        },
                    },
                },
            },
        ]

        self.assertTrue(self.agent._lookup_gap_is_satisfied_by_sibling_slots(rows[0], rows))
        self.assertEqual(self.agent._infer_planner_feedback_from_answer_slots(rows), "")

    def test_capture_current_subtask_result_prefers_live_active_trace_over_stale_artifact(self) -> None:
        state = {
            "query": "2023년 연결기준 영업비용률을 계산해 줘.",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "영업비용률",
                "query": "2023년 연결기준 영업비용률을 계산해 줘.",
            },
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "영업비용률",
                    "status": "completed",
                    "artifact_ids": ["artifact:401", "artifact:402", "artifact:403"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:401",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"operand_id": "stale_op", "label": "stale", "raw_value": "0", "raw_unit": "%"}
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:402",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "ratio"}
                    },
                },
                {
                    "artifact_id": "artifact:403",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {
                            "status": "ok",
                            "rendered_value": "stale",
                            "answer_slots": {
                                "operation_family": "ratio",
                                "primary_value": {"status": "missing", "label": "영업비용률"},
                            },
                        }
                    },
                },
            ],
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "rev",
                        "label": "매출액",
                        "raw_value": "162,663,579",
                        "raw_unit": "백만원",
                        "normalized_value": 162663579000000.0,
                        "normalized_unit": "KRW",
                    }
                ],
                "calculation_plan": {"status": "ok", "operation": "ratio"},
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "90.7%",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {
                            "status": "ok",
                            "label": "영업비용률",
                            "raw_value": "90.7",
                            "raw_unit": "%",
                            "normalized_value": 90.7,
                            "normalized_unit": "PERCENT",
                            "rendered_value": "90.7%",
                        },
                    },
                },
            },
            "answer": "2023년 연결기준 영업비용률은 90.7%입니다.",
            "compressed_answer": "2023년 연결기준 영업비용률은 90.7%입니다.",
            "reconciliation_result": {"status": "ready"},
        }

        current = self.agent._capture_current_subtask_result(state)

        self.assertEqual(current["calculation_result"]["rendered_value"], "90.7%")
        self.assertEqual(
            current["calculation_result"]["answer_slots"]["primary_value"]["rendered_value"],
            "90.7%",
        )
        self.assertEqual(current["calculation_operands"][0]["operand_id"], "rev")

    def test_capture_current_subtask_result_ignores_legacy_top_level_calculation_projection(self) -> None:
        state = {
            "query": "calculate ratio",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "ratio",
                "operation_family": "ratio",
            },
            "answer": "The ratio is 25.4%.",
            "compressed_answer": "The ratio is 25.4%.",
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "calculation_operands": [{"operand_id": "legacy"}],
            "calculation_plan": {"status": "ok", "operation": "ratio"},
            "calculation_result": {"status": "ok", "rendered_value": "25.4%"},
            "reconciliation_result": {},
        }

        current = self.agent._capture_current_subtask_result(state)

        self.assertEqual(current["calculation_operands"], [])
        self.assertEqual(current["calculation_plan"], {})
        self.assertEqual(current["calculation_result"], {})
        self.assertEqual(current["status"], "ok")

    def test_capture_current_subtask_result_promotes_single_lookup_prose_value(self) -> None:
        state = {
            "query": "2023년 연결 연구개발비용 총액을 추출하고, Harman 부문 기술 초점을 요약해 줘.",
            "answer": "2023년 연결 연구개발비용 총액은 28,352,769 백만원입니다.",
            "compressed_answer": "2023년 연결 연구개발비용 총액은 28,352,769 백만원입니다.",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 연결 연구개발비용 총액",
                "query": "2023년 연결 연구개발비용 총액을 찾아 줘.",
                "operation_family": "lookup",
            },
            "selected_claim_ids": ["ev_001"],
            "evidence_items": [],
            "retrieved_docs": [
                (
                    Document(
                        page_content="연구개발비용 계 | 28,352,769 | ※ 연결 누계기준입니다.",
                        metadata={
                            "company": "삼성전자",
                            "year": 2023,
                            "section_path": "II. 사업의 내용 > 6. 주요계약 및 연구개발활동",
                        },
                    ),
                    0.9,
                )
            ],
            "seed_retrieved_docs": [],
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "reconciliation_result": {},
        }

        current = self.agent._capture_current_subtask_result(state)

        self.assertEqual(current["status"], "ok")
        self.assertEqual(current["calculation_result"]["answer_slots"]["operation_family"], "lookup")
        self.assertEqual(
            current["calculation_result"]["answer_slots"]["primary_value"]["rendered_value"],
            "28,352,769백만원",
        )
        self.assertEqual(len(current["calculation_operands"]), 1)
        self.assertEqual(current["calculation_operands"][0]["rendered_value"], "28,352,769백만원")
        self.assertTrue(current["calculation_operands"][0]["source_row_ids"])

    def test_capture_current_subtask_result_does_not_promote_percent_prose_for_krw_lookup(self) -> None:
        state = {
            "query": "삼성전자의 2023년 영업이익을 찾아줘.",
            "answer": "삼성전자의 2023년 연결 기준 영업이익률은 2.5361%입니다.",
            "compressed_answer": "삼성전자의 2023년 연결 기준 영업이익률은 2.5361%입니다.",
            "active_subtask": {
                "task_id": "task_3",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 영업이익",
                "query": "2023년 영업이익을 찾아줘.",
                "operation_family": "lookup",
                "required_operands": [
                    {
                        "label": "영업이익",
                        "concept": "operating_income",
                        "aliases": ["영업손익"],
                        "role": "primary_value",
                        "unit_family": "KRW",
                        "required": True,
                    }
                ],
            },
            "selected_claim_ids": ["ev_margin"],
            "evidence_items": [],
            "retrieved_docs": [
                (
                    Document(
                        page_content="영업이익률 | 2023 | 2.5361%",
                        metadata={"company": "삼성전자", "year": 2023},
                    ),
                    0.9,
                )
            ],
            "seed_retrieved_docs": [],
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "reconciliation_result": {},
        }

        current = self.agent._capture_current_subtask_result(state)

        self.assertEqual(current["status"], "ok")
        self.assertEqual(current["calculation_operands"], [])
        self.assertNotIn("primary_value", current["calculation_result"].get("answer_slots") or {})

    def test_capture_current_subtask_result_strips_formula_open_paren_from_prose_value(self) -> None:
        state = {
            "query": "삼성전자의 2023년 영업이익을 찾아줘.",
            "answer": "영업이익률은 (6,566,976 백만원 / 258,935,494 백만원) * 100입니다.",
            "compressed_answer": "영업이익률은 (6,566,976 백만원 / 258,935,494 백만원) * 100입니다.",
            "active_subtask": {
                "task_id": "task_3",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 영업이익",
                "query": "2023년 영업이익을 찾아줘.",
                "operation_family": "lookup",
                "required_operands": [
                    {
                        "label": "영업이익",
                        "concept": "operating_income",
                        "aliases": ["영업손익"],
                        "role": "primary_value",
                        "unit_family": "KRW",
                        "required": True,
                    }
                ],
            },
            "selected_claim_ids": ["ev_income"],
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "reconciliation_result": {},
        }

        current = self.agent._capture_current_subtask_result(state)

        slot = current["calculation_result"]["answer_slots"]["primary_value"]
        self.assertEqual(slot["raw_value"], "6,566,976")
        self.assertEqual(slot["normalized_unit"], "KRW")
        self.assertEqual(slot["rendered_value"], "6,566,976백만원")

    def test_capture_current_subtask_result_prefers_deterministic_dividend_hybrid_answer(self) -> None:
        state = {
            "query": "2023년 연결 현금흐름표에서 '배당금 지급'으로 유출된 현금 규모를 찾고, 사업보고서의 '배당에 관한 사항'을 바탕으로 2024~2026년 주주환원 정책을 요약해 줘.",
            "answer": "2023년 연결 현금흐름표상 배당금 지급으로 유출된 현금은 9조 8,094억원입니다.",
            "compressed_answer": "2023년 연결 현금흐름표상 배당금 지급으로 유출된 현금은 9조 8,094억원입니다.",
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "metric_label": "질문 관련 배경/영향 설명",
                "query": "2023년 연결 현금흐름표에서 '배당금 지급'으로 유출된 현금 규모를 찾고, 사업보고서의 '배당에 관한 사항'을 바탕으로 2024~2026년 주주환원 정책을 요약해 줘.",
                "operation_family": "narrative_summary",
            },
            "evidence_items": [
                {
                    "evidence_id": "ev_001",
                    "source_anchor": "[삼성전자 | 2023 | III. 재무에 관한 사항 > 6. 배당에 관한 사항]",
                    "claim": "2023년(제55기) 연결 현금흐름표에서 '배당금 지급'으로 유출된 현금 규모는 9조 8,094억원입니다.",
                    "quote_span": "현금배당금총액(백만원) | 9,809,438",
                    "metadata": {
                        "section_path": "III. 재무에 관한 사항 > 6. 배당에 관한 사항",
                    },
                },
                {
                    "evidence_id": "ev_002",
                    "source_anchor": "[삼성전자 | 2023 | III. 재무에 관한 사항 > 6. 배당에 관한 사항]",
                    "claim": "삼성전자는 2024년부터 2026년까지 3년간 잉여현금흐름의 50%를 재원으로 연간 9.8조원 수준의 정규배당을 유지하고, 정규배당 이후 잔여 재원이 발생하면 추가로 환원할 계획입니다.",
                    "quote_span": "2024년부터 2026년까지 3년간 발생하는 잉여현금흐름의 50%를 재원으로 활용하여 연간 9.8조원 수준의 정규배당을 유지하되, 정규배당 이후에도 잔여 재원이 발생하는 경우에 추가로 환원할 계획입니다.",
                    "metadata": {
                        "section_path": "III. 재무에 관한 사항 > 6. 배당에 관한 사항",
                    },
                },
                {
                    "evidence_id": "ev_003",
                    "source_anchor": "[삼성전자 | 2023 | IV. 이사의 경영진단 및 분석의견]",
                    "claim": "당기말 현재 당사 차입금은 12조 6,859억원이며, 당사의 유동성은 당기 영업활동 현금흐름으로 44조 1,374억원이 유입되었고, 배당금 지급 9조 8,645억원 등이 유출되었습니다.",
                    "quote_span": "당기말 현재 당사 차입금은 12조 6,859억원이며, 배당금 지급 9조 8,645억원 등이 유출되었습니다.",
                    "metadata": {
                        "section_path": "IV. 이사의 경영진단 및 분석의견 > 유동성 및 자금조달",
                    },
                },
            ],
            "selected_claim_ids": ["ev_001", "ev_002"],
            "tasks": [],
            "artifacts": [],
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "reconciliation_result": {},
        }

        current = self.agent._capture_current_subtask_result(state)

        self.assertIn("9조 8,645억원", current["answer"])
        self.assertIn("2024년부터 2026년까지", current["answer"])
        self.assertEqual(current["selected_claim_ids"], ["ev_003", "ev_002"])

    def test_project_runtime_calculation_trace_prefers_ledger_trace_over_stale_top_level(self) -> None:
        state = {
            "answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "compressed_answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "active_subtask": {"task_id": "task_1"},
            "subtask_results": [],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "부채비율",
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
                        "calculation_result": {
                            "status": "ok",
                            "rendered_value": "25.4%",
                            "answer_slots": {
                                "operation_family": "ratio",
                                "primary_value": {"status": "ok", "rendered_value": "25.4%"},
                            },
                        }
                    },
                },
            ],
            "calculation_operands": [{"row_id": "stale"}],
            "calculation_plan": {"status": "stale"},
            "calculation_result": {"status": "stale", "rendered_value": "999%"},
        }

        projected = self.agent._project_runtime_calculation_trace(state)

        self.assertEqual(len(projected["calculation_operands"]), 2)
        self.assertEqual(projected["calculation_plan"]["operation"], "divide")
        self.assertEqual(projected["calculation_result"]["rendered_value"], "25.4%")
        self.assertEqual(projected["runtime_projection"]["source"], "task_artifact_ledger")
        self.assertFalse(projected["runtime_projection"]["legacy_fallback"])

    def test_project_runtime_calculation_trace_prefers_ledger_trace_over_stale_resolved_trace(self) -> None:
        state = {
            "answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "compressed_answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "active_subtask": {"task_id": "task_1"},
            "subtask_results": [],
            "resolved_calculation_trace": {
                "calculation_operands": [{"row_id": "stale"}],
                "calculation_plan": {"operation": "stale"},
                "calculation_result": {"status": "stale", "rendered_value": "999%"},
            },
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "부채비율",
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
                        "calculation_result": {
                            "status": "ok",
                            "rendered_value": "25.4%",
                            "answer_slots": {
                                "operation_family": "ratio",
                                "primary_value": {"status": "ok", "rendered_value": "25.4%"},
                            },
                        }
                    },
                },
            ],
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        projected = self.agent._project_runtime_calculation_trace(state)

        self.assertEqual(len(projected["calculation_operands"]), 2)
        self.assertEqual(projected["calculation_plan"]["operation"], "divide")
        self.assertEqual(projected["calculation_result"]["rendered_value"], "25.4%")
        self.assertEqual(projected["runtime_projection"]["source"], "task_artifact_ledger")

    def test_capture_current_subtask_result_ignores_stale_aggregate_resolved_trace(self) -> None:
        state = {
            "query": "2023년 시설투자(CAPEX) 총액을 찾아 줘.",
            "answer": "2023년 시설투자(CAPEX) 총액은 53조 1,139억원입니다.",
            "compressed_answer": "2023년 시설투자(CAPEX) 총액은 53조 1,139억원입니다.",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 시설투자(CAPEX) 총액",
                "query": "2023년 시설투자(CAPEX) 총액을 찾아 줘.",
            },
            "resolved_calculation_trace": {
                "calculation_operands": [],
                "calculation_plan": {"status": "ok", "mode": "aggregate_subtasks", "subtask_count": 2},
                "calculation_result": {
                    "status": "partial",
                    "rendered_value": "stale aggregate",
                    "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []},
                },
            },
            "calculation_operands": [
                {
                    "operand_id": "capex_2023",
                    "label": "2023 시설투자(CAPEX)",
                    "raw_value": "531,139",
                    "raw_unit": "억원",
                    "normalized_value": 53113900000000.0,
                    "normalized_unit": "KRW",
                    "matched_operand_role": "current_period",
                    "matched_operand_concept": "capital_expenditure_total",
                }
            ],
            "calculation_plan": {"status": "ok", "operation": "lookup", "mode": "single_value"},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "53조 1,139억원",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {
                        "status": "ok",
                        "label": "2023 시설투자(CAPEX)",
                        "concept": "capital_expenditure_total",
                        "period": "2023년",
                        "raw_value": "531,139",
                        "raw_unit": "억원",
                        "normalized_value": 53113900000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "53조 1,139억원",
                    }
                },
            },
            "tasks": [],
            "artifacts": [],
        }

        current = self.agent._capture_current_subtask_result(state)

        self.assertEqual(current["calculation_plan"]["operation"], "lookup")
        self.assertEqual(current["calculation_result"]["rendered_value"], "53조 1,139억원")
        self.assertEqual(current["calculation_operands"][0]["operand_id"], "capex_2023")

    def test_project_runtime_calculation_trace_prefers_live_lookup_over_stale_aggregate_trace(self) -> None:
        state = {
            "answer": "2023년 시설투자(CAPEX) 총액은 53조 1,139억원입니다.",
            "compressed_answer": "2023년 시설투자(CAPEX) 총액은 53조 1,139억원입니다.",
            "active_subtask": {"task_id": "task_1"},
            "resolved_calculation_trace": {
                "calculation_operands": [],
                "calculation_plan": {"status": "ok", "mode": "aggregate_subtasks", "subtask_count": 2},
                "calculation_result": {
                    "status": "partial",
                    "rendered_value": "stale aggregate",
                    "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []},
                },
            },
            "calculation_operands": [
                {
                    "operand_id": "capex_2023",
                    "label": "2023 시설투자(CAPEX)",
                    "raw_value": "531,139",
                    "raw_unit": "억원",
                    "normalized_value": 53113900000000.0,
                    "normalized_unit": "KRW",
                }
            ],
            "calculation_plan": {"status": "ok", "operation": "lookup", "mode": "single_value"},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "53조 1,139억원",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {"status": "ok", "rendered_value": "53조 1,139억원"},
                },
            },
            "tasks": [],
            "artifacts": [],
        }

        projected = self.agent._project_runtime_calculation_trace(state)

        self.assertEqual(projected["calculation_plan"]["operation"], "lookup")
        self.assertEqual(projected["calculation_result"]["rendered_value"], "53조 1,139억원")
        self.assertEqual(projected["calculation_operands"][0]["operand_id"], "capex_2023")

    def test_project_legacy_calculation_fields_aliases_runtime_trace_projection(self) -> None:
        state = {
            "calculation_operands": [{"row_id": "legacy"}],
            "calculation_plan": {"operation": "lookup"},
            "calculation_result": {"status": "ok", "rendered_value": "123"},
            "tasks": [],
            "artifacts": [],
            "subtask_results": [],
        }

        self.assertEqual(
            self.agent._project_legacy_calculation_fields(state),
            self.agent._project_runtime_calculation_trace(state),
        )

    def test_reflection_retry_ignores_legacy_top_level_runtime_projection(self) -> None:
        self.agent._llm_for_phase = lambda _phase: _FailingStructuredLLM()
        state = {
            "query": "find the missing numeric value",
            "topic": "missing numeric value",
            "intent": "comparison",
            "query_type": "comparison",
            "years": [],
            "companies": [],
            "seed_retrieved_docs": [],
            "active_subtask": {},
            "missing_info": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [{"label": "legacy", "value": "999"}],
            "calculation_plan": {},
            "calculation_result": {},
        }

        update = self.agent._plan_reflection_retry(state)

        self.assertEqual(update["reflection_plan"]["retry_objective"], "find_missing_values")
        self.assertEqual(update["reflection_request"]["remaining_retry_budget"], 1)
        self.assertEqual(
            update["planner_debug_trace"]["reflection_request"],
            update["reflection_request"],
        )
        self.assertEqual(update["planner_debug_trace"]["reflection_error"], "structured output disabled")

    def test_prepare_reflection_retry_ignores_legacy_top_level_runtime_projection(self) -> None:
        state = {
            "query": "find the missing numeric value",
            "topic": "missing numeric value",
            "intent": "comparison",
            "query_type": "comparison",
            "years": [],
            "companies": [],
            "active_subtask": {},
            "missing_info": [],
            "reflection_count": 0,
            "reflection_plan": {},
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [{"label": "legacy", "value": "999"}],
            "calculation_plan": {"missing_info": ["legacy plan"]},
            "calculation_result": {"explanation": "legacy result"},
        }

        update = self.agent._prepare_reflection_retry(state)

        self.assertEqual(update["retry_reason"], "missing operands")
        self.assertEqual(update["missing_info"], ["missing numeric value"])
        self.assertEqual(update["reflection_action"]["action_type"], "retry_retrieval")
        self.assertEqual(update["reflection_action"]["retry_queries"], update["retry_queries"])
        self.assertEqual(update["reflection_action"]["stop_reason"], "")
        self.assertEqual(update["reflection_report"]["outcome"], "retry_prepared")
        self.assertEqual(update["reflection_report"]["action_taken"], "retry_retrieval")
        self.assertEqual(update["reflection_report"]["budget_consumed"], 1)
        trace = _project_task_artifact_trace(update["tasks"], update["artifacts"])
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["tasks"][0]["kind"], "reflection")
        self.assertEqual(trace["tasks"][0]["artifact_kinds"], ["reflection_report"])
        self.assertEqual(trace["artifacts"][0]["payload_keys"], [
            "reflection_action",
            "reflection_plan",
            "reflection_report",
            "reflection_request",
        ])
        self.assertEqual(
            _resolve_runtime_calculation_trace(update, allow_legacy_top_level=False),
            {},
        )

    def test_prepare_reflection_retry_allocates_next_id_from_existing_ledger(self) -> None:
        state = {
            "query": "find the missing numeric value",
            "topic": "missing numeric value",
            "intent": "comparison",
            "query_type": "comparison",
            "years": [],
            "companies": [],
            "active_subtask": {"task_id": "task_1", "metric_family": "numeric_lookup"},
            "missing_info": ["missing numeric value"],
            "reflection_count": 0,
            "reflection_plan": {
                "retry_strategy": "retry_retrieval",
                "missing_info": ["missing numeric value"],
                "retry_queries": ["find missing numeric value"],
            },
            "resolved_calculation_trace": {},
            "structured_result": {},
            "tasks": [
                {
                    "task_id": "reflection:task_1:001",
                    "kind": "reflection",
                    "label": "reflect task_1",
                    "status": "completed",
                    "artifact_ids": ["reflection:task_1:001:report"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "reflection:task_1:001:report",
                    "task_id": "reflection:task_1:001",
                    "kind": "reflection_report",
                    "status": "retry_prepared",
                    "payload": {
                        "reflection_report": {
                            "outcome": "retry_prepared",
                            "action_taken": "retry_retrieval",
                            "budget_consumed": 1,
                            "target_task_ids": ["task_1"],
                            "target_artifact_ids": [],
                            "blocking_issues": [],
                        },
                        "reflection_action": {
                            "action_type": "retry_retrieval",
                            "retry_queries": ["find missing numeric value"],
                            "retrieval_scope_hints": [],
                            "synthesis_source_ids": [],
                            "stop_reason": "",
                        },
                    },
                    "evidence_refs": [],
                }
            ],
        }

        update = self.agent._prepare_reflection_retry(state)

        artifact_ids = [
            str(item.get("artifact_id") or "")
            for item in update["artifacts"]
            if str(item.get("artifact_id") or "")
        ]
        self.assertEqual(artifact_ids[-1], "reflection:task_1:002:report")
        self.assertEqual(len(artifact_ids), len(set(artifact_ids)))
        task_ids = [str(item.get("task_id") or "") for item in update["tasks"]]
        self.assertIn("reflection:task_1:001", task_ids)
        self.assertIn("reflection:task_1:002", task_ids)
        trace = _project_task_artifact_trace(update["tasks"], update["artifacts"])
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])

    def test_prepare_synthesis_reflection_retry_records_task_output_source_ids(self) -> None:
        state = {
            "query": "calculate ratio from completed lookup tasks",
            "topic": "ratio",
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "years": [],
            "companies": [],
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "ratio",
                "operation_family": "ratio",
                "depends_on": ["task_2", "task_3"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "label": "numerator",
                        "preferred_task_id": "task_2",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "label": "denominator",
                        "preferred_task_id": "task_3",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "artifact_ids": ["operands:task_2:001", "plan:task_2:002", "result:task_2:003"],
                    "calculation_result": {"status": "ok", "rendered_value": "10"},
                },
                {
                    "task_id": "task_3",
                    "artifact_ids": ["operands:task_3:004", "plan:task_3:005", "result:task_3:006"],
                    "calculation_result": {"status": "ok", "rendered_value": "20"},
                },
            ],
            "tasks": [
                {
                    "task_id": "task_2",
                    "kind": "calculation",
                    "label": "numerator",
                    "status": "completed",
                    "artifact_ids": ["operands:task_2:001", "plan:task_2:002", "result:task_2:003"],
                },
                {
                    "task_id": "task_3",
                    "kind": "calculation",
                    "label": "denominator",
                    "status": "completed",
                    "artifact_ids": ["operands:task_3:004", "plan:task_3:005", "result:task_3:006"],
                },
            ],
            "artifacts": [
                {
                    "artifact_id": "operands:task_2:001",
                    "task_id": "task_2",
                    "kind": "operand_set",
                    "status": "ok",
                    "payload": {"calculation_operands": [{"operand_id": "n"}]},
                    "evidence_refs": ["ev_task_2"],
                },
                {
                    "artifact_id": "plan:task_2:002",
                    "task_id": "task_2",
                    "kind": "calculation_plan",
                    "status": "ok",
                    "payload": {"calculation_plan": {"status": "ok", "operation": "lookup"}},
                    "evidence_refs": ["ev_task_2"],
                },
                {
                    "artifact_id": "result:task_2:003",
                    "task_id": "task_2",
                    "kind": "calculation_result",
                    "status": "ok",
                    "payload": {"calculation_result": {"status": "ok", "rendered_value": "10"}},
                    "evidence_refs": ["ev_task_2"],
                },
                {
                    "artifact_id": "operands:task_3:004",
                    "task_id": "task_3",
                    "kind": "operand_set",
                    "status": "ok",
                    "payload": {"calculation_operands": [{"operand_id": "d"}]},
                    "evidence_refs": ["ev_task_3"],
                },
                {
                    "artifact_id": "plan:task_3:005",
                    "task_id": "task_3",
                    "kind": "calculation_plan",
                    "status": "ok",
                    "payload": {"calculation_plan": {"status": "ok", "operation": "lookup"}},
                    "evidence_refs": ["ev_task_3"],
                },
                {
                    "artifact_id": "result:task_3:006",
                    "task_id": "task_3",
                    "kind": "calculation_result",
                    "status": "ok",
                    "payload": {"calculation_result": {"status": "ok", "rendered_value": "20"}},
                    "evidence_refs": ["ev_task_3"],
                },
            ],
            "missing_info": [],
            "reflection_count": 0,
            "reflection_plan": {
                "retry_strategy": "synthesize_from_task_outputs",
                "missing_info": ["ratio operands"],
                "subqueries": [],
                "preferred_sections": [],
                "explanation": "use completed task outputs",
            },
            "reflection_request": {"failure_status": "incomplete"},
            "resolved_calculation_trace": {
                "calculation_operands": [],
                "calculation_plan": {"status": "incomplete", "missing_info": ["ratio operands"]},
                "calculation_result": {},
            },
            "structured_result": {},
        }

        update = self.agent._prepare_reflection_retry(state)

        self.assertEqual(update["reflection_action"]["action_type"], "synthesize_from_task_outputs")
        self.assertEqual(
            update["reflection_action"]["synthesis_source_ids"],
            ["result:task_2:003", "result:task_3:006"],
        )
        self.assertEqual(
            update["reflection_plan"]["synthesis_source_ids"],
            ["result:task_2:003", "result:task_3:006"],
        )
        trace = _project_task_artifact_trace(update["tasks"], update["artifacts"])
        self.assertEqual(trace["integrity_status"], "ok")

    def test_task_artifact_trace_ignores_superseded_empty_required_payload(self) -> None:
        trace = _project_task_artifact_trace(
            [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "ratio",
                    "status": "completed",
                    "artifact_ids": [
                        "operands:task_1:001",
                        "operands:task_1:002",
                        "plan:task_1:003",
                        "result:task_1:004",
                    ],
                }
            ],
            [
                {
                    "artifact_id": "operands:task_1:001",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "status": "missing",
                    "payload": {"calculation_operands": []},
                },
                {
                    "artifact_id": "operands:task_1:002",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "status": "sufficient",
                    "payload": {"calculation_operands": [{"operand_id": "n"}]},
                    "evidence_refs": ["ev_n"],
                },
                {
                    "artifact_id": "plan:task_1:003",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "status": "ok",
                    "payload": {"calculation_plan": {"operation": "ratio"}},
                },
                {
                    "artifact_id": "result:task_1:004",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "status": "ok",
                    "payload": {"calculation_result": {"rendered_value": "50%"}},
                },
            ],
        )

        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])

    def test_aggregate_subtasks_resolves_ledger_tasks_from_final_slots(self) -> None:
        self.agent.llm = None
        state = {
            "query": "calculate the 2023 expense ratio.",
            "calc_subtasks": [
                {"task_id": "task_2", "metric_family": "concept_lookup", "metric_label": "2023 expense amount", "operation_family": "lookup"},
                {"task_id": "task_3", "metric_family": "concept_lookup", "metric_label": "2023 base amount", "operation_family": "lookup"},
                {"task_id": "task_1", "metric_family": "concept_ratio", "metric_label": "expense ratio", "operation_family": "ratio"},
            ],
            "active_subtask_index": 2,
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "expense ratio",
                "operation_family": "ratio",
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 expense amount",
                    "operation_family": "lookup",
                    "status": "ok",
                    "answer": "expense amount 40",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "40",
                        "formatted_result": "expense amount 40",
                        "source_row_ids": ["ev_expense"],
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "expense amount",
                                "period": "2023",
                                "raw_value": "40",
                                "raw_unit": "KRW",
                                "normalized_value": 40.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "40",
                                "source_row_ids": ["ev_expense"],
                            },
                        },
                    },
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 base amount",
                    "operation_family": "aggregate_subtasks",
                    "status": "partial",
                    "answer": "base amount is missing",
                    "calculation_result": {
                        "status": "partial",
                        "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []},
                    },
                },
            ],
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "op_expense",
                        "label": "2023 expense amount",
                        "matched_operand_label": "expense amount",
                        "matched_operand_role": "numerator_1",
                        "raw_value": "40",
                        "raw_unit": "KRW",
                        "normalized_value": 40.0,
                        "normalized_unit": "KRW",
                        "period": "2023",
                        "evidence_id": "task_output:task_2",
                    },
                    {
                        "operand_id": "op_base",
                        "label": "2023 base amount",
                        "matched_operand_label": "base amount",
                        "matched_operand_role": "denominator_1",
                        "raw_value": "100",
                        "raw_unit": "KRW",
                        "normalized_value": 100.0,
                        "normalized_unit": "KRW",
                        "period": "2023",
                        "evidence_id": "ev_base",
                    },
                ],
                "calculation_plan": {"status": "ok", "operation": "ratio"},
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "40.00%",
                    "formatted_result": "expense ratio 40.00%",
                    "source_row_ids": ["task_output:task_2", "ev_base"],
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {
                            "status": "ok",
                            "label": "expense ratio",
                            "raw_value": "40.00",
                            "raw_unit": "%",
                            "normalized_value": 40.0,
                            "normalized_unit": "PERCENT",
                            "rendered_value": "40.00%",
                            "source_row_ids": ["task_output:task_2", "ev_base"],
                        },
                        "components_by_role": {
                            "numerator_1": [
                                {
                                    "status": "ok",
                                    "label": "expense amount",
                                    "period": "2023",
                                    "raw_value": "40",
                                    "raw_unit": "KRW",
                                    "normalized_value": 40.0,
                                    "normalized_unit": "KRW",
                                    "rendered_value": "40",
                                    "source_row_ids": ["task_output:task_2"],
                                }
                            ],
                            "denominator_1": [
                                {
                                    "status": "ok",
                                    "label": "base amount",
                                    "period": "2023",
                                    "raw_value": "100",
                                    "raw_unit": "KRW",
                                    "normalized_value": 100.0,
                                    "normalized_unit": "KRW",
                                    "rendered_value": "100",
                                    "source_row_ids": ["ev_base"],
                                }
                            ],
                        },
                    },
                },
            },
            "answer": "expense ratio 40.00%",
            "compressed_answer": "expense ratio 40.00%",
            "tasks": [
                {
                    "task_id": "task_2",
                    "kind": "calculation",
                    "label": "2023 expense amount",
                    "status": "pending",
                    "metric_family": "concept_lookup",
                    "artifact_ids": ["semantic_plan:001"],
                },
                {
                    "task_id": "task_3",
                    "kind": "reconciliation",
                    "label": "reconcile 2023 base amount",
                    "status": "partial",
                    "metric_family": "concept_lookup",
                    "artifact_ids": ["semantic_plan:001", "reconcile:task_3:001"],
                },
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "expense ratio",
                    "status": "completed",
                    "metric_family": "concept_ratio",
                    "artifact_ids": ["operands:task_1:001", "plan:task_1:002", "result:task_1:003"],
                },
            ],
            "artifacts": [
                {
                    "artifact_id": "semantic_plan:001",
                    "task_id": "task_2",
                    "kind": "semantic_plan",
                    "status": "concept_fallback",
                    "payload": {"subtasks": []},
                },
                {
                    "artifact_id": "reconcile:task_3:001",
                    "task_id": "task_3",
                    "kind": "reconciliation_result",
                    "status": "insufficient_operands",
                    "payload": {"reconciliation_result": {"status": "insufficient_operands"}},
                },
                {
                    "artifact_id": "operands:task_1:001",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "status": "sufficient",
                    "payload": {"calculation_operands": [{"operand_id": "op_expense"}]},
                    "evidence_refs": ["task_output:task_2", "ev_base"],
                },
                {
                    "artifact_id": "plan:task_1:002",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "status": "ok",
                    "payload": {"calculation_plan": {"operation": "ratio"}},
                    "evidence_refs": ["task_output:task_2", "ev_base"],
                },
                {
                    "artifact_id": "result:task_1:003",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "status": "ok",
                    "payload": {"calculation_result": {"rendered_value": "40.00%"}},
                    "evidence_refs": ["task_output:task_2", "ev_base"],
                },
            ],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)
        trace = _project_task_artifact_trace(updated["tasks"], updated["artifacts"])
        tasks_by_id = {task["task_id"]: task for task in trace["tasks"]}

        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(tasks_by_id["task_2"]["status"], "superseded")
        self.assertEqual(
            tasks_by_id["task_2"]["resolution_status"],
            "superseded_by_aggregate_result",
        )
        self.assertEqual(tasks_by_id["task_2"]["superseded_by_task_id"], "aggregate")
        self.assertEqual(tasks_by_id["task_3"]["status"], "superseded")
        self.assertEqual(
            tasks_by_id["task_3"]["resolution_status"],
            "superseded_by_aggregate_result",
        )
        self.assertEqual(tasks_by_id["task_3"]["superseded_by_task_id"], "aggregate")

    def test_aggregate_ledger_supersedes_tasks_from_final_subtask_slots(self) -> None:
        tasks = [
            {
                "task_id": "task_2",
                "kind": "reconciliation",
                "label": "reconcile 2023 base amount",
                "status": "partial",
                "metric_family": "concept_lookup",
                "artifact_ids": ["reconcile:task_2:001"],
            }
        ]
        artifacts = [
            {
                "artifact_id": "reconcile:task_2:001",
                "task_id": "task_2",
                "kind": "reconciliation_result",
                "status": "insufficient_operands",
                "payload": {"reconciliation_result": {"status": "insufficient_operands"}},
            }
        ]
        ordered_results = [
            {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "expense ratio",
                "operation_family": "ratio",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "40.00%",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {
                            "status": "ok",
                            "label": "expense ratio",
                            "normalized_value": 40.0,
                            "normalized_unit": "PERCENT",
                            "rendered_value": "40.00%",
                        },
                        "components_by_role": {
                            "denominator_1": [
                                {
                                    "status": "ok",
                                    "label": "base amount",
                                    "period": "2023",
                                    "raw_value": "100",
                                    "raw_unit": "KRW",
                                    "normalized_value": 100.0,
                                    "normalized_unit": "KRW",
                                    "rendered_value": "100",
                                    "source_row_ids": ["ev_base"],
                                }
                            ]
                        },
                    },
                },
            }
        ]
        aggregate_projection = {
            "calculation_operands": [],
            "calculation_plan": {"mode": "aggregate_subtasks"},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "expense ratio 40.00%",
                "answer_slots": {
                    "operation_family": "aggregate_subtasks",
                    "subtask_results": [],
                },
            },
        }

        updated_tasks, updated_artifacts = self.agent._finalize_aggregate_task_ledger(
            tasks,
            artifacts,
            ordered_results=ordered_results,
            aggregate_projection=aggregate_projection,
            aggregate_artifact_id="aggregate:002",
        )
        trace = _project_task_artifact_trace(updated_tasks, updated_artifacts)

        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["tasks"][0]["status"], "superseded")
        self.assertEqual(trace["tasks"][0]["superseded_by_artifact_id"], "aggregate:002")

    def test_verify_calculation_skip_does_not_rewrite_compatibility_mirrors(self) -> None:
        state = {
            "answer": "insufficient evidence",
            "compressed_answer": "insufficient evidence",
            "resolved_calculation_trace": {
                "calculation_operands": [{"row_id": "fresh"}],
                "calculation_plan": {"operation": "none"},
                "calculation_result": {"status": "insufficient_operands"},
            },
            "structured_result": {"status": "insufficient_operands"},
            "calculation_operands": [{"row_id": "stale"}],
            "calculation_plan": {"status": "stale"},
            "calculation_result": {"status": "stale"},
            "calculation_debug_trace": {},
        }

        updated = self.agent._verify_calculation_answer(state)

        self.assertEqual(
            updated["resolved_calculation_trace"]["calculation_result"]["status"],
            "insufficient_operands",
        )
        self.assertEqual(updated["calculation_debug_trace"]["verification"]["reason"], "calculation_status_not_ok")
        self.assertNotIn("calculation_operands", updated)
        self.assertNotIn("calculation_plan", updated)
        self.assertNotIn("calculation_result", updated)

    def test_route_after_aggregate_subtasks_reuses_pre_calc_planner_when_feedback_exists(self) -> None:
        route = self.agent._route_after_aggregate_subtasks(
            {
                "planner_feedback": "유동비율 계산 재료 누락",
                "plan_loop_count": 0,
            }
        )
        self.assertEqual(route, "pre_calc_planner")
        self.assertEqual(
            self.agent._route_after_aggregate_subtasks(
                {
                    "planner_feedback": "",
                    "plan_loop_count": 0,
                }
            ),
            "cite",
        )

    def test_aggregate_subtasks_replans_on_task_artifact_integrity_error(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 대상 지표는 100억원입니다.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 대상 지표를 알려줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"}
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"},
            "subtask_results": [],
            "answer": "2023년 대상 지표는 100억원입니다.",
            "compressed_answer": "2023년 대상 지표는 100억원입니다.",
            "selected_claim_ids": ["ev_1"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "대상 지표",
                    "status": "completed",
                    "artifact_ids": ["artifact:missing"],
                }
            ],
            "artifacts": [],
            "calculation_result": {"status": "ok", "rendered_value": "100억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_mode"], "replan")
        self.assertIn("Task/artifact ledger integrity error", updated["planner_feedback"])
        self.assertIn("missing_artifact_reference", updated["planner_feedback"])
        self.assertEqual(
            self.agent._route_after_aggregate_subtasks(
                {
                    "planner_feedback": updated["planner_feedback"],
                    "plan_loop_count": 0,
                }
            ),
            "pre_calc_planner",
        )

    def test_aggregate_subtasks_replans_on_missing_required_calculation_artifact_kind(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 대상 지표는 100억원입니다.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 대상 지표를 알려줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"}
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"},
            "subtask_results": [],
            "answer": "2023년 대상 지표는 100억원입니다.",
            "compressed_answer": "2023년 대상 지표는 100억원입니다.",
            "selected_claim_ids": ["ev_1"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "대상 지표",
                    "status": "completed",
                    "artifact_ids": ["artifact:operand", "artifact:plan"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:operand",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "status": "ok",
                    "payload": {"calculation_operands": []},
                },
                {
                    "artifact_id": "artifact:plan",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "status": "ok",
                    "payload": {"calculation_plan": {"operation": "lookup"}},
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "100억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_mode"], "replan")
        self.assertIn("missing_required_artifact_kind", updated["planner_feedback"])
        self.assertIn("calculation_result", updated["planner_feedback"])

    def test_aggregate_subtasks_replans_on_missing_required_artifact_payload(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 대상 지표는 100억원입니다.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 대상 지표를 알려줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"}
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"},
            "subtask_results": [],
            "answer": "2023년 대상 지표는 100억원입니다.",
            "compressed_answer": "2023년 대상 지표는 100억원입니다.",
            "selected_claim_ids": ["ev_1"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "대상 지표",
                    "status": "completed",
                    "artifact_ids": ["artifact:operand", "artifact:plan", "artifact:result"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:operand",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "status": "ok",
                    "payload": {"calculation_operands": []},
                },
                {
                    "artifact_id": "artifact:plan",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "status": "ok",
                    "payload": {"calculation_plan": {"status": "ok"}},
                },
                {
                    "artifact_id": "artifact:result",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "status": "ok",
                    "payload": {"calculation_result": {"status": "ok"}},
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "100억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_mode"], "replan")
        self.assertIn("missing_required_artifact_payload", updated["planner_feedback"])
        self.assertIn("missing_required_evidence_ref", updated["planner_feedback"])
        self.assertIn("calculation_result", updated["planner_feedback"])

    def test_aggregate_subtasks_replans_on_reconciliation_integrity_error(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 대상 지표는 100억원입니다.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 대상 지표를 알려줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"}
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"},
            "subtask_results": [],
            "answer": "2023년 대상 지표는 100억원입니다.",
            "compressed_answer": "2023년 대상 지표는 100억원입니다.",
            "selected_claim_ids": ["ev_1"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "대상 지표",
                    "status": "completed",
                    "artifact_ids": ["artifact:operand", "artifact:plan", "artifact:result"],
                },
                {
                    "task_id": "task_reconcile",
                    "kind": "reconciliation",
                    "label": "reconcile 대상 지표",
                    "status": "completed",
                    "artifact_ids": ["artifact:reconcile"],
                },
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:operand",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "status": "ok",
                    "payload": {"calculation_operands": [{"label": "대상 지표", "value": "100", "row_id": "ev_1"}]},
                },
                {
                    "artifact_id": "artifact:plan",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "status": "ok",
                    "payload": {"calculation_plan": {"status": "ok", "operation": "lookup"}},
                },
                {
                    "artifact_id": "artifact:result",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "status": "ok",
                    "payload": {"calculation_result": {"status": "ok", "rendered_value": "100억원"}},
                },
                {
                    "artifact_id": "artifact:reconcile",
                    "task_id": "task_reconcile",
                    "kind": "reconciliation_result",
                    "status": "ok",
                    "payload": {"reconciliation_result": {"status": "ready", "matched_operands": []}},
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "100억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_mode"], "replan")
        self.assertIn("missing_required_evidence_ref", updated["planner_feedback"])
        self.assertIn("task_reconcile", updated["planner_feedback"])

    def test_aggregate_subtasks_uses_current_task_source_refs_for_reconciliation_artifact(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "The requested value is 100.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "Return the requested value.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "requested value"}
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "requested value",
                "operation_family": "lookup",
            },
            "subtask_results": [],
            "answer": "The requested value is 100.",
            "compressed_answer": "The requested value is 100.",
            "selected_claim_ids": ["claim:source"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "reconciliation",
                    "label": "reconcile requested value",
                    "status": "completed",
                    "artifact_ids": ["reconcile:task_1:001"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "reconcile:task_1:001",
                    "task_id": "task_1",
                    "kind": "reconciliation_result",
                    "status": "ready",
                    "payload": {"reconciliation_result": {"status": "ready", "matched_operands": []}},
                    "evidence_refs": [],
                }
            ],
            "resolved_calculation_trace": {
                "calculation_operands": [],
                "calculation_plan": {"operation": "lookup"},
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "100",
                    "source_row_ids": ["row:source"],
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "requested value",
                            "raw_value": "100",
                            "rendered_value": "100",
                            "source_row_id": "row:source",
                            "source_row_ids": ["row:source"],
                        },
                    },
                },
            },
            "structured_result": {
                "status": "ok",
                "rendered_value": "100",
            },
            "calculation_result": {
                "status": "ok",
                "rendered_value": "stale",
                "source_row_ids": ["row:stale"],
            },
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)
        reconcile_artifact = next(
            artifact
            for artifact in updated["artifacts"]
            if artifact["artifact_id"] == "reconcile:task_1:001"
        )

        self.assertEqual(reconcile_artifact["evidence_refs"], ["row:source", "claim:source"])
        self.assertNotIn("missing_required_evidence_ref", updated["planner_feedback"])
        trace = _project_task_artifact_trace(updated["tasks"], updated["artifacts"])
        aggregate_task = next(task for task in trace["tasks"] if task["task_id"] == "aggregate")

        self.assertEqual(trace["orphan_artifact_ids"], [])
        self.assertEqual(aggregate_task["kind"], "synthesis")
        self.assertEqual(aggregate_task["latest_artifact_kind"], "aggregated_answer")

    def test_aggregate_subtasks_ignores_stale_top_level_source_refs_for_reconciliation_artifact(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "The requested value is 100.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "Return the requested value.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "requested value"}
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "requested value",
                "operation_family": "lookup",
            },
            "subtask_results": [],
            "answer": "The requested value is 100.",
            "compressed_answer": "The requested value is 100.",
            "selected_claim_ids": [],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "reconciliation",
                    "label": "reconcile requested value",
                    "status": "completed",
                    "artifact_ids": ["reconcile:task_1:001"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "reconcile:task_1:001",
                    "task_id": "task_1",
                    "kind": "reconciliation_result",
                    "status": "ready",
                    "payload": {"reconciliation_result": {"status": "ready", "matched_operands": []}},
                    "evidence_refs": [],
                }
            ],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "100",
                "source_row_ids": ["row:stale"],
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {
                        "status": "ok",
                        "rendered_value": "100",
                        "source_row_id": "row:stale",
                    },
                },
            },
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)
        reconcile_artifact = next(
            artifact
            for artifact in updated["artifacts"]
            if artifact["artifact_id"] == "reconcile:task_1:001"
        )

        self.assertEqual(reconcile_artifact["evidence_refs"], [])
        self.assertEqual(updated["planner_mode"], "replan")
        self.assertIn("missing_required_evidence_ref", updated["planner_feedback"])

    def test_aggregate_subtasks_replans_on_retrieval_integrity_error(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 대상 지표는 100억원입니다.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 대상 지표를 알려줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"}
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"},
            "subtask_results": [],
            "answer": "2023년 대상 지표는 100억원입니다.",
            "compressed_answer": "2023년 대상 지표는 100억원입니다.",
            "selected_claim_ids": ["ev_1"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "대상 지표",
                    "status": "completed",
                    "artifact_ids": ["artifact:operand", "artifact:plan", "artifact:result"],
                },
                {
                    "task_id": "task_retrieve",
                    "kind": "retrieval",
                    "label": "retrieve 대상 지표",
                    "status": "completed",
                    "artifact_ids": ["artifact:retrieve"],
                },
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:operand",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "status": "ok",
                    "payload": {"calculation_operands": [{"label": "대상 지표", "value": "100", "row_id": "ev_1"}]},
                },
                {
                    "artifact_id": "artifact:plan",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "status": "ok",
                    "payload": {"calculation_plan": {"status": "ok", "operation": "lookup"}},
                },
                {
                    "artifact_id": "artifact:result",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "status": "ok",
                    "payload": {"calculation_result": {"status": "ok", "rendered_value": "100억원"}},
                },
                {
                    "artifact_id": "artifact:retrieve",
                    "task_id": "task_retrieve",
                    "kind": "retrieval_bundle",
                    "status": "ok",
                    "payload": {"retrieved_docs": []},
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "100억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_mode"], "replan")
        self.assertIn("missing_required_artifact_payload", updated["planner_feedback"])
        self.assertIn("missing_required_evidence_ref", updated["planner_feedback"])
        self.assertIn("task_retrieve", updated["planner_feedback"])

    def test_aggregate_subtasks_replans_on_synthesis_integrity_error(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 대상 지표는 100억원입니다.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 대상 지표를 알려줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"}
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"},
            "subtask_results": [],
            "answer": "2023년 대상 지표는 100억원입니다.",
            "compressed_answer": "2023년 대상 지표는 100억원입니다.",
            "selected_claim_ids": ["ev_1"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "대상 지표",
                    "status": "completed",
                    "artifact_ids": ["artifact:operand", "artifact:plan", "artifact:result"],
                },
                {
                    "task_id": "task_synthesis",
                    "kind": "synthesis",
                    "label": "final merge",
                    "status": "completed",
                    "artifact_ids": ["artifact:synthesis"],
                },
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:operand",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "status": "ok",
                    "payload": {"calculation_operands": [{"label": "대상 지표", "value": "100", "row_id": "ev_1"}]},
                },
                {
                    "artifact_id": "artifact:plan",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "status": "ok",
                    "payload": {"calculation_plan": {"status": "ok", "operation": "lookup"}},
                },
                {
                    "artifact_id": "artifact:result",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "status": "ok",
                    "payload": {"calculation_result": {"status": "ok", "rendered_value": "100억원"}},
                },
                {
                    "artifact_id": "artifact:synthesis",
                    "task_id": "task_synthesis",
                    "kind": "aggregated_answer",
                    "status": "ok",
                    "payload": {"final_answer": "2023년 대상 지표는 100억원입니다."},
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "100억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_mode"], "replan")
        self.assertIn("missing_required_artifact_payload", updated["planner_feedback"])
        self.assertIn("missing_required_evidence_ref", updated["planner_feedback"])
        self.assertIn("task_synthesis", updated["planner_feedback"])

    def test_aggregate_subtasks_replans_on_critic_integrity_error(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 대상 지표는 100억원입니다.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 대상 지표를 알려줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"}
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"},
            "subtask_results": [],
            "answer": "2023년 대상 지표는 100억원입니다.",
            "compressed_answer": "2023년 대상 지표는 100억원입니다.",
            "selected_claim_ids": ["ev_1"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "대상 지표",
                    "status": "completed",
                    "artifact_ids": ["artifact:operand", "artifact:plan", "artifact:result"],
                },
                {
                    "task_id": "task_critic",
                    "kind": "critic",
                    "label": "review final merge",
                    "status": "completed",
                    "artifact_ids": ["artifact:critic"],
                },
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:operand",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "status": "ok",
                    "payload": {"calculation_operands": [{"label": "대상 지표", "value": "100", "row_id": "ev_1"}]},
                },
                {
                    "artifact_id": "artifact:plan",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "status": "ok",
                    "payload": {"calculation_plan": {"status": "ok", "operation": "lookup"}},
                },
                {
                    "artifact_id": "artifact:result",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "status": "ok",
                    "payload": {"calculation_result": {"status": "ok", "rendered_value": "100억원"}},
                },
                {
                    "artifact_id": "artifact:critic",
                    "task_id": "task_critic",
                    "kind": "critic_report",
                    "status": "ok",
                    "payload": {
                        "critic_report": {
                            "passed": True,
                            "verdict": "passed",
                            "target_task_id": "task_synthesis",
                        }
                    },
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "100억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_mode"], "replan")
        self.assertIn("missing_required_artifact_payload", updated["planner_feedback"])
        self.assertIn("task_critic", updated["planner_feedback"])
        self.assertIn("critic_report.acceptance_reason_or_issues", updated["planner_feedback"])

    def test_aggregate_subtasks_replans_when_final_source_has_warning_integrity(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 대상 지표는 100억원입니다.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 대상 지표를 알려줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"}
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"},
            "subtask_results": [],
            "answer": "2023년 대상 지표는 100억원입니다.",
            "compressed_answer": "2023년 대상 지표는 100억원입니다.",
            "selected_claim_ids": ["ev_1"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "대상 지표",
                    "status": "completed",
                    "artifact_ids": ["artifact:operand", "artifact:plan", "artifact:result"],
                },
                {
                    "task_id": "task_synthesis",
                    "kind": "synthesis",
                    "label": "final merge",
                    "status": "completed",
                    "artifact_ids": ["artifact:synthesis"],
                },
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:operand",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "status": "ok",
                    "payload": {"calculation_operands": [{"label": "대상 지표", "value": "100", "row_id": "ev_1"}]},
                },
                {
                    "artifact_id": "artifact:plan",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "status": "ok",
                    "payload": {"calculation_plan": {"status": "ok", "operation": "lookup"}},
                },
                {
                    "artifact_id": "artifact:result",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "status": "ok",
                    "payload": {"calculation_result": {"status": "ok", "rendered_value": "100억원"}},
                },
                {
                    "artifact_id": "artifact:synthesis",
                    "task_id": "task_synthesis",
                    "kind": "aggregated_answer",
                    "status": "ok",
                    "payload": {
                        "final_answer": "2023년 대상 지표는 100억원입니다.",
                        "source_artifact_ids": ["artifact:orphan"],
                    },
                    "evidence_refs": ["artifact:orphan"],
                },
                {
                    "artifact_id": "artifact:orphan",
                    "task_id": "missing_task",
                    "kind": "semantic_plan",
                    "status": "ok",
                    "payload": {"status": "ok"},
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "100억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_mode"], "replan")
        self.assertIn("final_source_orphan_artifact", updated["planner_feedback"])
        self.assertIn("artifact:orphan", updated["planner_feedback"])

    def test_aggregate_subtasks_refuses_on_integrity_error_when_replan_budget_is_exhausted(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 대상 지표는 100억원입니다.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 대상 지표를 알려줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"}
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "대상 지표"},
            "subtask_results": [],
            "answer": "2023년 대상 지표는 100억원입니다.",
            "compressed_answer": "2023년 대상 지표는 100억원입니다.",
            "selected_claim_ids": ["ev_1"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "대상 지표",
                    "status": "completed",
                    "artifact_ids": ["artifact:missing"],
                }
            ],
            "artifacts": [],
            "calculation_result": {"status": "ok", "rendered_value": "100억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 2,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_mode"], "initial")
        self.assertIn("missing_artifact_reference", updated["planner_feedback"])
        self.assertIn("원하신 답을 완전히 확정할 수는 없습니다.", updated["answer"])

    def test_aggregate_subtasks_can_emit_planner_feedback_for_replan(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 법인세비용차감전순이익은 확인되었지만, 전년 대비 비교를 위해 2022년 값이 추가로 필요합니다.",
                    "planner_feedback": "2022년 법인세비용차감전순이익 raw value를 찾는 lookup task를 추가하세요.",
                }
            )
        )
        state = {
            "query": "2023년 법인세비용차감전순이익을 보여주고 전년 대비 증감액을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "2023년 법인세비용차감전순이익", "query": "2023년 법인세비용차감전순이익을 찾아줘."},
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "2023년 법인세비용차감전순이익", "query": "2023년 법인세비용차감전순이익을 찾아줘."},
            "subtask_results": [],
            "answer": "2023년 법인세비용차감전순이익은 1조 4,813억원입니다.",
            "compressed_answer": "2023년 법인세비용차감전순이익은 1조 4,813억원입니다.",
            "selected_claim_ids": ["ev_100"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "2023년 법인세비용차감전순이익",
                    "status": "completed",
                    "artifact_ids": ["artifact:101", "artifact:102", "artifact:103"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:101",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "pretax_2023", "label": "2023년 법인세비용차감전순이익", "normalized_value": 1481396318000, "raw_value": "1,481,396,318", "raw_unit": "천원", "period": "2023년"}
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:102",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "lookup"}
                    },
                },
                {
                    "artifact_id": "artifact:103",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {"status": "ok", "rendered_value": "1조 4,813억원", "series": []}
                    },
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "1조 4,813억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }
        updated = self.agent._aggregate_calculation_subtasks(state)
        self.assertEqual(updated["planner_mode"], "replan")
        self.assertEqual(
            updated["planner_feedback"],
            "2022년 법인세비용차감전순이익 raw value를 찾는 lookup task를 추가하세요.",
        )
        self.assertIn("2023년 법인세비용차감전순이익은 확인되었지만", updated["answer"])
        self.assertEqual(
            self.agent._route_after_aggregate_subtasks(
                {
                    "planner_feedback": "추가 재계획 필요",
                    "plan_loop_count": 2,
                }
            ),
            "cite",
        )

    def test_exclusive_narrative_aggregate_feedback_does_not_replan(self) -> None:
        self.assertEqual(
            self.agent._route_after_aggregate_subtasks(
                {
                    "semantic_plan": {"status": "narrative_policy_exclusive"},
                    "planner_feedback": "직접 근거가 부족하므로 추가 계획이 필요합니다.",
                    "plan_loop_count": 0,
                }
            ),
            "cite",
        )

    def test_aggregate_subtasks_emits_final_refusal_when_replan_budget_is_exhausted(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 법인세비용차감전순이익은 1조 4,813억원입니다.",
                    "planner_feedback": "2022년 법인세비용차감전순이익 raw value가 여전히 필요합니다.",
                }
            )
        )
        state = {
            "query": "2023년 법인세비용차감전순이익을 보여주고 전년 대비 증감액을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "2023년 법인세비용차감전순이익", "query": "2023년 법인세비용차감전순이익을 찾아줘."},
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "2023년 법인세비용차감전순이익", "query": "2023년 법인세비용차감전순이익을 찾아줘."},
            "subtask_results": [],
            "answer": "2023년 법인세비용차감전순이익은 1조 4,813억원입니다.",
            "compressed_answer": "2023년 법인세비용차감전순이익은 1조 4,813억원입니다.",
            "selected_claim_ids": ["ev_100"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "2023년 법인세비용차감전순이익",
                    "status": "completed",
                    "artifact_ids": ["artifact:101", "artifact:102", "artifact:103"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:101",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "pretax_2023", "label": "2023년 법인세비용차감전순이익", "normalized_value": 1481396318000, "raw_value": "1,481,396,318", "raw_unit": "천원", "period": "2023년"}
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:102",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "lookup"}
                    },
                },
                {
                    "artifact_id": "artifact:103",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {"status": "ok", "rendered_value": "1조 4,813억원", "series": []}
                    },
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "1조 4,813억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 2,
        }
        updated = self.agent._aggregate_calculation_subtasks(state)
        self.assertEqual(updated["planner_mode"], "initial")
        self.assertEqual(
            updated["planner_feedback"],
            "2022년 법인세비용차감전순이익 raw value가 여전히 필요합니다.",
        )
        self.assertIn("2023년 법인세비용차감전순이익은 1조 4,813억원입니다.", updated["answer"])
        self.assertIn("원하신 답을 완전히 확정할 수는 없습니다.", updated["answer"])

    def test_aggregate_subtasks_drops_unsupported_partial_when_final_refusal_is_exhausted(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "Unrelated sustainability initiatives are described in the report.",
                    "planner_feedback": "The requested numeric facts are still missing.",
                }
            )
        )
        state = {
            "query": "How many owned trucks and deliveries are disclosed?",
            "calc_subtasks": [
                {
                    "task_id": "task_1",
                    "metric_family": "generic_numeric",
                    "metric_label": "owned truck count and delivery count",
                    "operation_family": "single_value",
                }
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "generic_numeric",
                "metric_label": "owned truck count and delivery count",
                "operation_family": "single_value",
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "generic_numeric",
                    "metric_label": "owned truck count and delivery count",
                    "operation_family": "single_value",
                    "answer": "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다.",
                    "status": "insufficient_operands",
                    "calculation_result": {
                        "status": "insufficient_operands",
                        "rendered_value": "",
                        "answer_slots": {
                            "operation_family": "single_value",
                            "primary_value": {
                                "status": "missing",
                                "label": "owned truck count and delivery count",
                                "rendered_value": "",
                                "source_row_ids": [],
                            },
                        },
                    },
                    "source_row_ids": [],
                    "source_evidence_ids": [],
                }
            ],
            "answer": "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다.",
            "compressed_answer": "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다.",
            "selected_claim_ids": [],
            "tasks": [],
            "artifacts": [],
            "calculation_result": {"status": "insufficient_operands"},
            "reconciliation_result": {"status": "insufficient_operands"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 2,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_mode"], "initial")
        self.assertNotIn("Unrelated sustainability", updated["answer"])
        self.assertIn("owned truck count and delivery count 정보를 찾을 수 없습니다.", updated["answer"])
        self.assertIn("원하신 답을 완전히 확정할 수는 없습니다.", updated["answer"])

    def test_aggregate_subtasks_blocks_replan_after_duplicate_direct_lookup_rejection(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "확인된 일부 값만으로는 최종 계산을 확정할 수 없습니다.",
                    "planner_feedback": "누락된 lookup 값을 다시 찾아야 합니다.",
                }
            )
        )
        state = {
            "query": "ratio calculation",
            "calc_subtasks": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "known numerator",
                    "query": "known numerator",
                }
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "known numerator",
                "query": "known numerator",
            },
            "subtask_results": [],
            "answer": "known numerator is 100",
            "compressed_answer": "known numerator is 100",
            "selected_claim_ids": ["ev_100"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "known numerator",
                    "status": "completed",
                    "artifact_ids": ["artifact:101", "artifact:102", "artifact:103"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:101",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "row_1", "label": "known numerator", "normalized_value": 100, "raw_value": "100"}
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:102",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {"calculation_plan": {"status": "ok", "operation": "lookup"}},
                },
                {
                    "artifact_id": "artifact:103",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {"calculation_result": {"status": "ok", "rendered_value": "100", "series": []}},
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "100"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 1,
            "numeric_debug_trace_history": [
                {
                    "rejected_reason": "missing_direct_lookup_operand_support",
                    "numeric_extraction_fingerprint": "same-window",
                },
                {
                    "rejected_reason": "missing_direct_lookup_operand_support",
                    "skipped_reason": "duplicate_missing_direct_lookup_operand_support",
                    "numeric_extraction_fingerprint": "same-window",
                },
            ],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_mode"], "initial")
        self.assertEqual(
            updated["replan_blocked_reason"],
            "duplicate_missing_direct_lookup_operand_support",
        )
        self.assertIn("원하신 답을 완전히 확정할 수는 없습니다.", updated["answer"])
        self.assertEqual(self.agent._route_after_aggregate_subtasks(updated), "cite")

    def test_aggregate_subtasks_ignores_spurious_llm_feedback_when_material_is_complete(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 연결기준 매출액은 162조 6,636억원입니다.",
                    "planner_feedback": "추가 재료 확인이 필요합니다.",
                }
            )
        )
        state = {
            "query": "2023년 연결기준 매출액은 얼마야?",
            "calc_subtasks": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 연결기준 매출액",
                    "query": "2023년 연결기준 매출액을 찾아줘.",
                },
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 연결기준 매출액",
                "query": "2023년 연결기준 매출액을 찾아줘.",
            },
            "subtask_results": [],
            "answer": "2023년 연결기준 매출액은 162조 6,636억원입니다.",
            "compressed_answer": "2023년 연결기준 매출액은 162조 6,636억원입니다.",
            "selected_claim_ids": ["ev_rev"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "2023년 연결기준 매출액",
                    "status": "completed",
                    "artifact_ids": ["artifact:301", "artifact:302", "artifact:303"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:301",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {
                                "row_id": "revenue_2023",
                                "label": "2023년 연결기준 매출액",
                                "normalized_value": 162663579000000.0,
                                "raw_value": "162,663,579",
                                "raw_unit": "백만원",
                                "period": "2023년",
                            }
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:302",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "lookup"}
                    },
                },
                {
                    "artifact_id": "artifact:303",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {
                            "status": "ok",
                            "rendered_value": "162조 6,636억원",
                            "answer_slots": {
                                "operation_family": "lookup",
                                "primary_value": {
                                    "status": "ok",
                                    "label": "2023년 연결기준 매출액",
                                    "period": "2023년",
                                    "raw_value": "162,663,579",
                                    "raw_unit": "백만원",
                                    "normalized_value": 162663579000000.0,
                                    "normalized_unit": "KRW",
                                    "rendered_value": "162조 6,636억원",
                                },
                            },
                        }
                    },
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "162조 6,636억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 2,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_feedback"], "")
        self.assertEqual(updated["planner_mode"], "initial")
        self.assertEqual(updated["answer"], "2023년 연결기준 매출액은 162조 6,636억원입니다.")
        self.assertNotIn("완전히 확정할 수는 없습니다", updated["answer"])

    def test_aggregate_subtasks_dedupes_stale_failed_metric_before_feedback(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 연결기준 매출액은 162조 6,636억원입니다. 매출원가는 129조 1,792억원, 판매비와관리비는 18조 3,575억원입니다. 이를 합산한 총 영업비용은 147조 5,367억원이며, 전체 매출액 대비 영업비용률은 90.7%입니다.",
                    "planner_feedback": "영업비용률 계산 재료가 아직 부족합니다.",
                }
            )
        )
        state = {
            "query": "2023년 손익계산서에서 '매출원가'와 '판매비와관리비'를 합산하여 '총 영업비용'을 구한 뒤, 전체 매출액 대비 영업비용률을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_4"},
                {"task_id": "task_5"},
                {"task_id": "task_1"},
                {"task_id": "task_6"},
                {"task_id": "task_2"},
            ],
            "active_subtask_index": 4,
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "concept_ratio",
                "metric_label": "영업비용률",
                "operation_family": "ratio",
            },
            "subtask_results": [
                {
                    "task_id": "task_4",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 매출액",
                    "status": "ok",
                    "answer": "2023년 연결기준 매출액은 162조 6,636억원입니다.",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 매출액",
                            "primary_value": {
                                "status": "ok",
                                "label": "매출액",
                                "normalized_value": 162663579000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "162조 6,636억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_5",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 매출원가",
                    "status": "ok",
                    "answer": "2023년 연결기준 매출원가는 129조 1,792억원입니다.",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 매출원가",
                            "primary_value": {
                                "status": "ok",
                                "label": "매출원가",
                                "normalized_value": 129179183000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "129조 1,792억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_1",
                    "metric_family": "concept_ratio",
                    "metric_label": "영업비용률",
                    "status": "insufficient_operands",
                    "answer": "",
                    "calculation_result": {
                        "status": "insufficient_operands",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "metric_label": "영업비용률",
                            "primary_value": {"status": "missing", "label": "영업비용률"},
                        },
                    },
                },
                {
                    "task_id": "task_6",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 판매비와관리비",
                    "status": "ok",
                    "answer": "2023년 판매비와관리비는 18조 3,575억원입니다.",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 판매비와관리비",
                            "primary_value": {
                                "status": "ok",
                                "label": "판매비와관리비",
                                "normalized_value": 18357495000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "18조 3,575억원",
                            },
                        },
                    },
                },
            ],
            "answer": "2023년 연결기준 영업비용률은 90.7%입니다.",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "영업비용률",
                    "components_by_role": {
                        "numerator_1": [{"status": "ok", "label": "매출원가"}],
                        "numerator_2": [{"status": "ok", "label": "판매비와관리비"}],
                        "denominator_1": [{"status": "ok", "label": "매출액"}],
                    },
                    "primary_value": {
                        "status": "ok",
                        "label": "영업비용률",
                        "normalized_value": 90.7004990957441,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "90.7%",
                    },
                },
                "source_row_ids": [],
            },
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "selected_claim_ids": [],
            "plan_loop_count": 2,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_feedback"], "")
        self.assertNotIn("완전히 확정할 수는 없습니다", updated["answer"])

    def test_aggregate_subtasks_uses_answer_slots_gap_check_without_llm(self) -> None:
        state = {
            "query": "2023년 법인세비용차감전순이익을 보여주고 전년 대비 증감액을 계산해 줘.",
            "calc_subtasks": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_difference",
                    "metric_label": "법인세비용차감전순이익 증감액",
                    "query": "법인세비용차감전순이익 증감액을 계산해 줘.",
                },
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_difference",
                "metric_label": "법인세비용차감전순이익 증감액",
                "query": "법인세비용차감전순이익 증감액을 계산해 줘.",
            },
            "subtask_results": [],
            "answer": "2023년 법인세비용차감전순이익은 1조 4,814억원입니다.",
            "compressed_answer": "2023년 법인세비용차감전순이익은 1조 4,814억원입니다.",
            "selected_claim_ids": ["ev_200"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "법인세비용차감전순이익 증감액",
                    "status": "completed",
                    "artifact_ids": ["artifact:201", "artifact:202", "artifact:203"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:201",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "pretax_2023", "label": "2023년 법인세비용차감전순이익", "normalized_value": 1481396318000},
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:202",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "subtract"}
                    },
                },
                {
                    "artifact_id": "artifact:203",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {
                            "status": "partial",
                            "rendered_value": "",
                            "answer_slots": {
                                "operation_family": "difference",
                                "current_value": {"period": "2023년", "rendered_value": "1조 4,814억원"},
                            },
                        }
                    },
                },
            ],
            "calculation_result": {"status": "partial"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }
        updated = self.agent._aggregate_calculation_subtasks(state)
        self.assertEqual(updated["planner_mode"], "replan")
        self.assertIn("법인세비용차감전순이익 증감액 계산에 필요한", updated["planner_feedback"])
        self.assertIn("prior", updated["planner_feedback"])

    def test_aggregate_subtasks_ignores_growth_gap_when_sibling_lookups_cover_periods(self) -> None:
        ordered_results = [
            {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 시설투자(CAPEX) 총액",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "label": "2023 시설투자(CAPEX)",
                            "concept": "capital_expenditure_total",
                            "period": "2023년",
                            "rendered_value": "53조 1,139억원",
                        },
                    },
                },
            },
            {
                "task_id": "task_2",
                "metric_family": "concept_growth_rate",
                "metric_label": "시설투자(CAPEX) 증감률",
                "status": "insufficient_operands",
                "calculation_result": {
                    "status": "insufficient_operands",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "components_by_role": {
                            "current_period": [
                                {
                                    "status": "ok",
                                    "label": "2023 시설투자(CAPEX)",
                                    "concept": "capital_expenditure_total",
                                    "period": "2023년",
                                    "rendered_value": "53조 1,139억원",
                                }
                            ]
                        },
                        "current_value": {
                            "status": "missing",
                            "label": "시설투자(CAPEX)",
                            "concept": "capital_expenditure_total",
                            "period": "",
                        },
                        "prior_value": {
                            "status": "missing",
                            "label": "시설투자(CAPEX)",
                            "concept": "capital_expenditure_total",
                            "period": "2022년",
                        },
                        "primary_value": {
                            "status": "missing",
                            "label": "시설투자(CAPEX) 증감률",
                        },
                    },
                },
            },
            {
                "task_id": "task_3",
                "metric_family": "concept_lookup",
                "metric_label": "2022년 시설투자(CAPEX) 총액",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "label": "시설투자(CAPEX) 총액",
                            "period": "2022년",
                            "rendered_value": "18조 1,168억원",
                        },
                    },
                },
            },
        ]

        feedback = self.agent._infer_planner_feedback_from_answer_slots(ordered_results)

        self.assertEqual(feedback, "")

    def test_aggregate_subtasks_ignores_stale_lookup_gap_when_growth_slots_cover_value(self) -> None:
        ordered_results = [
            {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 커머스 부문 매출액",
                "status": "insufficient_operands",
                "answer": "2023년 커머스 부문 매출액 계산에 필요한 재료가 누락되었습니다.",
                "calculation_result": {"status": "insufficient_operands"},
            },
            {
                "task_id": "task_4",
                "metric_family": "concept_growth_rate",
                "metric_label": "커머스 부문 매출 성장률",
                "status": "ok",
                "answer": "커머스 부문은 2023년에 2조 5,466억 원의 매출을 기록하며 전년 대비 41.4% 성장했습니다.",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "41.4%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "metric_label": "커머스 부문 매출 성장률",
                        "primary_value": {
                            "status": "ok",
                            "label": "커머스 부문 매출 성장률",
                            "period": "2023",
                            "normalized_value": 41.4,
                            "normalized_unit": "PERCENT",
                            "rendered_value": "41.4%",
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "커머스 부문 매출액",
                            "concept": "revenue",
                            "period": "2023",
                            "normalized_value": 2546649000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "2조 5,466억원",
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "커머스 부문 매출액",
                            "concept": "revenue",
                            "period": "2022",
                            "normalized_value": 1801079000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "1조 8,011억원",
                        },
                    },
                },
            },
        ]

        feedback = self.agent._infer_planner_feedback_from_answer_slots(ordered_results)

        self.assertEqual(feedback, "")

    def test_aggregate_subtasks_ignores_failed_lookup_when_growth_slots_cover_value(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 시설투자(CAPEX) 총액은 53조 1,139억원이며, 이는 전년(2022년)의 53조 1,153억원 대비 0.0026% 감소한 수치입니다.",
                    "planner_feedback": "2023년 시설투자(CAPEX) 총액 direct value가 누락되었습니다.",
                }
            )
        )
        state = {
            "query": "2023년 메모리 반도체 업황 악화에도 불구하고 집행된 시설투자(CAPEX) 총액을 찾고, 전년(2022년) 대비 증감률을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1"},
                {"task_id": "task_4"},
                {"task_id": "task_2"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 시설투자(CAPEX) 총액",
                    "answer": "2023년 시설투자(CAPEX) 총액 계산에 필요한 값(시설투자(CAPEX))을 문서 근거에서 충분히 확인하지 못해 계산할 수 없습니다.",
                    "status": "insufficient_operands",
                    "calculation_result": {},
                },
                {
                    "task_id": "task_4",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022년 시설투자(CAPEX)",
                    "answer": "2022년 시설투자(CAPEX)은 53조 1,153억원입니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "시설투자(CAPEX)",
                                "concept": "capital_expenditure_total",
                                "period": "2022",
                                "rendered_value": "53조 1,153억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "시설투자(CAPEX) 총액 증감률",
                    "answer": "2023년 연결기준 시설투자(CAPEX) 총액 증감률은 2023 시설투자(CAPEX) 53조 1,139억원이 시설투자(CAPEX) 53조 1,153억원 대비 0.0026% 감소한 결과입니다.",
                    "status": "ok",
                    "runtime_evidence": [
                        {
                            "evidence_id": "ev_003",
                            "support_level": "context",
                            "source_anchor": "[삼성전자 | 2023 | IV. 이사의 경영진단 및 분석의견]",
                            "claim": "2023년 세계 경제의 불확실성 지속 및 경기 둔화로 경영 여건이 악화되었으며, 특히 메모리 등 부품 사업이 약세를 보였습니다.",
                        }
                    ],
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "-0.0026%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "시설투자(CAPEX) 총액 증감률",
                                "period": "2023",
                                "rendered_value": "-0.0026%",
                            },
                            "current_value": {
                                "status": "ok",
                                "role": "current_value",
                                "label": "2023 시설투자(CAPEX)",
                                "concept": "capital_expenditure_total",
                                "period": "2023",
                                "rendered_value": "53조 1,139억원",
                            },
                            "prior_value": {
                                "status": "ok",
                                "role": "prior_value",
                                "label": "시설투자(CAPEX)",
                                "concept": "capital_expenditure_total",
                                "period": "2022",
                                "rendered_value": "53조 1,153억원",
                            },
                        },
                    },
                },
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        trace = _resolve_runtime_calculation_trace(updated)
        self.assertEqual(updated["planner_feedback"], "")
        self.assertNotIn("완전히 확정할 수는 없습니다", updated["answer"])
        self.assertIn("메모리", updated["answer"])
        self.assertEqual(trace["calculation_result"]["status"], "ok")

    def test_aggregate_subtasks_repairs_truncated_growth_narrative_answer(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 커머스 부문 매출은 2조 5,466억원이고 전년 대비 41.4% 성장했습니다. 또한 Poshmark 인수는 커머스 실",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 커머스 부문 매출 성장률을 계산하고, Poshmark 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1"},
                {"task_id": "task_2"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "커머스 부문 매출 성장률",
                    "answer": "커머스 부문 매출은 전년 대비 41.4% 성장했습니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "41.4%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출 성장률",
                                "period": "2023",
                                "normalized_value": 41.4,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "41.4%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출액",
                                "concept": "revenue",
                                "period": "2023",
                                "normalized_value": 2546649000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "2조 5,466억원",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출액",
                                "concept": "revenue",
                                "period": "2022",
                                "normalized_value": 1801079000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "1조 8,011억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "Poshmark 인수 영향",
                    "answer": "Poshmark 인수와 연결 편입은 글로벌 C2C 경쟁력 강화와 커머스 실적 성장에 기여했습니다.",
                    "status": "ok",
                    "selected_claim_ids": ["ev_poshmark"],
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {"operation_family": "narrative_summary"},
                    },
                },
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_feedback"], "")
        self.assertIn("2조 5,466억원", updated["answer"])
        self.assertIn("41.4%", updated["answer"])
        self.assertIn("Poshmark", updated["answer"])
        self.assertFalse(updated["answer"].endswith("커머스 실"))
        self.assertIn("ev_poshmark", updated["selected_claim_ids"])

    def test_aggregate_subtasks_repairs_numeric_only_growth_narrative_answer(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": (
                        "2023년 신용손실충당금전입액은 3,146,409백만원이며, "
                        "2022년 1,847,775백만원 대비 70.23% 증가했습니다."
                    ),
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 연결 포괄손익계산서 상의 신용손실충당금전입액 전년 대비 증가율을 계산하고, 그 원인을 리스크 관리 측면에서 요약해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1"},
                {"task_id": "task_2"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "신용손실충당금전입액 증가율",
                    "answer": "70.28%",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "70.28%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "신용손실충당금전입액 증가율",
                                "period": "2023",
                                "normalized_value": 70.28,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "70.28%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "신용손실충당금전입액",
                                "period": "2023",
                                "rendered_value": "3,146,409백만원",
                                "normalized_value": 3146409000000.0,
                                "source_row_ids": ["ev_current"],
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "신용손실충당금전입액",
                                "period": "2022",
                                "rendered_value": "1,847,775백만원",
                                "normalized_value": 1847775000000.0,
                                "source_row_ids": ["ev_prior"],
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "리스크 관리 측면 원인",
                    "answer": "미래경기 불확실성에 대비한 보수적인 충당금적립이 증가 원인입니다.",
                    "status": "ok",
                    "selected_claim_ids": ["ev_risk_driver"],
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {"operation_family": "narrative_summary"},
                    },
                },
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("70.28%", updated["answer"])
        self.assertNotIn("70.23%", updated["answer"])
        self.assertIn("3,146,409백만원", updated["answer"])
        self.assertIn("미래경기 불확실성", updated["answer"])
        self.assertIn("보수적인 충당금적립", updated["answer"])
        self.assertIn("ev_risk_driver", updated["selected_claim_ids"])

    def test_nested_growth_promotion_prefers_sign_consistent_operand_pair(self) -> None:
        sign_mixed_growth = {
            "task_id": "task_1",
            "metric_family": "concept_growth_rate",
            "metric_label": "비용 증가율",
            "answer": "-270.28%",
            "status": "ok",
            "source_row_ids": ["row_current", "task_output:lookup", "row_prior_prose"],
            "calculation_result": {
                "status": "ok",
                "rendered_value": "-270.28%",
                "formatted_result": "-270.28%",
                "source_row_ids": ["row_current", "task_output:lookup", "row_prior_prose"],
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {
                        "status": "ok",
                        "label": "비용 증가율",
                        "period": "2023",
                        "normalized_value": -270.28,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "-270.28%",
                    },
                    "current_value": {
                        "status": "ok",
                        "label": "비용",
                        "period": "2023",
                        "normalized_value": -3146409000000,
                        "normalized_unit": "KRW",
                        "rendered_value": "(3,146,409)백만원",
                        "source_row_ids": ["row_current"],
                    },
                    "prior_value": {
                        "status": "ok",
                        "label": "비용",
                        "period": "2022",
                        "normalized_value": 1847775000000,
                        "normalized_unit": "KRW",
                        "rendered_value": "1,847,775백만원",
                        "source_row_ids": ["task_output:lookup", "row_prior_prose"],
                    },
                },
            },
        }
        signed_pair_growth = {
            "task_id": "task_1",
            "metric_family": "concept_growth_rate",
            "metric_label": "비용 증가율",
            "answer": "70.28%",
            "status": "ok",
            "source_row_ids": ["row_statement"],
            "calculation_result": {
                "status": "ok",
                "rendered_value": "70.28%",
                "formatted_result": "70.28%",
                "source_row_ids": ["row_statement"],
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {
                        "status": "ok",
                        "label": "비용 증가율",
                        "period": "2023",
                        "normalized_value": 70.28,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "70.28%",
                    },
                    "current_value": {
                        "status": "ok",
                        "label": "비용",
                        "period": "2023",
                        "normalized_value": -3146409000000,
                        "normalized_unit": "KRW",
                        "rendered_value": "(3,146,409)백만원",
                        "source_row_ids": ["row_statement"],
                    },
                    "prior_value": {
                        "status": "ok",
                        "label": "비용",
                        "period": "2022",
                        "normalized_value": -1847775000000,
                        "normalized_unit": "KRW",
                        "rendered_value": "(1,847,775)백만원",
                        "source_row_ids": ["row_statement"],
                    },
                },
            },
        }
        aggregate_summary = {
            "task_id": "task_2",
            "metric_family": "narrative_summary",
            "metric_label": "질문 관련 배경/영향 설명",
            "operation_family": "aggregate_subtasks",
            "answer": "비용은 전년 대비 70.28% 증가했습니다.",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "formatted_result": "비용은 전년 대비 70.28% 증가했습니다.",
                "subtask_results": [signed_pair_growth],
                "answer_slots": {
                    "operation_family": "aggregate_subtasks",
                    "subtask_results": [signed_pair_growth],
                },
            },
        }

        promoted = self.agent._promote_stronger_nested_aggregate_results(
            [sign_mixed_growth, aggregate_summary]
        )

        self.assertEqual(promoted[0]["answer"], "70.28%")
        self.assertTrue(promoted[0]["promoted_from_nested_aggregate"])

    def test_aggregate_growth_narrative_filters_table_fragment_noise(self) -> None:
        state = {
            "query": "2023년 커머스 부문 매출 성장률을 계산하고, Poshmark 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1"},
                {"task_id": "task_2"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "커머스 부문 매출 성장률",
                    "answer": "41.4%",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "41.4%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출 성장률",
                                "period": "2023",
                                "normalized_value": 41.4,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "41.4%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출액",
                                "period": "2023",
                                "rendered_value": "2조 5,466억원",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출액",
                                "period": "2022",
                                "rendered_value": "1조 8,011억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "질문 관련 배경/영향 설명",
                    "answer": (
                        "주된 사유는 Poshmark, Inc. 인수 등으로 인한 무형자산 증가 1조 9,641억원 입니다."
                        "- 부채제25기 당사의 부채는 전기 대비 증가하였습니다."
                        "- 자본제25기 자본은 당기순이익 등으로 증가했습니다. "
                        "| 1,488.8 | 1,304.7 | 14.1% | - 영업이익률(%) | 15.4% | 15.9% | -0.5%p | "
                        "개발/운영비는 Poshmark 연결 편입효과로 인해 전년대비 상승하였습니다. "
                        "Poshmark 연결 편입효과에 따른 영업수익 증가가 있었습니다."
                    ),
                    "status": "ok",
                    "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                },
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_driver",
                    "claim": "Poshmark 연결 편입효과에 따른 영업수익 증가가 있었습니다.",
                    "quote_span": "Poshmark 연결 편입효과에 따른 영업수익 증가",
                    "support_level": "direct",
                    "metadata": {"section_path": "IV. 이사의 경영진단 및 분석의견"},
                }
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("41.4%", updated["answer"])
        self.assertIn("Poshmark 연결 편입효과", updated["answer"])
        self.assertNotIn("부채", updated["answer"])
        self.assertNotIn("자본", updated["answer"])
        self.assertNotIn("무형자산", updated["answer"])

    def test_growth_narrative_composition_supplements_uncovered_driver_evidence(self) -> None:
        ordered_results = [
            {
                "task_id": "task_1",
                "metric_family": "concept_growth_rate",
                "metric_label": "커머스 부문 매출 성장률",
                "answer": "41.4%",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {
                            "status": "ok",
                            "label": "커머스 부문 매출 성장률",
                            "period": "2023",
                            "normalized_value": 41.4,
                            "normalized_unit": "PERCENT",
                            "rendered_value": "41.4%",
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "커머스 부문 매출액",
                            "period": "2023",
                            "rendered_value": "2조 5,466억원",
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "커머스 부문 매출액",
                            "period": "2022",
                            "rendered_value": "1조 8,011억원",
                        },
                    },
                },
            },
            {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "metric_label": "질문 관련 배경/영향 설명",
                "answer": (
                    "네이버의 커머스 사업은 스마트스토어와 브랜드스토어의 지속적인 성장, "
                    "그리고 Poshmark의 성공적인 체질 개선 등으로 전년 대비 41.4% 성장했습니다."
                ),
                "status": "ok",
                "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
            },
        ]
        evidence_items = [
            {
                "evidence_id": "ev_driver",
                "claim": "Poshmark 연결 편입효과에 따른 영업수익 증가가 있었습니다.",
                "quote_span": "Poshmark 연결 편입효과에 따른 영업수익 증가",
                "support_level": "direct",
                "metadata": {"section_path": "IV. 이사의 경영진단 및 분석의견"},
            }
        ]

        composed = self.agent._compose_growth_narrative_answer(
            query="커머스 부문의 2023년 매출 성장률을 계산하고, 포시마크(Poshmark) 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            ordered_results=ordered_results,
            existing_answer="",
            evidence_items=evidence_items,
        )

        self.assertIsNotNone(composed)
        answer = composed["compressed_answer"]
        self.assertIn("41.4%", answer)
        self.assertIn("체질 개선", answer)
        self.assertIn("연결 편입효과", answer)
        self.assertIn("ev_driver", composed["selected_claim_ids"])

    def test_aggregate_subtasks_preserves_evidence_built_growth_narrative_after_alignment(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023 commerce revenue was 2,546,649 million, up 41.4% from 1,801,079 million in 2022.",
                    "planner_feedback": "",
                }
            )
        )
        self.agent._align_lookup_results_with_dependency_projection = (
            lambda ordered_results, _state, _projection: list(ordered_results)
        )
        state = {
            "query": "Calculate the 2023 commerce revenue growth rate and summarize the impact of the acquisition (Poshmark).",
            "calc_subtasks": [{"task_id": "task_1"}],
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "commerce revenue growth rate",
                    "answer": "2023 commerce revenue was 2,546,649 million, up 41.4% from 1,801,079 million in 2022.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "41.4%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "commerce revenue growth rate",
                                "period": "2023",
                                "normalized_value": 41.4,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "41.4%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "commerce revenue",
                                "period": "2023",
                                "rendered_value": "2,546,649 million",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "commerce revenue",
                                "period": "2022",
                                "rendered_value": "1,801,079 million",
                            },
                        },
                    },
                },
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_driver",
                    "claim": "The Poshmark acquisition had an integration effect that increased operating revenue.",
                    "quote_span": "Poshmark acquisition integration effect increased operating revenue",
                    "support_level": "direct",
                    "metadata": {"section_path": "IV. 이사의 경영진단 및 분석의견"},
                }
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("41.4%", updated["answer"])
        self.assertIn("Poshmark acquisition", updated["answer"])
        self.assertIn("ev_driver", updated["selected_claim_ids"])

    def test_growth_narrative_prunes_irrelevant_supported_lead_sentence(self) -> None:
        original_policy = {
            key: CALCULATION_NARRATIVE_POLICY.get(key)
            for key in ("growth_query_pattern", "growth_impact_markers", "growth_narrative_markers")
        }
        CALCULATION_NARRATIVE_POLICY["growth_query_pattern"] = r"growth"
        CALCULATION_NARRATIVE_POLICY["growth_impact_markers"] = ("impact", "response", "PolicyA")
        CALCULATION_NARRATIVE_POLICY["growth_narrative_markers"] = ("impact", "response", "PolicyA")
        try:
            ordered_results = [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "regional sales volume growth",
                    "answer": "11.5%",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "regional sales volume growth",
                                "period": "2023",
                                "rendered_value": "11.5%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "regional sales volume",
                                "period": "2023",
                                "rendered_value": "870,000 units",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "regional sales volume",
                                "period": "2022",
                                "rendered_value": "781,000 units",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "policy context",
                    "answer": "The report says PolicyA requires an active response.",
                    "status": "ok",
                    "selected_claim_ids": ["ev_policy"],
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {"operation_family": "narrative_summary"},
                    },
                },
            ]
            evidence_items = [
                {
                    "evidence_id": "ev_policy",
                    "claim": "The report says PolicyA requires an active response.",
                    "quote_span": "PolicyA requires an active response.",
                    "support_level": "direct",
                }
            ]
            answer = (
                "The company improves customer service through pricing. "
                "2023 regional sales volume was 870,000 units, up 11.5% from 781,000 units in 2022. "
                "The report says PolicyA requires an active response."
            )

            pruned = self.agent._prune_irrelevant_growth_narrative_sentences(
                query="Calculate 2023 regional sales volume growth and summarize the impact of PolicyA.",
                answer=answer,
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )

            self.assertNotIn("customer service through pricing", pruned)
            self.assertIn("870,000 units", pruned)
            self.assertIn("11.5%", pruned)
            self.assertIn("PolicyA requires an active response", pruned)
        finally:
            for key, value in original_policy.items():
                CALCULATION_NARRATIVE_POLICY[key] = value

    def test_numeric_refresh_prunes_irrelevant_boilerplate_context_sentence(self) -> None:
        original_policy = {
            key: CALCULATION_NARRATIVE_POLICY.get(key)
            for key in ("growth_query_pattern", "growth_impact_markers", "growth_narrative_markers")
        }
        CALCULATION_NARRATIVE_POLICY["growth_query_pattern"] = r"growth"
        CALCULATION_NARRATIVE_POLICY["growth_impact_markers"] = ("impact", "pressure", "reduced")
        CALCULATION_NARRATIVE_POLICY["growth_narrative_markers"] = ("impact", "pressure", "reduced")
        try:
            ordered_results = [
                {
                    "task_id": "task_growth",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "segment profit growth",
                    "operation_family": "growth_rate",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "-20.0%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "segment profit growth",
                                "period": "2023",
                                "rendered_value": "-20.0%",
                                "normalized_value": -20.0,
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "segment profit",
                                "period": "2023",
                                "rendered_value": "80 million",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "segment profit",
                                "period": "2022",
                                "rendered_value": "100 million",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_narrative",
                    "metric_family": "narrative_summary",
                    "operation_family": "narrative_summary",
                    "answer": "MarginX pressure reduced segment profit.",
                    "status": "ok",
                    "selected_claim_ids": ["ev_driver"],
                    "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                },
            ]
            evidence_items = [
                {
                    "evidence_id": "ev_driver",
                    "claim": "MarginX pressure reduced segment profit.",
                    "quote_span": "MarginX pressure reduced segment profit.",
                }
            ]
            current_answer = (
                "2023 segment profit was 80 million, from 2022 100 million, down -20.0%. "
                "The forward-looking warning discusses uncertain future assumptions that may impact results. "
                "MarginX pressure reduced segment profit."
            )

            refreshed = self.agent._refresh_numeric_answer_preserving_narrative_context(
                query="Calculate segment profit growth and summarize the impact of MarginX.",
                current_answer=current_answer,
                numeric_answer="2023 segment profit was 80 million, from 2022 100 million, down -20.0%.",
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )

            self.assertIn("20.0%", refreshed["answer"])
            self.assertIn("MarginX pressure", refreshed["answer"])
            self.assertNotIn("forward-looking warning", refreshed["answer"])
        finally:
            for key, value in original_policy.items():
                CALCULATION_NARRATIVE_POLICY[key] = value

    def test_growth_narrative_prunes_untraced_numeric_driver_sentence(self) -> None:
        original_policy = {
            key: CALCULATION_NARRATIVE_POLICY.get(key)
            for key in ("growth_query_pattern", "growth_impact_markers", "growth_narrative_markers")
        }
        original_driver_groups = self.agent._narrative_driver_groups
        CALCULATION_NARRATIVE_POLICY["growth_query_pattern"] = r"growth"
        CALCULATION_NARRATIVE_POLICY["growth_impact_markers"] = ("impact", "growth", "effect")
        CALCULATION_NARRATIVE_POLICY["growth_narrative_markers"] = ("impact", "growth", "effect", "turnaround")
        self.agent._narrative_driver_groups = lambda _query: []
        try:
            ordered_results = [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "segment revenue growth",
                    "operation_family": "growth_rate",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "41.4%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "segment revenue growth",
                                "period": "2023",
                                "rendered_value": "41.4%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "period": "2023",
                                "rendered_value": "2,546,649 million",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "period": "2022",
                                "rendered_value": "1,801,079 million",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "operation_family": "narrative_summary",
                    "answer": "AcquisitionX turnaround improved segment growth.",
                    "status": "ok",
                    "selected_claim_ids": ["ev_driver"],
                    "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                },
            ]
            evidence_items = [
                {
                    "evidence_id": "ev_driver",
                    "claim": "AcquisitionX turnaround improved segment growth.",
                    "quote_span": "AcquisitionX turnaround improved segment growth.",
                }
            ]
            answer = (
                "2023 segment revenue was 2,546,649 million, up 41.4% from 1,801,079 million in 2022. "
                "AcquisitionX turnaround improved segment growth. "
                "The acquisition effect increased operating expense by 24.3%."
            )

            pruned = self.agent._prune_irrelevant_growth_narrative_sentences(
                query="Calculate segment revenue growth and summarize the impact of AcquisitionX.",
                answer=answer,
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )

            self.assertIn("41.4%", pruned)
            self.assertIn("AcquisitionX turnaround", pruned)
            self.assertNotIn("24.3%", pruned)
        finally:
            self.agent._narrative_driver_groups = original_driver_groups
            for key, value in original_policy.items():
                CALCULATION_NARRATIVE_POLICY[key] = value

    def test_growth_numeric_guard_allows_source_supported_narrative_numbers(self) -> None:
        ordered_results = [
            {
                "task_id": "task_1",
                "metric_family": "concept_growth_rate",
                "metric_label": "segment revenue growth",
                "operation_family": "growth_rate",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "41.4%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {
                            "status": "ok",
                            "label": "segment revenue growth",
                            "period": "2023",
                            "rendered_value": "41.4%",
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "period": "2023",
                            "rendered_value": "2,546,649 million",
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "period": "2022",
                            "rendered_value": "1,801,079 million",
                        },
                    },
                },
            }
        ]
        answer = (
            "2023 segment revenue was 2,546,649 million, up 41.4% from 1,801,079 million in 2022. "
            "The acquisition effect increased operating expense by 24.3%."
        )

        self.assertTrue(
            self.agent._growth_answer_has_untraced_numeric_material(
                answer,
                ordered_results,
                evidence_items=[],
            )
        )
        self.assertFalse(
            self.agent._growth_answer_has_untraced_numeric_material(
                answer,
                ordered_results,
                evidence_items=[
                    {
                        "evidence_id": "ev_driver",
                        "claim": "The acquisition effect increased operating expense by 24.3%.",
                        "quote_span": "operating expense by 24.3%",
                    }
                ],
            )
        )

    def test_retrieved_doc_narrative_evidence_is_selected_for_final_answer(self) -> None:
        evidence_items = [
            {
                "evidence_id": "ev_numeric",
                "source_anchor": "[ExampleCo | 2023 | Market]",
                "claim": "2023 regional sales volume was 870,000 units, up 11.5%.",
                "quote_span": "2023 regional sales volume was 870,000 units, up 11.5%.",
            }
        ]
        docs = [
            (
                Document(
                    page_content="The report says PolicyA requires an active response from management.",
                    metadata={
                        "company": "ExampleCo",
                        "year": 2023,
                        "section_path": "Management discussion",
                    },
                ),
                0.9,
            )
        ]

        updated, selected_ids = self.agent._append_retrieved_narrative_evidence_for_final_answer(
            evidence_items,
            final_answer=(
                "2023 regional sales volume was 870,000 units, up 11.5%. "
                "The report says PolicyA requires an active response from management."
            ),
            docs=docs,
        )

        self.assertEqual(len(selected_ids), 1)
        self.assertTrue(selected_ids[0].startswith("retrieved_narrative::"))
        selected = next(item for item in updated if item["evidence_id"] == selected_ids[0])
        self.assertIn("PolicyA requires an active response", selected["claim"])
        self.assertEqual(selected["metadata"]["section_path"], "Management discussion")

    def test_retrieved_doc_narrative_evidence_skips_missing_answer_sentences(self) -> None:
        docs = [
            (
                Document(
                    page_content="The report discusses unrelated sustainability initiatives.",
                    metadata={"company": "ExampleCo", "year": 2023, "section_path": "Sustainability"},
                ),
                0.9,
            )
        ]

        updated, selected_ids = self.agent._append_retrieved_narrative_evidence_for_final_answer(
            [],
            final_answer="요청한 수치는 제공된 보고서에서 찾을 수 없습니다.",
            docs=docs,
        )

        self.assertEqual(updated, [])
        self.assertEqual(selected_ids, [])

    def test_retrieved_narrative_source_surface_replaces_overstated_paraphrase(self) -> None:
        answer = (
            "2023 regional sales volume was 870,000 units, up 11.5%. "
            "The company stated that PolicyA requires an active response."
        )
        updated = self.agent._preserve_retrieved_narrative_source_surface(
            answer,
            [
                {
                    "evidence_id": "retrieved_narrative::001",
                    "claim": "The company stated that PolicyA requires an active response.",
                    "quote_span": "PolicyA requires an active response from management.",
                }
            ],
        )

        self.assertIn("870,000 units", updated)
        self.assertIn("11.5%", updated)
        self.assertIn("PolicyA requires an active response from management.", updated)
        self.assertNotIn("The company stated", updated)

    def test_retrieved_narrative_source_surface_keeps_missing_answer_sentence(self) -> None:
        answer = "요청한 수치는 제공된 보고서에서 찾을 수 없습니다."

        updated = self.agent._preserve_retrieved_narrative_source_surface(
            answer,
            [
                {
                    "evidence_id": "retrieved_narrative::001",
                    "claim": "요청한 수치는 제공된 보고서에서 찾을 수 없습니다.",
                    "quote_span": "The report discusses unrelated sustainability initiatives.",
                }
            ],
        )

        self.assertEqual(updated, answer)

    def test_growth_narrative_composition_uses_evidence_quote_driver_groups(self) -> None:
        original_policy = {
            key: CALCULATION_NARRATIVE_POLICY.get(key)
            for key in ("growth_query_pattern", "growth_impact_markers", "growth_narrative_markers")
        }
        original_driver_groups = self.agent._narrative_driver_groups
        CALCULATION_NARRATIVE_POLICY["growth_query_pattern"] = r"growth"
        CALCULATION_NARRATIVE_POLICY["growth_impact_markers"] = ("impact", "growth", "turnaround")
        CALCULATION_NARRATIVE_POLICY["growth_narrative_markers"] = ("impact", "growth", "turnaround")
        self.agent._narrative_driver_groups = lambda _query: [
            {
                "label": "store_growth",
                "variants": ("StoreA", "BrandB"),
                "phrase": "StoreA and BrandB growth",
            },
            {
                "label": "turnaround",
                "variants": ("AcquisitionX",),
                "phrase": "AcquisitionX turnaround",
            },
        ]
        try:
            ordered_results = [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "segment revenue growth",
                    "answer": "41.4%",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "segment revenue growth",
                                "period": "2023",
                                "normalized_value": 41.4,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "41.4%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "period": "2023",
                                "rendered_value": "2,546,649 million",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "period": "2022",
                                "rendered_value": "1,801,079 million",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "impact context",
                    "answer": "AcquisitionX turnaround improved segment growth.",
                    "status": "ok",
                    "selected_claim_ids": ["ev_driver"],
                    "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                },
            ]
            evidence_items = [
                {
                    "evidence_id": "ev_driver",
                    "claim": "AcquisitionX turnaround improved segment growth.",
                    "quote_span": "StoreA and BrandB growth plus AcquisitionX turnaround improved segment growth.",
                    "support_level": "direct",
                }
            ]
            existing_answer = (
                "2023 segment revenue was 2,546,649 million, up 41.4% "
                "from 1,801,079 million in 2022. "
                "AcquisitionX turnaround improved segment growth."
            )

            composed = self.agent._compose_growth_narrative_answer(
                query="Calculate 2023 segment revenue growth and explain the impact of AcquisitionX.",
                ordered_results=ordered_results,
                existing_answer=existing_answer,
                evidence_items=evidence_items,
            )

            self.assertIsNotNone(composed)
            self.assertIn("StoreA", composed["compressed_answer"])
            self.assertIn("BrandB", composed["compressed_answer"])
            self.assertIn("ev_driver", composed["selected_claim_ids"])
        finally:
            self.agent._narrative_driver_groups = original_driver_groups
            for key, value in original_policy.items():
                CALCULATION_NARRATIVE_POLICY[key] = value

    def test_source_stated_growth_composition_preserves_traced_prior_display(self) -> None:
        original_policy = {
            key: CALCULATION_NARRATIVE_POLICY.get(key)
            for key in (
                "growth_query_pattern",
                "growth_impact_markers",
                "growth_narrative_markers",
                "growth_numeric_sentence_template",
                "prior_phrase_with_value_template",
                "prior_phrase_template",
                "period_year_suffix",
                "period_prefix_with_year_template",
                "period_prefix_template",
                "direction_words",
            )
        }
        CALCULATION_NARRATIVE_POLICY["growth_query_pattern"] = r"growth"
        CALCULATION_NARRATIVE_POLICY["growth_impact_markers"] = ("impact", "needed")
        CALCULATION_NARRATIVE_POLICY["growth_narrative_markers"] = ("impact", "needed")
        CALCULATION_NARRATIVE_POLICY["growth_numeric_sentence_template"] = (
            "{period_prefix}{metric_label} was {current_value}, {prior_phrase}{growth_value} {direction_word}."
        )
        CALCULATION_NARRATIVE_POLICY["prior_phrase_with_value_template"] = "from {period} {value}, "
        CALCULATION_NARRATIVE_POLICY["prior_phrase_template"] = "from {period}, "
        CALCULATION_NARRATIVE_POLICY["period_year_suffix"] = "Y"
        CALCULATION_NARRATIVE_POLICY["period_prefix_with_year_template"] = "{period}Y "
        CALCULATION_NARRATIVE_POLICY["period_prefix_template"] = "{period} "
        CALCULATION_NARRATIVE_POLICY["direction_words"] = {"increase": "up", "growth": "up", "decrease": "down"}
        try:
            ordered_results = [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "regional sales volume growth",
                    "answer": "11.5%",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "regional sales volume growth",
                                "period": "2023",
                                "normalized_value": 11.5,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "11.5%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "regional sales volume",
                                "period": "2023",
                                "rendered_value": "870.0 thousand units",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "regional sales volume",
                                "period": "2022",
                                "rendered_value": "781.0 thousand units",
                            },
                        },
                    },
                    "calculation_operands": [
                        {
                            "matched_operand_role": "current_period",
                            "stated_change_raw_value": "11.5",
                            "stated_change_raw_unit": "%",
                        }
                    ],
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "policy context",
                    "answer": "Policy response is needed.",
                    "status": "ok",
                    "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                },
            ]
            composed = self.agent._compose_growth_narrative_answer(
                query="Calculate regional sales volume growth and explain policy impact.",
                ordered_results=ordered_results,
                existing_answer="",
                evidence_items=[
                    {
                        "evidence_id": "ev_policy",
                        "claim": "Policy response is needed.",
                        "quote_span": "Policy response is needed.",
                    }
                ],
            )

            self.assertIsNotNone(composed)
            self.assertIn("870.0 thousand units", composed["compressed_answer"])
            self.assertIn("11.5%", composed["compressed_answer"])
            self.assertIn("781.0 thousand units", composed["compressed_answer"])
            self.assertIn("from 2022Y 781.0 thousand units", composed["compressed_answer"])
            numeric_answer = self.agent._compose_complete_growth_numeric_answer(
                ordered_results[0],
                ordered_results,
                evidence_items=[],
            )
            self.assertIn("870.0 thousand units", numeric_answer)
            self.assertIn("11.5%", numeric_answer)
            self.assertIn("781.0 thousand units", numeric_answer)
        finally:
            for key, value in original_policy.items():
                CALCULATION_NARRATIVE_POLICY[key] = value

    def test_source_stated_growth_contract_restores_missing_prior_phrase(self) -> None:
        original_policy = {
            key: CALCULATION_NARRATIVE_POLICY.get(key)
            for key in (
                "growth_numeric_sentence_template",
                "prior_phrase_with_value_template",
                "direction_words",
            )
        }
        CALCULATION_NARRATIVE_POLICY["growth_numeric_sentence_template"] = (
            "{period_prefix}{metric_label} was {current_value}, {prior_phrase}{growth_value} {direction_word}."
        )
        CALCULATION_NARRATIVE_POLICY["prior_phrase_with_value_template"] = "from {period} {value}, "
        CALCULATION_NARRATIVE_POLICY["direction_words"] = {"increase": "up", "growth": "up", "decrease": "down"}
        try:
            ordered_results = [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "regional sales volume growth",
                    "answer": "11.5%",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "derived_metrics": {"source_stated_result_used": True},
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "regional sales volume growth",
                                "period": "2023",
                                "normalized_value": 11.5,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "11.5%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "regional sales volume",
                                "period": "2023",
                                "rendered_value": "870.0 thousand units",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "regional sales volume",
                                "period": "2022",
                                "rendered_value": "781.0 thousand units",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "policy context",
                    "answer": "Policy response is needed.",
                    "status": "ok",
                    "selected_claim_ids": ["ev_policy"],
                    "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                },
            ]
            incomplete_answer = (
                "2023 regional sales volume was 870.0 thousand units, 11.5% up. "
                "Policy response is needed."
            )

            contracted = self.agent._enforce_source_stated_growth_answer_contract(
                incomplete_answer,
                ordered_results,
                evidence_items=[],
            )

            self.assertIn("870.0 thousand units", contracted)
            self.assertIn("11.5%", contracted)
            self.assertIn("Policy response is needed.", contracted)
            self.assertIn("781.0 thousand units", contracted)
        finally:
            for key, value in original_policy.items():
                CALCULATION_NARRATIVE_POLICY[key] = value

    def test_selected_and_operand_evidence_filter_drops_unselected_numeric_chunk(self) -> None:
        evidence_items = [
            {
                "evidence_id": "ev_selected",
                "claim": "2023 regional sales volume was 870,000 units and growth was 11.5%.",
                "quote_span": "2023 regional sales volume was 870,000 units and growth was 11.5%.",
            },
            {
                "evidence_id": "operand::prior",
                "claim": "2022 regional sales volume 781,000 units",
                "quote_span": "2022 regional sales volume 781,000 units",
                "metadata": {"supports_answer_numeric_surface": True},
            },
            {
                "evidence_id": "ev_unselected_long_chunk",
                "claim": "Unrelated lead text. 2022 regional sales volume 781,000 units appears later.",
                "quote_span": "Unrelated lead text.",
                "raw_row_text": "Unrelated lead text. 2022 regional sales volume 781,000 units appears later.",
            },
        ]

        filtered = self.agent._filter_aggregate_evidence_for_final_answer(
            evidence_items,
            final_answer=(
                "2023 regional sales volume was 870,000 units, up 11.5% "
                "from 781,000 units in 2022."
            ),
            selected_claim_ids=["ev_selected", "ev_unselected_long_chunk"],
        )

        filtered_ids = [item["evidence_id"] for item in filtered]
        self.assertIn("ev_selected", filtered_ids)
        self.assertIn("operand::prior", filtered_ids)
        self.assertNotIn("ev_unselected_long_chunk", filtered_ids)

    def test_operand_evidence_uses_rendered_display_surface(self) -> None:
        updated = self.agent._append_operand_evidence_for_final_answer(
            [],
            operands=[
                {
                    "operand_id": "prior",
                    "matched_operand_role": "prior_period",
                    "label": "regional sales volume",
                    "period": "2022",
                    "raw_value": "781000",
                    "raw_unit": "units",
                    "rendered_value": "781.0 thousand units",
                    "normalized_value": 781000.0,
                    "normalized_unit": "COUNT",
                    "source_anchor": "[ExampleCo | 2022 | Sales]",
                    "source_quote": "The 2022 regional sales volume was 781.0 thousand units.",
                }
            ],
            final_answer="2023 sales rose 11.5% from 781.0 thousand units in 2022.",
        )

        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["evidence_id"], "operand::prior")
        self.assertEqual(updated[0]["quote_span"], "The 2022 regional sales volume was 781.0 thousand units.")
        self.assertTrue(updated[0]["metadata"]["supports_answer_numeric_surface"])
        filtered = self.agent._filter_aggregate_evidence_for_final_answer(
            updated,
            final_answer="2023 sales rose 11.5% from 781.0 thousand units in 2022.",
            selected_claim_ids=[],
        )
        self.assertEqual([item["evidence_id"] for item in filtered], ["operand::prior"])

    def test_growth_narrative_requires_all_supported_policy_driver_groups(self) -> None:
        original_driver_groups = self.agent._narrative_driver_groups
        self.agent._narrative_driver_groups = lambda _query: [
            {"label": "driver_a", "variants": ["DriverA"], "phrase": "DriverA expansion"},
            {"label": "driver_b", "variants": ["DriverB"], "phrase": "DriverB expansion"},
            {"label": "driver_c", "variants": ["DriverC"], "phrase": "DriverC expansion"},
        ]
        ordered_results = [
            {
                "task_id": "task_1",
                "metric_family": "concept_growth_rate",
                "metric_label": "revenue growth rate",
                "answer": "41.4%",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {
                            "status": "ok",
                            "label": "revenue growth rate",
                            "period": "2023",
                            "rendered_value": "41.4%",
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "revenue",
                            "period": "2023",
                            "rendered_value": "2,546,649 million",
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "revenue",
                            "period": "2022",
                            "rendered_value": "1,801,079 million",
                        },
                    },
                },
            },
            {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "metric_label": "drivers",
                "answer": (
                    "DriverA expansion contributed to growth. "
                    "DriverB expansion contributed to growth. "
                    "DriverC expansion contributed to growth."
                ),
                "status": "ok",
                "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
            },
        ]
        query = "Calculate the 2023 revenue 성장률 and summarize the impact of DriverA, DriverB, and DriverC."
        try:
            composed = self.agent._compose_growth_narrative_answer(
                query=query,
                ordered_results=ordered_results,
                existing_answer="",
                evidence_items=[],
            )
            self.assertIsNotNone(composed)
            answer = composed["compressed_answer"]
            self.assertIn("DriverA", answer)
            self.assertIn("DriverB", answer)
            self.assertIn("DriverC", answer)
            self.assertFalse(
                self.agent._answer_satisfies_growth_narrative_intent(
                    query=query,
                    answer="2023 revenue was 2,546,649 million, up 41.4% from 1,801,079 million. DriverA expansion contributed to growth.",
                    ordered_results=ordered_results,
                    evidence_items=[],
                )
            )
            self.assertTrue(
                self.agent._answer_satisfies_growth_narrative_intent(
                    query=query,
                    answer=answer,
                    ordered_results=ordered_results,
                    evidence_items=[],
                )
            )
        finally:
            self.agent._narrative_driver_groups = original_driver_groups

    def test_retrieved_docs_can_supply_missing_growth_driver_evidence(self) -> None:
        original_driver_groups = self.agent._narrative_driver_groups
        self.agent._narrative_driver_groups = lambda _query: [
            {"label": "driver_a", "variants": ["DriverA"], "phrase": "DriverA expansion"},
            {"label": "driver_b", "variants": ["DriverB"], "phrase": "DriverB expansion | noisy table"},
        ]
        try:
            evidence = self.agent._append_retrieved_growth_driver_evidence_for_query(
                [
                    {
                        "evidence_id": "ev_driver_a",
                        "claim": "DriverA expansion contributed to growth.",
                        "quote_span": "DriverA expansion contributed to growth.",
                    }
                ],
                query="Calculate 2023 revenue growth and summarize the acquisition impact.",
                docs=[
                    (
                        Document(
                            page_content=(
                                "The segment grew because DriverB expansion improved marketplace traffic. | noisy table tail "
                                "Unrelated operating cost text follows."
                            ),
                            metadata={"section_path": "Management discussion"},
                        ),
                        0.9,
                    )
                ],
            )

            retrieved = [item for item in evidence if str(item.get("evidence_id") or "").startswith("retrieved_driver::")]
            self.assertEqual(len(retrieved), 1)
            self.assertEqual(retrieved[0]["claim"], "DriverB expansion")
            self.assertNotIn("|", retrieved[0]["quote_span"])
        finally:
            self.agent._narrative_driver_groups = original_driver_groups

    def test_retrieved_growth_driver_evidence_compacts_numeric_table_tail(self) -> None:
        original_driver_groups = self.agent._narrative_driver_groups
        self.agent._narrative_driver_groups = lambda _query: [
            {"label": "driver_b", "variants": ["DriverB effect"], "phrase": "DriverB effect"},
        ]
        try:
            evidence = self.agent._append_retrieved_growth_driver_evidence_for_query(
                [],
                query="Calculate 2023 revenue growth and summarize the acquisition impact.",
                docs=[
                    (
                        Document(
                            page_content=(
                                "segment | current | prior | change | operating costs rose because DriverB effect "
                                "increased development expense by 24.3% and excluding DriverB effect it rose 14.7%."
                            ),
                            metadata={"section_path": "Management discussion"},
                        ),
                        0.9,
                    )
                ],
            )

            retrieved = [item for item in evidence if str(item.get("evidence_id") or "").startswith("retrieved_driver::")]
            self.assertEqual(len(retrieved), 1)
            self.assertEqual("DriverB effect", retrieved[0]["claim"])
            self.assertEqual("DriverB effect", retrieved[0]["quote_span"])
            self.assertIn("24.3%", retrieved[0]["metadata"]["raw_driver_quote_span"])
        finally:
            self.agent._narrative_driver_groups = original_driver_groups

    def test_aggregate_growth_narrative_uses_retrieved_doc_driver_evidence(self) -> None:
        self.agent.llm = None
        original_driver_groups = self.agent._narrative_driver_groups
        self.agent._narrative_driver_groups = lambda _query: [
            {"label": "driver_a", "variants": ["DriverA"], "phrase": "DriverA expansion"},
            {"label": "driver_b", "variants": ["DriverB"], "phrase": "DriverB expansion"},
        ]
        try:
            state = {
                "query": "Calculate 2023 revenue growth and summarize the acquisition impact.",
                "calc_subtasks": [{"task_id": "task_1"}, {"task_id": "task_2"}],
                "active_subtask_index": 1,
                "active_subtask": {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "operation_family": "narrative_summary",
                },
                "subtask_results": [
                    {
                        "task_id": "task_1",
                        "metric_family": "concept_growth_rate",
                        "metric_label": "revenue growth rate",
                        "answer": "41.4%",
                        "status": "ok",
                        "calculation_result": {
                            "status": "ok",
                            "answer_slots": {
                                "operation_family": "growth_rate",
                                "primary_value": {
                                    "status": "ok",
                                    "label": "revenue growth rate",
                                    "period": "2023",
                                    "rendered_value": "41.4%",
                                    "normalized_value": 41.4,
                                    "normalized_unit": "PERCENT",
                                },
                                "current_value": {
                                    "status": "ok",
                                    "label": "revenue",
                                    "period": "2023",
                                    "rendered_value": "2,546,649 million",
                                },
                                "prior_value": {
                                    "status": "ok",
                                    "label": "revenue",
                                    "period": "2022",
                                    "rendered_value": "1,801,079 million",
                                },
                            },
                        },
                    },
                    {
                        "task_id": "task_2",
                        "metric_family": "narrative_summary",
                        "metric_label": "drivers",
                        "answer": "DriverA expansion contributed to growth.",
                        "status": "ok",
                        "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                    },
                ],
                "retrieved_docs": [
                    (
                        Document(
                            page_content="DriverB expansion also improved marketplace traffic and contributed to growth.",
                            metadata={"section_path": "Management discussion"},
                        ),
                        0.9,
                    )
                ],
                "plan_loop_count": 2,
                "artifacts": [],
            }

            updated = self.agent._aggregate_calculation_subtasks(state)

            self.assertIn("41.4%", updated["answer"])
            self.assertIn("DriverA", updated["answer"])
            self.assertIn("DriverB", updated["answer"])
            self.assertTrue(
                any(str(claim_id).startswith("retrieved_driver::") for claim_id in updated["selected_claim_ids"])
            )
        finally:
            self.agent._narrative_driver_groups = original_driver_groups

    def test_preserve_source_visible_query_terms_from_retrieved_docs(self) -> None:
        answer = self.agent._preserve_source_visible_query_terms(
            "Adjusted operating income is 100 million.",
            query="Calculate adjusted operating income excluding Alpha Program (ABC) and production credit (XYZ).",
            ordered_results=[],
            evidence_items=[],
            docs=[
                (
                    Document(
                        page_content="Alpha Program (ABC) and production credit (XYZ) are included in the source disclosure.",
                        metadata={"section_path": "Management discussion"},
                    ),
                    0.8,
                )
            ],
        )

        self.assertIn("ABC", answer)
        self.assertIn("XYZ", answer)

    def test_preserve_query_terms_from_ontology_alias_binding(self) -> None:
        answer = self.agent._preserve_source_visible_query_terms(
            "LG에너지솔루션 2023년 연결기준 영업이익은 2,163,234백만원입니다. "
            "첨단제조 생산세액공제 금액은 676,874백만원이며, 이를 제외한 실질 영업이익은 1,486,360백만원입니다.",
            query="2023년 연결기준 영업이익을 확인하고, 미국 인플레이션 감축법(IRA)에 따른 세액공제(AMPC) 금액을 제외했을 때의 실질 영업이익을 계산해 줘.",
            ordered_results=[],
            evidence_items=[],
            docs=[],
        )

        self.assertIn("IRA", answer)
        self.assertIn("AMPC", answer)

    def test_format_citations_prefers_selected_evidence_source_anchor(self) -> None:
        state = {
            "selected_claim_ids": ["ev_driver"],
            "evidence_items": [
                {
                    "evidence_id": "ev_driver",
                    "source_anchor": "[ExampleCo | 2023 | Management]",
                    "claim": "Selected driver evidence.",
                    "metadata": {
                        "company": "ExampleCo",
                        "year": 2023,
                        "section_path": "Management discussion",
                    },
                },
                {
                    "evidence_id": "ev_unused",
                    "source_anchor": "[ExampleCo | 2023 | Unused section]",
                    "claim": "Unused evidence.",
                },
            ],
            "retrieved_docs": [
                (
                    Document(
                        page_content="table text",
                        metadata={
                            "company": "ExampleCo",
                            "year": 2023,
                            "report_type": "annual report",
                            "section_path": "Financial statements",
                            "block_type": "table",
                            "chunk_uid": "chunk_1",
                        },
                    ),
                    0.9,
                )
            ],
        }

        result = self.agent._format_citations(state)

        self.assertEqual(result["citations"][0], "[ExampleCo | 2023 | Management discussion]")
        self.assertNotIn("[ExampleCo | 2023 | Unused section]", result["citations"])
        self.assertTrue(any("Financial statements" in citation for citation in result["citations"]))

    def test_runtime_evidence_item_resolves_metadata_from_short_source_anchor(self) -> None:
        item = EvidenceItem(
            source_anchor="ExampleCo | 2023 | Management",
            claim="Selected driver evidence.",
            quote_span="driver evidence",
            support_level="direct",
            question_relevance="high",
        )
        anchor_lookup = {
            "[ExampleCo | 2023 | Management discussion > Performance]": [
                {
                    "metadata": {
                        "company": "ExampleCo",
                        "year": 2023,
                        "section_path": "Management discussion > Performance",
                        "block_type": "paragraph",
                    },
                    "page_content": "Selected driver evidence.",
                }
            ]
        }

        result = self.agent._build_runtime_evidence_item(item, 1, anchor_lookup)

        self.assertEqual(result["metadata"]["section_path"], "Management discussion > Performance")

    def test_dependency_rows_keep_resolved_task_output_slot_over_evidence_pool(self) -> None:
        state = {
            "active_subtask": {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "operation_family": "growth_rate",
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "revenue",
                        "period": "2023",
                        "label": "2023 segment revenue",
                        "preferred_task_id": "task_current",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 segment revenue",
                    "operation_family": "lookup",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "concept": "revenue",
                                "period": "2023",
                                "raw_value": "2,546,649",
                                "raw_unit": "million",
                                "normalized_value": 2546649000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "2,546,649 million",
                                "source_row_id": "ev_current",
                            }
                        },
                    },
                }
            ],
            "evidence_items": [{"evidence_id": "ev_current"}],
        }
        preferred_slot = {
            "status": "ok",
            "label": "segment revenue",
            "concept": "revenue",
            "period": "2023",
            "raw_value": "3,589,061",
            "raw_unit": "thousand",
            "normalized_value": 3589061000000.0,
            "normalized_unit": "KRW",
            "rendered_value": "3,589,061 thousand",
            "source_row_id": "ev_direct",
        }
        self.agent._best_direct_lookup_slot_from_evidence_pool = lambda _binding, _pool: (preferred_slot, 10.0)
        self.agent._direct_structured_lookup_evidence_score = lambda _binding, _evidence: 0.0

        rows = self.agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["raw_value"], "2,546,649")
        self.assertEqual(rows[0]["raw_unit"], "million")
        self.assertEqual(rows[0]["normalized_value"], 2546649000000.0)
        self.assertEqual(rows[0]["source_row_ids"], ["task_output:task_current", "ev_current"])

    def test_dependency_alignment_preserves_task_output_when_direct_value_has_distinct_provenance(self) -> None:
        dependency_rows = [
            {
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "100",
                "raw_unit": "unit",
                "normalized_value": 100.0,
                "normalized_unit": "COUNT",
                "source_task_id": "task_lookup",
                "source_row_id": "task_output:task_lookup",
                "source_row_ids": ["task_output:task_lookup", "ev_lookup"],
                "dependency_resolved": True,
            }
        ]
        direct_rows = [
            {
                "evidence_id": "ev_direct_num",
                "source_row_id": "ev_direct_num",
                "source_row_ids": ["ev_direct_num"],
                "table_source_id": "table_a",
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "80",
                "raw_unit": "unit",
                "normalized_value": 80.0,
                "normalized_unit": "COUNT",
            },
            {
                "evidence_id": "ev_direct_den",
                "source_row_id": "ev_direct_den",
                "source_row_ids": ["ev_direct_den"],
                "table_source_id": "table_a",
                "label": "base value",
                "matched_operand_label": "base value",
                "matched_operand_role": "denominator_1",
                "raw_value": "40",
                "raw_unit": "unit",
                "normalized_value": 40.0,
                "normalized_unit": "COUNT",
            },
        ]

        rows = self.agent._align_dependency_rows_with_sibling_direct_context(dependency_rows, direct_rows)

        self.assertEqual(rows[0]["raw_value"], "100")
        self.assertEqual(rows[0]["normalized_value"], 100.0)
        self.assertEqual(rows[0]["source_row_ids"], ["task_output:task_lookup", "ev_lookup"])
        self.assertTrue(rows[0]["sibling_table_context_realignment_blocked"])
        self.assertNotIn("sibling_table_context_realigned", rows[0])

    def test_dependency_alignment_preserves_task_output_only_row_when_direct_value_conflicts(self) -> None:
        dependency_rows = [
            {
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "120",
                "raw_unit": "unit",
                "normalized_value": 120.0,
                "normalized_unit": "COUNT",
                "source_task_id": "task_lookup",
                "source_row_id": "task_output:task_lookup",
                "source_row_ids": ["task_output:task_lookup"],
                "dependency_resolved": True,
            }
        ]
        direct_rows = [
            {
                "evidence_id": "ev_direct_num",
                "source_row_id": "ev_direct_num",
                "source_row_ids": ["ev_direct_num"],
                "table_source_id": "table_a",
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "70",
                "raw_unit": "unit",
                "normalized_value": 70.0,
                "normalized_unit": "COUNT",
            },
            {
                "evidence_id": "ev_direct_den",
                "source_row_id": "ev_direct_den",
                "source_row_ids": ["ev_direct_den"],
                "table_source_id": "table_a",
                "label": "base value",
                "matched_operand_label": "base value",
                "matched_operand_role": "denominator_1",
                "raw_value": "30",
                "raw_unit": "unit",
                "normalized_value": 30.0,
                "normalized_unit": "COUNT",
            },
        ]

        rows = self.agent._align_dependency_rows_with_sibling_direct_context(dependency_rows, direct_rows)

        self.assertEqual(rows[0]["raw_value"], "120")
        self.assertEqual(rows[0]["normalized_value"], 120.0)
        self.assertEqual(rows[0]["source_row_ids"], ["task_output:task_lookup"])
        self.assertTrue(rows[0]["sibling_table_context_realignment_blocked"])
        self.assertNotIn("sibling_table_context_realigned", rows[0])

    def test_dependency_alignment_preserves_source_task_row_when_shared_id_has_conflicting_anchor(self) -> None:
        dependency_rows = [
            {
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "120",
                "raw_unit": "unit",
                "normalized_value": 120.0,
                "normalized_unit": "COUNT",
                "source_task_id": "task_lookup",
                "source_row_id": "ev_shared",
                "source_row_ids": ["ev_shared"],
                "source_anchor": "source task table",
                "dependency_resolved": True,
            }
        ]
        direct_rows = [
            {
                "evidence_id": "ev_shared",
                "source_row_id": "ev_shared",
                "source_row_ids": ["ev_shared"],
                "source_anchor": "direct sibling table",
                "table_source_id": "table_a",
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "70",
                "raw_unit": "unit",
                "normalized_value": 70.0,
                "normalized_unit": "COUNT",
            },
            {
                "evidence_id": "ev_direct_den",
                "source_row_id": "ev_direct_den",
                "source_row_ids": ["ev_direct_den"],
                "source_anchor": "direct sibling table",
                "table_source_id": "table_a",
                "label": "base value",
                "matched_operand_label": "base value",
                "matched_operand_role": "denominator_1",
                "raw_value": "30",
                "raw_unit": "unit",
                "normalized_value": 30.0,
                "normalized_unit": "COUNT",
            },
        ]

        rows = self.agent._align_dependency_rows_with_sibling_direct_context(dependency_rows, direct_rows)

        self.assertEqual(rows[0]["raw_value"], "120")
        self.assertEqual(rows[0]["normalized_value"], 120.0)
        self.assertEqual(rows[0]["source_anchor"], "source task table")
        self.assertTrue(rows[0]["sibling_table_context_realignment_blocked"])
        self.assertNotIn("sibling_table_context_realigned", rows[0])

    def test_dependency_alignment_still_realigns_unanchored_row_to_complete_direct_context(self) -> None:
        dependency_rows = [
            {
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "100",
                "raw_unit": "unit",
                "normalized_value": 100.0,
                "normalized_unit": "COUNT",
                "source_row_id": "ev_lookup",
                "source_row_ids": ["ev_lookup"],
            }
        ]
        direct_rows = [
            {
                "evidence_id": "ev_direct_num",
                "source_row_id": "ev_direct_num",
                "source_row_ids": ["ev_direct_num"],
                "table_source_id": "table_a",
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "80",
                "raw_unit": "unit",
                "normalized_value": 80.0,
                "normalized_unit": "COUNT",
            },
            {
                "evidence_id": "ev_direct_den",
                "source_row_id": "ev_direct_den",
                "source_row_ids": ["ev_direct_den"],
                "table_source_id": "table_a",
                "label": "base value",
                "matched_operand_label": "base value",
                "matched_operand_role": "denominator_1",
                "raw_value": "40",
                "raw_unit": "unit",
                "normalized_value": 40.0,
                "normalized_unit": "COUNT",
            },
        ]

        rows = self.agent._align_dependency_rows_with_sibling_direct_context(dependency_rows, direct_rows)

        self.assertEqual(rows[0]["raw_value"], "80")
        self.assertEqual(rows[0]["normalized_value"], 80.0)
        self.assertEqual(rows[0]["source_row_ids"], ["ev_direct_num"])
        self.assertTrue(rows[0]["sibling_table_context_realigned"])

    def test_aggregate_dependency_coherence_infers_source_task_from_matching_slot(self) -> None:
        source_slots = {
            "task_lookup": {
                "status": "ok",
                "label": "target value",
                "concept": "target_metric",
                "raw_value": "120",
                "raw_unit": "unit",
                "normalized_value": 120.0,
                "normalized_unit": "COUNT",
                "source_anchor": "source task table",
            }
        }
        row = {
            "operation_family": "ratio",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "operation_family": "ratio",
                    "components_by_role": {
                        "numerator_1": [
                            {
                                "role": "numerator_1",
                                "label": "target value",
                                "concept": "target_metric",
                                "raw_value": "70",
                                "raw_unit": "unit",
                                "normalized_value": 70.0,
                                "normalized_unit": "COUNT",
                                "source_row_id": "ev_shared",
                                "source_anchor": "direct sibling table",
                            }
                        ]
                    },
                },
            },
        }

        self.assertEqual(
            self.agent._aggregate_result_dependency_coherence_ranks(row, source_slots)[0],
            0,
        )

    def test_compact_ratio_answer_from_projection_rejects_dependency_incoherent_operands(self) -> None:
        self.agent._compact_ratio_answer = lambda _state, _result: "target share is 70%."
        state = {
            "subtask_results": [
                {
                    "task_id": "task_lookup",
                    "calculation_result": {
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "target value",
                                "concept": "target_metric",
                                "raw_value": "120",
                                "raw_unit": "unit",
                                "normalized_value": 120.0,
                                "normalized_unit": "COUNT",
                                "source_anchor": "source task table",
                            }
                        }
                    },
                }
            ]
        }
        result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "ratio",
                "components_by_role": {
                    "numerator_1": [
                        {
                            "role": "numerator_1",
                            "label": "target value",
                            "concept": "target_metric",
                            "raw_value": "70",
                            "raw_unit": "unit",
                            "normalized_value": 70.0,
                            "normalized_unit": "COUNT",
                            "source_anchor": "direct sibling table",
                        }
                    ],
                    "denominator_1": [
                        {
                            "role": "denominator_1",
                            "label": "base value",
                            "concept": "base_metric",
                            "raw_value": "100",
                            "raw_unit": "unit",
                            "normalized_value": 100.0,
                            "normalized_unit": "COUNT",
                            "source_anchor": "direct sibling table",
                        }
                    ],
                },
            },
        }

        self.assertEqual(
            self.agent._compact_ratio_answer_from_projection(
                state,
                {
                    "calculation_operands": [],
                    "calculation_plan": {"operation": "ratio"},
                    "calculation_result": result,
                },
            ),
            "",
        )

    def test_preferred_complete_numeric_answer_skips_dependency_incoherent_ratio_row(self) -> None:
        self.agent._compact_ratio_answer = lambda _state, _result: "target share is 70%."
        ordered_results = [
            self._lookup_result_row(
                task_id="task_lookup",
                label="target value",
                concept="target_metric",
                raw_value="120",
                raw_unit="unit",
                normalized_value=120.0,
                normalized_unit="COUNT",
                source_anchor="source task table",
            ),
            self._ratio_result_row(
                status="ok",
                components_by_role={
                    "numerator_1": [
                        self._ratio_component(
                            role="numerator_1",
                            label="target value",
                            concept="target_metric",
                            raw_value="70",
                            raw_unit="unit",
                            normalized_value=70.0,
                            normalized_unit="COUNT",
                            source_anchor="direct sibling table",
                        )
                    ],
                    "denominator_1": [
                        self._ratio_component(
                            role="denominator_1",
                            label="base value",
                            concept="base_metric",
                            raw_value="100",
                            raw_unit="unit",
                            normalized_value=100.0,
                            normalized_unit="COUNT",
                            source_anchor="direct sibling table",
                        )
                    ],
                },
            ),
        ]

        self.assertEqual(self.agent._preferred_complete_numeric_answer(ordered_results), "")

    def test_preferred_complete_numeric_answer_rebuilds_ratio_from_dependency_source_slots(self) -> None:
        ordered_results = [
            self._lookup_result_row(
                task_id="task_num",
                metric_label="target value",
                label="target value",
                concept="target_metric",
                raw_value="120",
                normalized_value=120000000.0,
                rendered_value="120백만원",
                source_row_id="ev_num",
                source_anchor="source task table",
                answer="target value is 120백만원.",
            ),
            self._ratio_result_row(
                status="insufficient_operands",
                answer="not enough operands",
                components_by_group={
                    "operand": [
                        self._ratio_component(
                            role="operand",
                            label="target value",
                            concept="target_metric",
                            raw_value="70",
                            normalized_value=70000000.0,
                            source_row_id="ev_direct",
                            source_anchor="direct sibling table",
                        )
                    ]
                },
            ),
            self._lookup_result_row(
                task_id="task_den",
                metric_label="base value",
                label="stale sibling value",
                concept="base_metric",
                raw_value="70",
                normalized_value=70000000.0,
                rendered_value="70백만원",
                source_row_id="ev_stale",
                source_anchor="direct sibling table",
                answer="base value is 150백만원.",
            ),
        ]

        answer = self.agent._preferred_complete_numeric_answer(ordered_results)

        self.assertIn("80%", answer)
        self.assertIn("target value", answer)
        self.assertIn("base value", answer)
        self.assertNotIn("70", answer)

    def test_preferred_complete_numeric_answer_uses_lookup_metric_label_for_denominator_source(self) -> None:
        ordered_results = [
            self._lookup_result_row(
                task_id="task_num",
                metric_label="target value",
                label="target value",
                concept="metric",
                raw_value="120",
                normalized_value=120000000.0,
                rendered_value="120백만원",
                source_row_id="ev_num",
                answer="target value is 120백만원.",
            ),
            self._lookup_result_row(
                task_id="task_part",
                metric_label="sibling value",
                label="sibling value",
                concept="metric",
                raw_value="30",
                normalized_value=30000000.0,
                rendered_value="30백만원",
                source_row_id="ev_part",
                answer="sibling value is 30백만원.",
            ),
            self._ratio_result_row(
                status="insufficient_operands",
                components_by_group={
                    "operand": [
                        self._ratio_component(
                            role="operand",
                            label="target value",
                            concept="metric",
                            raw_value="70",
                            normalized_value=70000000.0,
                            source_row_id="ev_direct",
                        )
                    ]
                },
            ),
            self._lookup_result_row(
                task_id="task_den",
                metric_label="base value",
                label="value",
                concept="metric",
                raw_value="150",
                normalized_value=150000000.0,
                rendered_value="150백만원",
                source_row_id="ev_den",
                answer="base value is 150백만원.",
            ),
        ]

        answer = self.agent._preferred_complete_numeric_answer(ordered_results)

        self.assertIn("80%", answer)
        self.assertIn("base value", answer)
        self.assertNotIn("400%", answer)

    def test_precision_refinement_prefers_more_specific_contextual_row_label(self) -> None:
        row = {
            "label": "2023년 목표조정(환입) 등",
            "matched_operand_label": "목표조정(환입) 등",
            "matched_operand_role": "numerator_1",
            "raw_value": "62,964",
            "raw_unit": "백만원",
            "normalized_value": 62964000000.0,
            "normalized_unit": "KRW",
        }
        evidence_item = {
            "evidence_id": "ev_table",
            "source_anchor": "[ExampleCo | 2023 | note]",
            "metadata": {
                "year": 2023,
                "unit_hint": "백만원",
                "table_row_labels_text": "부분조정(환입)\n목표조정(환입) 등",
                "table_row_records_json": json.dumps(
                    [
                        {
                            "row_label": "부분조정(환입)",
                            "cells": [{"value_text": "62,964", "unit_hint": "백만원"}],
                        },
                        {
                            "row_label": "목표조정(환입) 등",
                            "cells": [{"value_text": "5,037,579", "unit_hint": "백만원"}],
                        },
                    ],
                    ensure_ascii=False,
                ),
            },
        }

        refined = self.agent._refine_operand_precision_from_evidence_table(row, evidence_item)

        self.assertEqual(refined["raw_value"], "5,037,579")
        self.assertEqual(refined["raw_unit"], "백만원")
        self.assertEqual(refined["normalized_value"], 5037579000000.0)
        self.assertEqual(refined["precision_source"], "contextual_note_structured_table_cell")

    def test_dependency_row_realigns_unit_from_structured_graph_provenance(self) -> None:
        self.agent.vsm = type(
            "VectorStoreStub",
            (),
            {
                "_structure_graph": {
                    "nodes": {
                        "node_1": {
                            "text": "target value 100",
                            "metadata": {
                                "company": "ExampleCo",
                                "year": 2023,
                                "report_type": "annual report",
                                "rcept_no": "r1",
                                "section_path": "Financial statements",
                                "table_value_labels_text": "target value 100",
                                "unit_hint": "백만원",
                                "statement_type": "income_statement",
                                "consolidation_scope": "consolidated",
                                "table_source_id": "table_income",
                            },
                        }
                    }
                }
            },
        )()
        state = {
            "report_scope": {"year": 2023, "rcept_no": "r1"},
            "query": "target value ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "operation_family": "ratio",
                "inputs": [
                    {
                        "role": "denominator_1",
                        "concept": "target_metric",
                        "label": "target value",
                        "preferred_task_id": "task_lookup",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output"],
                    }
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_lookup",
                    "metric_label": "target value",
                    "operation_family": "lookup",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "target value",
                                "concept": "target_metric",
                                "raw_value": "100",
                                "raw_unit": "천원",
                                "normalized_value": 100000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "100천원",
                                "source_row_id": "ev_lookup",
                                "source_row_ids": ["ev_lookup"],
                            }
                        },
                    },
                }
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_lookup",
                    "claim": "target value 100 (천원)",
                    "quote_span": "100",
                }
            ],
        }

        rows = self.agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["raw_value"], "100")
        self.assertEqual(rows[0]["raw_unit"], "백만원")
        self.assertEqual(rows[0]["normalized_value"], 100000000.0)
        self.assertTrue(rows[0]["unit_realigned_from_structured_provenance"])
        self.assertIn("node_1", rows[0]["source_row_ids"])

    def test_dependency_row_preserves_source_visible_converted_unit_over_graph_hint(self) -> None:
        self.agent.vector_store = type(
            "Store",
            (),
            {
                "_structure_graph": {
                    "nodes": {
                        "node_1": {
                            "text": "target value 100",
                            "metadata": {
                                "company": "ExampleCo",
                                "year": 2023,
                                "report_type": "annual report",
                                "rcept_no": "r1",
                                "section_path": "Financial statements",
                                "table_value_labels_text": "target value 100",
                                "unit_hint": "백만원",
                                "statement_type": "income_statement",
                                "consolidation_scope": "consolidated",
                                "table_source_id": "table_income",
                            },
                        }
                    }
                }
            },
        )()
        state = {
            "report_scope": {"year": 2023, "rcept_no": "r1"},
            "query": "target value ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "operation_family": "ratio",
                "inputs": [
                    {
                        "role": "denominator_1",
                        "concept": "target_metric",
                        "label": "target value",
                        "preferred_task_id": "task_lookup",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output"],
                    }
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_lookup",
                    "metric_label": "target value",
                    "operation_family": "lookup",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "target value",
                                "concept": "target_metric",
                                "raw_value": "100",
                                "raw_unit": "원",
                                "normalized_value": 100.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "100원",
                                "source_row_id": "ev_lookup",
                                "source_row_ids": ["ev_lookup"],
                            }
                        },
                    },
                }
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_lookup",
                    "claim": "target value 100원",
                    "quote_span": "100원",
                }
            ],
        }

        rows = self.agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["raw_value"], "100")
        self.assertEqual(rows[0]["raw_unit"], "원")
        self.assertEqual(rows[0]["normalized_value"], 100.0)
        self.assertFalse(rows[0].get("unit_realigned_from_structured_provenance", False))

    def test_dependency_row_preserves_high_magnitude_converted_unit_without_rendered_display(self) -> None:
        self.agent.vector_store = type(
            "Store",
            (),
            {
                "_structure_graph": {
                    "nodes": {
                        "node_1": {
                            "text": "target value 651481422157",
                            "metadata": {
                                "company": "ExampleCo",
                                "year": 2023,
                                "report_type": "annual report",
                                "rcept_no": "r1",
                                "section_path": "Financial statements",
                                "table_value_labels_text": "target value 651481422157",
                                "unit_hint": "천원",
                                "statement_type": "income_statement",
                                "consolidation_scope": "consolidated",
                                "table_source_id": "table_income",
                            },
                        }
                    }
                }
            },
        )()
        state = {
            "report_scope": {"year": 2023, "rcept_no": "r1"},
            "query": "target value ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "operation_family": "ratio",
                "inputs": [
                    {
                        "role": "numerator",
                        "concept": "target_metric",
                        "label": "target value",
                        "preferred_task_id": "task_lookup",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output"],
                    }
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_lookup",
                    "metric_label": "target value",
                    "operation_family": "lookup",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "target value",
                                "concept": "target_metric",
                                "raw_value": "651,481,422,157",
                                "raw_unit": "원",
                                "normalized_value": 651481422157.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "",
                                "source_row_id": "ev_lookup",
                                "source_row_ids": ["ev_lookup"],
                            }
                        },
                    },
                }
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_lookup",
                    "claim": "target value 651,481,422,157",
                    "quote_span": "651,481,422,157",
                }
            ],
        }

        rows = self.agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["raw_unit"], "원")
        self.assertEqual(rows[0]["normalized_value"], 651481422157.0)
        self.assertFalse(rows[0].get("unit_realigned_from_structured_provenance", False))

    def test_lookup_recovery_prefers_table_unit_hint_when_source_surface_has_no_unit(self) -> None:
        state = {
            "calc_subtasks": [
                {
                    "task_id": "task_lookup",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "segment revenue",
                            "concept": "revenue",
                            "role": "primary_value",
                            "required": True,
                        }
                    ],
                }
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_direct",
                    "quote_span": "2,546,649",
                    "metadata": {"unit_hint": "백만원"},
                }
            ],
        }
        preferred_slot = {
            "status": "ok",
            "label": "segment revenue",
            "concept": "revenue",
            "period": "2023",
            "raw_value": "2,546,649",
            "raw_unit": "천원",
            "normalized_value": 2546649000.0,
            "normalized_unit": "KRW",
            "rendered_value": "2,546,649천원",
            "source_row_id": "ev_direct",
            "source_row_ids": ["ev_direct"],
        }
        current_row = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {"primary_value": {**preferred_slot, "source_row_id": "ev_weak"}},
            },
        }
        self.agent._best_direct_lookup_slot_from_evidence_pool = lambda _operand, _pool: (preferred_slot, 10.0)
        self.agent._direct_structured_lookup_evidence_score = lambda _operand, _evidence: 0.0

        recovered = self.agent._recover_lookup_results_from_sibling_table_evidence([current_row], state)
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertEqual(slot["raw_unit"], "백만원")
        self.assertEqual(slot["normalized_value"], 2546649000000.0)
        self.assertEqual(slot["rendered_value"], "2,546,649백만원")

    def test_lookup_recovery_preserves_claim_visible_unit_over_table_unit_hint(self) -> None:
        state = {
            "calc_subtasks": [
                {
                    "task_id": "task_lookup",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "segment revenue",
                            "concept": "revenue",
                            "role": "primary_value",
                            "required": True,
                        }
                    ],
                }
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_direct",
                    "claim": "segment revenue 2,546,649 (원)",
                    "quote_span": "2,546,649",
                    "metadata": {"unit_hint": "천원"},
                }
            ],
        }
        preferred_slot = {
            "status": "ok",
            "label": "segment revenue",
            "concept": "revenue",
            "period": "2023",
            "raw_value": "2,546,649",
            "raw_unit": "원",
            "normalized_value": 2546649.0,
            "normalized_unit": "KRW",
            "rendered_value": "2,546,649원",
            "source_row_id": "ev_direct",
            "source_row_ids": ["ev_direct"],
        }
        current_row = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {"primary_value": {**preferred_slot, "source_row_id": "ev_weak"}},
            },
        }
        self.agent._best_direct_lookup_slot_from_evidence_pool = lambda _operand, _pool: (preferred_slot, 10.0)
        self.agent._direct_structured_lookup_evidence_score = lambda _operand, _evidence: 0.0

        recovered = self.agent._recover_lookup_results_from_sibling_table_evidence([current_row], state)
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertEqual(slot["raw_unit"], "원")
        self.assertEqual(slot["normalized_value"], 2546649.0)
        self.assertEqual(slot["rendered_value"], "2,546,649원")

    def test_lookup_recovery_rejects_preferred_slot_without_operand_surface(self) -> None:
        state = {
            "calc_subtasks": [
                {
                    "task_id": "task_lookup",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "property plant equipment",
                            "concept": "property_plant_equipment",
                            "role": "primary_value",
                            "required": True,
                        }
                    ],
                }
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_asset",
                    "claim": "property plant equipment 52,704,853 million",
                    "raw_row_text": "property plant equipment | 52,704,853 million",
                    "metadata": {
                        "row_label": "property plant equipment",
                        "semantic_label": "property plant equipment",
                        "unit_hint": "million",
                    },
                },
                {
                    "evidence_id": "ev_other_aggregate",
                    "claim": "borrowing total 10,121,033 million",
                    "raw_row_text": "borrowing total | 10,121,033 million",
                    "metadata": {
                        "row_label": "borrowing total",
                        "semantic_label": "borrowing total",
                        "aggregate_label": "borrowing total",
                        "value_role": "aggregate",
                        "aggregation_stage": "final",
                        "unit_hint": "million",
                    },
                },
            ],
        }
        current_slot = {
            "status": "ok",
            "label": "property plant equipment",
            "concept": "property_plant_equipment",
            "period": "2023",
            "raw_value": "52,704,853",
            "raw_unit": "million",
            "normalized_value": 52704853000000.0,
            "normalized_unit": "KRW",
            "rendered_value": "52,704,853million",
            "source_row_id": "ev_asset",
            "source_row_ids": ["ev_asset"],
        }
        preferred_slot = {
            **current_slot,
            "raw_value": "10,121,033",
            "normalized_value": 10121033000000.0,
            "rendered_value": "10,121,033million",
            "source_row_id": "ev_other_aggregate",
            "source_row_ids": ["ev_other_aggregate"],
        }
        current_row = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {"primary_value": current_slot},
            },
        }
        self.agent._best_direct_lookup_slot_from_evidence_pool = lambda _operand, _pool: (preferred_slot, 10.0)

        recovered = self.agent._recover_lookup_results_from_sibling_table_evidence([current_row], state)
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertEqual(slot["source_row_id"], "ev_asset")
        self.assertEqual(slot["raw_value"], "52,704,853")

    def test_lookup_recovery_preserves_value_when_preferred_slot_is_different_column(self) -> None:
        state = {
            "calc_subtasks": [
                {
                    "task_id": "task_lookup",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "capitalized development cost",
                            "concept": "capitalized_development_cost",
                            "role": "primary_value",
                            "required": True,
                        }
                    ],
                }
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_cost_row",
                    "claim": "capitalized development cost | current 100 | prior 200",
                    "quote_span": "capitalized development cost | current 100 | prior 200",
                    "raw_row_text": "capitalized development cost | current 100 | prior 200",
                    "metadata": {
                        "row_label": "capitalized development cost",
                        "semantic_label": "capitalized development cost",
                        "table_value_labels_text": "capitalized development cost 100\ncapitalized development cost 200",
                        "column_headers_chain": ["current"],
                        "structured_cells": [
                            {
                                "column_headers": ["current"],
                                "value_text": "100",
                                "unit_hint": "KRW",
                            },
                            {
                                "column_headers": ["prior"],
                                "value_text": "200",
                                "unit_hint": "KRW",
                            },
                        ],
                    },
                }
            ],
        }
        current_slot = {
            "status": "ok",
            "label": "capitalized development cost",
            "concept": "capitalized_development_cost",
            "period": "current",
            "raw_value": "100",
            "raw_unit": "KRW",
            "normalized_value": 100.0,
            "normalized_unit": "KRW",
            "rendered_value": "100KRW",
            "source_row_id": "ev_cost_row",
            "source_row_ids": ["ev_cost_row"],
        }
        preferred_slot = {
            **current_slot,
            "raw_value": "200",
            "normalized_value": 200.0,
            "rendered_value": "200KRW",
        }
        current_row = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {"primary_value": current_slot},
            },
        }
        self.agent._best_direct_lookup_slot_from_evidence_pool = lambda _operand, _pool: (preferred_slot, 10.0)
        self.agent._direct_structured_lookup_evidence_score = lambda _operand, _evidence: 0.0

        recovered = self.agent._recover_lookup_results_from_sibling_table_evidence([current_row], state)
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertEqual(slot["raw_value"], "100")
        self.assertEqual(slot["normalized_value"], 100.0)

    def test_dependency_output_rejects_retrieval_replacement_without_operand_surface(self) -> None:
        current_slot = {
            "status": "ok",
            "label": "property plant equipment",
            "concept": "property_plant_equipment",
            "period": "2023",
            "raw_value": "52,704,853",
            "raw_unit": "million",
            "normalized_value": 52704853000000.0,
            "normalized_unit": "KRW",
            "rendered_value": "52,704,853million",
            "source_row_id": "ev_asset",
            "source_row_ids": ["ev_asset"],
        }
        preferred_slot = {
            "status": "ok",
            "label": "borrowing total",
            "period": "2023",
            "raw_value": "10,121,033",
            "raw_unit": "million",
            "normalized_value": 10121033000000.0,
            "normalized_unit": "KRW",
            "rendered_value": "10,121,033million",
            "source_row_id": "ev_other_aggregate",
            "source_row_ids": ["ev_other_aggregate"],
        }
        state = {
            "active_subtask": {
                "task_id": "task_ratio",
                "operation_family": "ratio",
                "inputs": [
                    {
                        "label": "property plant equipment",
                        "concept": "property_plant_equipment",
                        "role": "denominator_1",
                        "required": True,
                        "preferred_task_id": "task_asset",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "label": "borrowing total",
                        "concept": "total_borrowings",
                        "role": "numerator",
                        "required": True,
                        "preferred_task_id": "task_borrowings",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_asset",
                    "metric_family": "concept_lookup",
                    "metric_label": "property plant equipment",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {"primary_value": current_slot},
                    },
                    "runtime_evidence": [
                        {
                            "evidence_id": "ev_asset",
                            "claim": "property plant equipment 52,704,853 million",
                            "raw_row_text": "property plant equipment | 52,704,853 million",
                            "metadata": {
                                "row_label": "property plant equipment",
                                "semantic_label": "property plant equipment",
                                "unit_hint": "million",
                            },
                        }
                    ],
                }
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_other_aggregate",
                    "claim": "borrowing total 10,121,033 million",
                    "raw_row_text": "borrowing total | 10,121,033 million",
                    "metadata": {
                        "row_label": "borrowing total",
                        "semantic_label": "borrowing total",
                        "aggregate_label": "borrowing total",
                        "unit_hint": "million",
                    },
                }
            ],
        }
        self.agent._best_direct_lookup_slot_from_evidence_pool_compat = lambda _operand, _pool, state=None: (
            preferred_slot,
            10.0,
        )
        self.agent._lookup_value_from_table_label_metadata = lambda _operand, _evidence: {}
        self.agent._direct_structured_lookup_evidence_score = lambda _operand, _evidence: 0.0
        self.agent._structured_graph_provenance_for_dependency_operand = lambda *_args, **_kwargs: {}

        rows = self.agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["matched_operand_role"], "denominator_1")
        self.assertEqual(rows[0]["source_row_id"], "task_output:task_asset")
        self.assertEqual(rows[0]["raw_value"], "52,704,853")

    def test_lookup_recovery_aligns_current_slot_unit_without_preferred_replacement(self) -> None:
        state = {
            "calc_subtasks": [
                {
                    "task_id": "task_lookup",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "segment revenue",
                            "concept": "revenue",
                            "role": "primary_value",
                            "required": True,
                        }
                    ],
                }
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_direct",
                    "quote_span": "2,546,649",
                    "metadata": {"unit_hint": "백만원"},
                }
            ],
        }
        current_slot = {
            "status": "ok",
            "label": "segment revenue",
            "concept": "revenue",
            "period": "2023",
            "raw_value": "2,546,649",
            "raw_unit": "천원",
            "normalized_value": 2546649000.0,
            "normalized_unit": "KRW",
            "rendered_value": "2,546,649천원",
            "source_row_id": "ev_direct",
            "source_row_ids": ["ev_direct"],
        }
        current_row = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {"primary_value": current_slot},
            },
        }
        self.agent._best_direct_lookup_slot_from_evidence_pool = lambda _operand, _pool: ({}, 0.0)
        self.agent._direct_structured_lookup_evidence_score = lambda _operand, _evidence: 10.0

        recovered = self.agent._recover_lookup_results_from_sibling_table_evidence([current_row], state)
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertTrue(recovered[0].get("unit_aligned_from_evidence_metadata"))
        self.assertEqual(slot["raw_unit"], "백만원")
        self.assertEqual(slot["normalized_value"], 2546649000000.0)

    def test_lookup_recovery_uses_nested_subtask_runtime_evidence(self) -> None:
        state = {
            "calc_subtasks": [
                {
                    "task_id": "task_lookup",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "segment operating income",
                            "concept": "operating_income",
                            "role": "primary_value",
                            "required": True,
                        }
                    ],
                }
            ],
        }
        current_slot = {
            "status": "ok",
            "label": "segment operating income",
            "concept": "operating_income",
            "period": "2023",
            "raw_value": "1,385,538",
            "raw_unit": "천원",
            "normalized_value": 1385538000.0,
            "normalized_unit": "KRW",
            "rendered_value": "1,385,538천원",
            "source_row_id": "ev_weak",
            "source_row_ids": ["ev_weak"],
        }
        current_row = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {"primary_value": current_slot},
            },
        }
        nested_evidence_row = {
            "task_id": "task_nested",
            "runtime_evidence": [
                {
                    "evidence_id": "ev_direct",
                    "claim": "segment operating income 1,385,538백만원",
                    "quote_span": "segment operating income | 1,385,538",
                    "metadata": {
                        "year": 2023,
                        "unit_hint": "백만원",
                        "table_source_id": "table_income",
                        "table_value_labels_text": "\n".join(
                            [
                                "operating income 1,385,538",
                                "other line 100",
                            ]
                        ),
                    },
                }
            ],
        }
        sibling_row = {
            "task_id": "task_aggregate",
            "operation_family": "aggregate_subtasks",
            "calculation_result": {"subtask_results": [nested_evidence_row]},
        }

        recovered = self.agent._recover_lookup_results_from_sibling_table_evidence(
            [current_row, sibling_row],
            state,
        )
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertTrue(recovered[0].get("recovered_from_sibling_table_evidence"))
        self.assertEqual(slot["raw_value"], "1,385,538")
        self.assertEqual(slot["raw_unit"], "백만원")
        self.assertEqual(slot["source_row_id"], "ev_direct")

    def test_table_label_lookup_uses_partial_row_label_and_requested_period(self) -> None:
        evidence = {
            "evidence_id": "ev_segment_table",
            "source_anchor": "COMPANY | 2023 | management discussion",
            "metadata": {
                "year": 2023,
                "unit_hint": "million",
                "table_source_id": "mda::table:1",
                "table_value_labels_text": "\n".join(
                    [
                        "total revenue 9,670.6",
                        "total revenue 8,220.1",
                        "commerce 2,546.6",
                        "commerce 1,801.1",
                    ]
                ),
            },
        }

        current_slot = self.agent._lookup_value_from_table_label_metadata(
            {
                "label": "2023 commerce revenue",
                "concept": "revenue",
                "role": "current_period",
            },
            evidence,
        )
        prior_slot = self.agent._lookup_value_from_table_label_metadata(
            {
                "label": "2022 commerce revenue",
                "concept": "revenue",
                "role": "prior_period",
            },
            evidence,
        )

        self.assertEqual(current_slot["raw_value"], "2,546.6")
        self.assertEqual(current_slot["period"], "2023")
        self.assertEqual(prior_slot["raw_value"], "1,801.1")
        self.assertEqual(prior_slot["period"], "2022")

    def test_lookup_recovery_uses_current_slot_when_required_operands_missing(self) -> None:
        state = {
            "calc_subtasks": [
                {
                    "task_id": "task_lookup",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                }
            ],
            "runtime_evidence": [
                {
                    "evidence_id": "ev_segment_table",
                    "source_anchor": "COMPANY | 2023 | management discussion",
                    "metadata": {
                        "year": 2023,
                        "unit_hint": "million",
                        "table_source_id": "mda::table:1",
                        "table_value_labels_text": "\n".join(
                            [
                                "total revenue 9,670.6",
                                "total revenue 8,220.1",
                                "commerce 2,546.6",
                                "commerce 1,801.1",
                            ]
                        ),
                    },
                }
            ],
        }
        current_row = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "primary_value": {
                        "status": "ok",
                        "label": "2023 commerce revenue",
                        "concept": "revenue",
                        "period": "2023",
                        "raw_value": "3,589.1",
                        "raw_unit": "million",
                        "normalized_value": 3589100000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "3,589.1 million",
                        "source_row_id": "ev_weak",
                    }
                },
            },
        }

        recovered = self.agent._recover_lookup_results_from_sibling_table_evidence([current_row], state)
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertTrue(recovered[0].get("recovered_from_sibling_table_evidence"))
        self.assertEqual(slot["raw_value"], "2,546.6")
        self.assertEqual(slot["source_row_id"], "ev_segment_table")

    def test_lookup_recovery_rejects_context_dependent_table_when_scope_not_requested(self) -> None:
        state = {
            "query": "Calculate 2023 consolidated interest coverage ratio.",
            "calc_subtasks": [
                {
                    "task_id": "task_lookup",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "sibling_lookup_surfaces": ["interest expense"],
                    "required_operands": [
                        {
                            "label": "interest expense",
                            "concept": "interest_expense",
                            "role": "primary_value",
                            "required": True,
                        }
                    ],
                }
            ],
            "runtime_evidence": [
                {
                    "evidence_id": "ev_context_table",
                    "source_anchor": "COMPANY | 2023 | Notes",
                    "claim": "interest expense | segment / steel (718,937) million | segment / total (1,180,096) million",
                    "quote_span": "interest expense | segment / steel (718,937) million | segment / total (1,180,096) million",
                    "raw_row_text": "interest expense | segment / steel (718,937) million | segment / total (1,180,096) million",
                    "metadata": {
                        "year": 2023,
                        "unit_hint": "million",
                        "table_view": "column_row_window",
                        "table_value_labels_text": "interest expense (718,937)\ninterest expense (1,180,096)",
                        "structured_cells": [
                            {"column_headers": ["segment", "steel"], "value_text": "(718,937)", "unit_hint": "million"},
                            {"column_headers": ["segment", "trading"], "value_text": "(284,056)", "unit_hint": "million"},
                            {"column_headers": ["segment", "construction"], "value_text": "(105,102)", "unit_hint": "million"},
                            {"column_headers": ["segment", "total"], "value_text": "(1,180,096)", "unit_hint": "million"},
                        ],
                    },
                }
            ],
        }
        current_row = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "operation_family": "lookup",
            "status": "missing",
            "answer": "interest expense is missing.",
            "calculation_result": {"status": "missing", "answer_slots": {}},
        }

        recovered = self.agent._recover_lookup_results_from_sibling_table_evidence([current_row], state)

        self.assertEqual(recovered[0], current_row)
        self.assertFalse(recovered[0].get("recovered_from_sibling_table_evidence"))

    def test_aggregate_subtasks_recalculates_growth_from_dependency_lookup_slots_without_child_operands(self) -> None:
        self.agent.llm = None
        state = {
            "query": "Calculate the 2023 segment revenue growth rate and summarize the acquisition impact.",
            "calc_subtasks": [
                {"task_id": "task_3", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_4", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_1", "metric_family": "concept_growth_rate", "operation_family": "growth_rate"},
                {"task_id": "task_2", "metric_family": "narrative_summary", "operation_family": "narrative_summary"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 segment revenue",
                    "operation_family": "lookup",
                    "answer": "2,546,649 million",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "2,546,649 million",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "concept": "revenue",
                                "period": "2023",
                                "raw_value": "2,546,649",
                                "raw_unit": "million",
                                "normalized_value": 2546649000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "2,546,649 million",
                                "source_row_id": "ev_current",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_4",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022 segment revenue",
                    "operation_family": "lookup",
                    "answer": "1,801,079 million",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "1,801,079 million",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "concept": "revenue",
                                "period": "2022",
                                "raw_value": "1,801,079",
                                "raw_unit": "million",
                                "normalized_value": 1801079000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "1,801,079 million",
                                "source_row_id": "ev_prior",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "segment revenue growth rate",
                    "operation_family": "growth_rate",
                    "answer": "2023 segment revenue was 3,589,061 thousand, up 40.93% from 2,546,649 thousand.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "40.93%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "segment revenue growth rate",
                                "period": "2023",
                                "normalized_value": 40.93,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "40.93%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "concept": "revenue",
                                "period": "2023",
                                "raw_value": "3,589,061",
                                "raw_unit": "thousand",
                                "normalized_value": 3589061000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "3,589,061 thousand",
                                "source_row_id": "task_output:task_3",
                                "source_row_ids": ["task_output:task_3", "ev_current"],
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "concept": "revenue",
                                "period": "2023",
                                "raw_value": "2,546,649",
                                "raw_unit": "thousand",
                                "normalized_value": 2546649000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "2,546,649 thousand",
                                "source_row_id": "task_output:task_4",
                                "source_row_ids": ["task_output:task_4", "ev_prior"],
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "acquisition impact",
                    "operation_family": "narrative_summary",
                    "answer": "The acquisition integration improved segment revenue growth.",
                    "status": "ok",
                    "selected_claim_ids": ["ev_driver"],
                    "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                },
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_driver",
                    "claim": "The acquisition integration improved segment revenue growth.",
                    "quote_span": "acquisition integration improved segment revenue growth",
                    "support_level": "direct",
                    "metadata": {"section_path": "Management discussion"},
                }
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("41.4%", updated["answer"])
        self.assertIn("2,546,649 million", updated["answer"])
        self.assertIn("1,801,079 million", updated["answer"])
        self.assertNotIn("3,589,061", updated["answer"])
        growth_row = next(row for row in updated["subtask_results"] if row["task_id"] == "task_1")
        self.assertTrue(growth_row.get("aligned_from_source_task_slots"))
        self.assertEqual(growth_row["calculation_result"]["rendered_value"], "41.4%")
        growth_slots = growth_row["calculation_result"]["answer_slots"]
        self.assertEqual(growth_slots["current_value"]["raw_value"], "2,546,649")
        self.assertEqual(growth_slots["prior_value"]["raw_value"], "1,801,079")
        self.assertEqual(growth_slots["prior_value"]["period"], "2022")

    def test_late_nested_lookup_promotion_recalculates_growth_before_final_projection(self) -> None:
        self.agent.llm = None
        self.agent._append_retrieved_narrative_evidence_for_final_answer = (
            lambda evidence_items, **_kwargs: (list(evidence_items or []), ["ev_driver"])
        )
        self.agent._preserve_retrieved_narrative_source_surface = (
            lambda _answer, _evidence_items: (
                "2023 segment revenue was 2,546,649 million, "
                "up 41.4% from 1,801,079 million."
            )
        )
        correct_prior_row = {
            "task_id": "task_4",
            "metric_family": "concept_lookup",
            "metric_label": "2022 segment revenue",
            "operation_family": "lookup",
            "answer": "1,801,079 million",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "1,801,079 million",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "concept": "revenue",
                        "period": "2022",
                        "raw_value": "1,801,079",
                        "raw_unit": "million",
                        "normalized_value": 1801079000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "1,801,079 million",
                        "source_row_id": "ev_prior",
                    },
                },
            },
        }
        state = {
            "query": "Calculate the 2023 segment revenue growth rate and summarize the acquisition impact.",
            "calc_subtasks": [
                {"task_id": "task_3", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_4", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_1", "metric_family": "concept_growth_rate", "operation_family": "growth_rate"},
                {"task_id": "task_2", "metric_family": "narrative_summary", "operation_family": "aggregate_subtasks"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 segment revenue",
                    "operation_family": "lookup",
                    "answer": "2,546,649 million",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "2,546,649 million",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "concept": "revenue",
                                "period": "2023",
                                "raw_value": "2,546,649",
                                "raw_unit": "million",
                                "normalized_value": 2546649000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "2,546,649 million",
                                "source_row_id": "ev_current",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_4",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022 segment revenue",
                    "operation_family": "lookup",
                    "answer": "303 million",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "303 million",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "concept": "revenue",
                                "period": "2022",
                                "raw_value": "303",
                                "raw_unit": "million",
                                "normalized_value": 303000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "303 million",
                                "source_row_id": "ev_weak_prior",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "segment revenue growth rate",
                    "operation_family": "growth_rate",
                    "answer": "segment revenue increased 840478.88%",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "840478.88%",
                        "formatted_result": "840478.88%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "segment revenue growth rate",
                                "period": "2023",
                                "normalized_value": 840478.88,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "840478.88%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "concept": "revenue",
                                "period": "2023",
                                "raw_value": "2,546,649",
                                "raw_unit": "million",
                                "normalized_value": 2546649000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "2,546,649 million",
                                "source_row_id": "task_output:task_3",
                                "source_row_ids": ["task_output:task_3", "ev_current"],
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "segment revenue",
                                "concept": "revenue",
                                "period": "2022",
                                "raw_value": "303",
                                "raw_unit": "million",
                                "normalized_value": 303000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "303 million",
                                "source_row_id": "task_output:task_4",
                                "source_row_ids": ["task_output:task_4", "ev_weak_prior"],
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "growth narrative",
                    "operation_family": "aggregate_subtasks",
                    "answer": (
                        "2023 segment revenue was 2,546,649 million, "
                        "up 41.4% from 1,801,079 million. "
                        "인수 통합 영향으로 segment revenue growth가 개선되었습니다."
                    ),
                    "status": "ok",
                    "selected_claim_ids": ["ev_driver"],
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": (
                            "2023 segment revenue was 2,546,649 million, "
                            "up 41.4% from 1,801,079 million. "
                            "인수 통합 영향으로 segment revenue growth가 개선되었습니다."
                        ),
                        "answer_slots": {"operation_family": "aggregate_subtasks"},
                        "subtask_results": [correct_prior_row],
                    },
                },
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_driver",
                    "claim": "인수 통합 영향으로 segment revenue growth가 개선되었습니다.",
                    "quote_span": "인수 통합 영향으로 segment revenue growth가 개선되었습니다",
                    "support_level": "direct",
                }
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("41.4%", updated["answer"])
        self.assertIn("1,801,079 million", updated["answer"])
        self.assertIn("인수 통합 영향", updated["answer"])
        self.assertNotIn("303 million", updated["answer"])
        self.assertNotIn("840478.88%", updated["answer"])
        prior_row = next(row for row in updated["subtask_results"] if row["task_id"] == "task_4")
        self.assertTrue(prior_row.get("promoted_from_nested_aggregate"))
        growth_row = next(row for row in updated["subtask_results"] if row["task_id"] == "task_1")
        self.assertTrue(growth_row.get("aligned_from_source_task_slots"))
        self.assertEqual(growth_row["calculation_result"]["rendered_value"], "41.4%")
        self.assertEqual(
            growth_row["calculation_result"]["answer_slots"]["prior_value"]["raw_value"],
            "1,801,079",
        )
        structured_rows = updated["structured_result"]["subtask_results"]
        structured_growth_row = next(row for row in structured_rows if row["task_id"] == "task_1")
        structured_prior_row = next(row for row in structured_rows if row["task_id"] == "task_4")
        self.assertEqual(structured_growth_row["calculation_result"]["rendered_value"], "41.4%")
        self.assertEqual(
            structured_growth_row["calculation_result"]["answer_slots"]["prior_value"]["raw_value"],
            "1,801,079",
        )
        self.assertEqual(
            structured_prior_row["calculation_result"]["answer_slots"]["primary_value"]["raw_value"],
            "1,801,079",
        )

    def test_projection_subtask_consistency_uses_full_nested_projection_rows(self) -> None:
        def _lookup_row(task_id, period, raw_value, source_id):
            return {
                "task_id": task_id,
                "metric_family": "concept_lookup",
                "metric_label": f"{period} segment revenue",
                "operation_family": "lookup",
                "answer": f"{raw_value} million",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": f"{raw_value} million",
                    "formatted_result": f"{raw_value} million",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "concept": "revenue",
                            "period": period,
                            "raw_value": raw_value,
                            "raw_unit": "million",
                            "normalized_value": float(raw_value.replace(",", "")) * 1000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": f"{raw_value} million",
                            "source_row_id": source_id,
                        },
                    },
                    "source_row_ids": [source_id],
                },
            }

        current_row = _lookup_row("task_current", "2023", "2,546,649", "ev_current")
        stale_prior_row = _lookup_row("task_prior", "2022", "303", "ev_weak_prior")
        correct_prior_row = _lookup_row("task_prior", "2022", "1,801,079", "ev_prior")
        stale_growth_row = {
            "task_id": "task_growth",
            "metric_family": "concept_growth_rate",
            "metric_label": "segment revenue growth rate",
            "operation_family": "growth_rate",
            "answer": "840478.88%",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "840478.88%",
                "formatted_result": "840478.88%",
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {
                        "status": "ok",
                        "label": "segment revenue growth rate",
                        "normalized_value": 840478.88,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "840478.88%",
                    },
                    "current_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "concept": "revenue",
                        "period": "2023",
                        "raw_value": "2,546,649",
                        "raw_unit": "million",
                        "normalized_value": 2546649000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "2,546,649 million",
                        "source_row_id": "task_output:task_current",
                    },
                    "prior_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "concept": "revenue",
                        "period": "2022",
                        "raw_value": "303",
                        "raw_unit": "million",
                        "normalized_value": 303000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "303 million",
                        "source_row_id": "task_output:task_prior",
                    },
                },
            },
        }
        summary_row = {
            "task_id": "task_summary",
            "metric_family": "narrative_summary",
            "metric_label": "growth narrative",
            "operation_family": "aggregate_subtasks",
            "answer": "Segment revenue increased 41.4%.",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "Segment revenue increased 41.4%.",
                "answer_slots": {"operation_family": "aggregate_subtasks"},
                "subtask_results": [stale_prior_row, stale_growth_row, correct_prior_row],
            },
        }
        compact_summary_row = {
            **summary_row,
            "calculation_result": {
                "status": "ok",
                "answer_slots": {"operation_family": "aggregate_subtasks"},
            },
        }
        state = {
            "query": "Calculate segment revenue growth and summarize the change.",
            "calc_subtasks": [
                {"task_id": "task_current", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_prior", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_growth", "metric_family": "concept_growth_rate", "operation_family": "growth_rate"},
                {"task_id": "task_summary", "metric_family": "narrative_summary", "operation_family": "aggregate_subtasks"},
            ],
        }
        ordered_results = [current_row, stale_prior_row, stale_growth_row, compact_summary_row]
        aggregate_projection = {
            "calculation_result": {
                "status": "ok",
                "subtask_results": [current_row, stale_prior_row, stale_growth_row, summary_row],
            },
        }

        synced_results, synced_projection = self.agent._sync_projection_subtask_results_with_nested_promotions(
            ordered_results,
            state,
            aggregate_projection,
            "Segment revenue increased 41.4%.",
        )

        prior_row = next(row for row in synced_results if row["task_id"] == "task_prior")
        growth_row = next(row for row in synced_results if row["task_id"] == "task_growth")
        projected_rows = synced_projection["calculation_result"]["subtask_results"]
        projected_growth_row = next(row for row in projected_rows if row["task_id"] == "task_growth")
        projected_summary_row = next(row for row in projected_rows if row["task_id"] == "task_summary")
        projected_summary_nested = projected_summary_row["calculation_result"]["subtask_results"]
        projected_summary_growth_row = next(
            row for row in projected_summary_nested if row["task_id"] == "task_growth"
        )
        projected_summary_prior_rows = [
            row for row in projected_summary_nested if row["task_id"] == "task_prior"
        ]
        self.assertTrue(prior_row.get("promoted_from_nested_aggregate"))
        self.assertEqual(
            prior_row["calculation_result"]["answer_slots"]["primary_value"]["raw_value"],
            "1,801,079",
        )
        self.assertTrue(growth_row.get("aligned_from_source_task_slots"))
        self.assertEqual(growth_row["calculation_result"]["rendered_value"], "41.4%")
        self.assertEqual(
            growth_row["calculation_result"]["answer_slots"]["prior_value"]["raw_value"],
            "1,801,079",
        )
        self.assertEqual(projected_growth_row["calculation_result"]["rendered_value"], "41.4%")
        self.assertEqual(projected_summary_growth_row["calculation_result"]["rendered_value"], "41.4%")
        self.assertTrue(projected_summary_prior_rows)
        self.assertTrue(
            all(
                row["calculation_result"]["answer_slots"]["primary_value"]["raw_value"] == "1,801,079"
                for row in projected_summary_prior_rows
            )
        )

    def test_dependency_slot_alignment_dedupes_stale_operand_ids(self) -> None:
        state = {
            "query": "Calculate segment revenue growth.",
            "calc_subtasks": [
                {"task_id": "task_3", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_4", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_1", "metric_family": "concept_growth_rate", "operation_family": "growth_rate"},
            ],
        }
        ordered_results = [
            {
                "task_id": "task_3",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "concept": "revenue",
                            "period": "2023",
                            "raw_value": "2,546,649",
                            "raw_unit": "million",
                            "normalized_value": 2546649000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "2,546,649 million",
                            "source_row_id": "ev_current",
                        }
                    },
                },
            },
            {
                "task_id": "task_4",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "concept": "revenue",
                            "period": "2022",
                            "raw_value": "1,801,079",
                            "raw_unit": "million",
                            "normalized_value": 1801079000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "1,801,079 million",
                            "source_row_id": "ev_prior",
                        }
                    },
                },
            },
            {
                "task_id": "task_1",
                "metric_family": "concept_growth_rate",
                "operation_family": "growth_rate",
                "calculation_operands": [
                    {
                        "operand_id": "dep_task_3_001",
                        "source_row_id": "task_output:task_3",
                        "source_task_id": "task_3",
                        "source_slot": "primary_value",
                        "matched_operand_role": "current_period",
                        "matched_operand_concept": "revenue",
                        "raw_value": "3,589,061",
                        "raw_unit": "thousand",
                        "normalized_value": 3589061000000.0,
                        "normalized_unit": "KRW",
                    },
                    {
                        "operand_id": "dep_task_4_002",
                        "source_row_id": "task_output:task_4",
                        "source_task_id": "task_4",
                        "source_slot": "primary_value",
                        "matched_operand_role": "prior_period",
                        "matched_operand_concept": "revenue",
                        "raw_value": "2,546,649",
                        "raw_unit": "thousand",
                        "normalized_value": 2546649000000.0,
                        "normalized_unit": "KRW",
                    },
                    {
                        "operand_id": "dep_task_3_001",
                        "source_row_id": "task_output:task_3",
                        "source_task_id": "task_3",
                        "source_slot": "primary_value",
                        "matched_operand_role": "current_period",
                        "matched_operand_concept": "revenue",
                        "raw_value": "2,546,649",
                        "raw_unit": "million",
                        "normalized_value": 2546649000000.0,
                        "normalized_unit": "KRW",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "growth_rate",
                    "ordered_operand_ids": ["dep_task_3_001", "dep_task_4_002"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "dep_task_3_001"},
                        {"variable": "B", "operand_id": "dep_task_4_002"},
                    ],
                    "formula": "((A - B) / B) * 100",
                    "result_unit": "%",
                },
                "calculation_result": {"status": "ok", "rendered_value": "40.93%"},
            },
        ]

        aligned = self.agent._align_lookup_results_with_dependency_projection(ordered_results, state, {})
        growth_row = next(row for row in aligned if row["task_id"] == "task_1")

        self.assertEqual(growth_row["calculation_result"]["rendered_value"], "41.4%")
        operand_ids = [operand["operand_id"] for operand in growth_row["calculation_operands"]]
        self.assertEqual(operand_ids.count("dep_task_3_001"), 1)
        self.assertEqual(operand_ids.count("dep_task_4_002"), 1)

    def test_dependency_projection_refreshes_lookup_unit_when_direct_evidence_supports_it(self) -> None:
        state = {
            "query": "Calculate segment revenue growth.",
            "calc_subtasks": [
                {
                    "task_id": "task_prior",
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "segment revenue",
                            "concept": "revenue",
                            "role": "primary_value",
                            "required": True,
                        }
                    ],
                },
                {"task_id": "task_growth", "metric_family": "concept_growth_rate", "operation_family": "growth_rate"},
            ],
        }
        ordered_results = [
            {
                "task_id": "task_prior",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "answer": "1,801,079 thousand",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "1,801,079 thousand",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment revenue",
                            "concept": "revenue",
                            "period": "2022",
                            "raw_value": "1,801,079",
                            "raw_unit": "thousand",
                            "normalized_value": 1801079000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "1,801,079 thousand",
                            "source_row_id": "task_output:task_prior",
                        },
                    },
                },
            },
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "operation_family": "growth_rate",
                "status": "ok",
                "calculation_result": {"status": "ok", "rendered_value": "41.4%"},
            },
        ]
        aggregate_projection = {
            "calculation_operands": [
                {
                    "operand_id": "dep_task_prior_001",
                    "source_row_id": "task_output:task_prior",
                    "source_row_ids": ["task_output:task_prior", "ev_prior"],
                    "source_task_id": "task_prior",
                    "source_slot": "primary_value",
                    "matched_operand_role": "prior_period",
                    "matched_operand_label": "segment revenue",
                    "matched_operand_concept": "revenue",
                    "label": "segment revenue",
                    "raw_value": "1,801,079",
                    "raw_unit": "million",
                    "normalized_value": 1801079000000.0,
                    "normalized_unit": "KRW",
                    "period": "2022",
                }
            ],
        }

        aligned = self.agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            state,
            aggregate_projection,
        )

        prior_row = aligned[0]
        prior_slot = prior_row["calculation_result"]["answer_slots"]["primary_value"]
        self.assertTrue(prior_row.get("aligned_from_dependency_projection"))
        self.assertNotIn("thousand", prior_row["answer"])
        self.assertEqual(prior_slot["raw_unit"], "million")
        self.assertEqual(prior_slot["normalized_value"], 1801079000000.0)
        self.assertEqual(prior_slot["source_row_id"], "ev_prior")

    def test_preferred_numeric_answer_skips_same_period_growth_row(self) -> None:
        good_row = {
            "task_id": "task_good",
            "metric_family": "concept_growth_rate",
            "operation_family": "growth_rate",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "41.4%",
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {
                        "status": "ok",
                        "label": "segment revenue growth",
                        "normalized_value": 41.4,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "41.4%",
                    },
                    "current_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "period": "2023",
                        "raw_value": "2,546,649",
                        "raw_unit": "million",
                        "normalized_value": 2546649000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "2,546,649 million",
                    },
                    "prior_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "period": "2022",
                        "raw_value": "1,801,079",
                        "raw_unit": "million",
                        "normalized_value": 1801079000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "1,801,079 million",
                    },
                },
            },
        }
        stale_row = {
            "task_id": "task_stale",
            "metric_family": "concept_growth_rate",
            "operation_family": "growth_rate",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "17.65%",
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {
                        "status": "ok",
                        "label": "segment revenue growth",
                        "normalized_value": 17.65,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "17.65%",
                    },
                    "current_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "period": "2023",
                        "raw_value": "9,670.6",
                        "raw_unit": "hundred million",
                        "normalized_value": 967060000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "9,671 hundred million",
                    },
                    "prior_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "period": "2023",
                        "raw_value": "8,220.1",
                        "raw_unit": "hundred million",
                        "normalized_value": 822010000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "8,220 hundred million",
                    },
                },
            },
        }

        answer = self.agent._preferred_complete_numeric_answer([good_row, stale_row])

        self.assertIn("41.4%", answer)
        self.assertNotIn("17.65%", answer)

    def test_material_gap_flags_same_period_growth_row(self) -> None:
        row = {
            "task_id": "task_growth",
            "metric_family": "concept_growth_rate",
            "metric_label": "segment revenue growth",
            "operation_family": "growth_rate",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "17.65%",
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {
                        "status": "ok",
                        "label": "segment revenue growth",
                        "normalized_value": 17.65,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "17.65%",
                    },
                    "current_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "period": "2023",
                        "raw_value": "9,670.6",
                        "raw_unit": "hundred million",
                        "normalized_value": 967060000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "9,671 hundred million",
                    },
                    "prior_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "period": "2023",
                        "raw_value": "8,220.1",
                        "raw_unit": "hundred million",
                        "normalized_value": 822010000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "8,220 hundred million",
                    },
                },
            },
        }

        gap = self.agent._material_gap_feedback_for_subtask_result(row)

        self.assertTrue(gap)
        self.assertIn("segment revenue growth", gap)

    def test_aggregate_projection_does_not_promote_gap_operands(self) -> None:
        row = {
            "task_id": "task_growth",
            "metric_family": "concept_growth_rate",
            "metric_label": "segment revenue growth",
            "operation_family": "growth_rate",
            "answer": "Segment revenue decreased by 17.65%.",
            "status": "ok",
            "calculation_operands": [
                {
                    "operand_id": "current",
                    "matched_operand_role": "current_period",
                    "raw_value": "9,670.6",
                    "raw_unit": "hundred million",
                    "source_row_id": "row_current",
                },
                {
                    "operand_id": "prior",
                    "matched_operand_role": "prior_period",
                    "raw_value": "8,220.1",
                    "raw_unit": "hundred million",
                    "source_row_id": "row_prior",
                },
            ],
            "calculation_result": {
                "status": "ok",
                "rendered_value": "17.65%",
                "source_row_ids": ["row_current", "row_prior"],
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {"status": "ok", "rendered_value": "17.65%"},
                    "current_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "period": "2023",
                        "rendered_value": "9,671 hundred million",
                    },
                    "prior_value": {
                        "status": "ok",
                        "label": "segment revenue",
                        "period": "2023",
                        "rendered_value": "8,220 hundred million",
                    },
                },
            },
        }

        projection = self.agent._build_aggregate_calculation_projection([row], "partial answer")

        self.assertEqual(projection["calculation_operands"], [])
        self.assertEqual(projection["calculation_result"]["source_row_ids"], [])
        projected_child = projection["calculation_result"]["subtask_results"][0]
        self.assertTrue(projected_child["calculation_result"]["material_gap_feedback"])

    def test_late_numeric_refresh_preserves_narrative_summary_child(self) -> None:
        self.agent.llm = None
        self.agent._compose_growth_narrative_answer = lambda **_kwargs: None
        self.agent._align_lookup_results_with_dependency_projection = (
            lambda ordered_results, _state, _projection: list(ordered_results)
        )
        state = {
            "query": "Calculate the 2023 commerce revenue growth rate and summarize the acquisition impact.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_growth_rate", "operation_family": "growth_rate"},
                {"task_id": "task_2", "metric_family": "narrative_summary", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 1,
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "operation_family": "narrative_summary",
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "commerce revenue growth rate",
                    "answer": "2023 commerce revenue was up 41.4%.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "41.4%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "commerce revenue growth rate",
                                "period": "2023",
                                "rendered_value": "41.4%",
                                "normalized_value": 41.4,
                                "normalized_unit": "PERCENT",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "commerce revenue",
                                "period": "2023",
                                "rendered_value": "2,546,649 million",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "commerce revenue",
                                "period": "2022",
                                "rendered_value": "1,801,079 million",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "acquisition impact summary",
                    "answer": "The acquisition integration improved commerce revenue growth.",
                    "status": "ok",
                    "selected_claim_ids": ["ev_driver"],
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {"operation_family": "narrative_summary"},
                    },
                },
            ],
            "answer": "The acquisition integration improved commerce revenue growth.",
            "compressed_answer": "The acquisition integration improved commerce revenue growth.",
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": ["ev_driver"],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("41.4%", updated["answer"])
        self.assertIn("2,546,649 million", updated["answer"])
        self.assertIn("1,801,079 million", updated["answer"])
        self.assertIn("acquisition integration improved", updated["answer"])
        self.assertIn("ev_driver", updated["selected_claim_ids"])

    def test_late_runtime_numeric_answer_promotes_supported_aggregate_formatted_result(self) -> None:
        nested_results = [
            {
                "task_id": "task_1",
                "metric_family": "concept_growth_rate",
                "metric_label": "commerce revenue growth rate",
                "operation_family": "growth_rate",
                "answer": "41.4%",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "41.4%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {
                            "status": "ok",
                            "label": "commerce revenue growth rate",
                            "period": "2023",
                            "rendered_value": "41.4%",
                            "normalized_value": 41.4,
                            "normalized_unit": "PERCENT",
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "commerce revenue",
                            "period": "2023",
                            "rendered_value": "2,546,649 million",
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "commerce revenue",
                            "period": "2022",
                            "rendered_value": "1,801,079 million",
                        },
                    },
                },
            },
            {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "metric_label": "acquisition impact summary",
                "operation_family": "narrative_summary",
                "answer": "The acquisition integration improved commerce revenue growth.",
                "status": "ok",
                "selected_claim_ids": ["ev_driver"],
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {"operation_family": "narrative_summary"},
                },
            },
        ]
        formatted_result = (
            "2023 commerce revenue was 2,546,649 million, "
            "up 41.4% from 1,801,079 million. "
            "The acquisition integration improved commerce revenue growth."
        )
        state = {
            "query": "Calculate the 2023 commerce revenue growth rate and summarize the acquisition impact.",
            "resolved_calculation_trace": {
                "calculation_plan": {"operation": "aggregate_subtasks"},
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "aggregate_subtasks",
                    "formatted_result": formatted_result,
                    "answer_slots": {"operation_family": "aggregate_subtasks"},
                    "subtask_results": nested_results,
                },
                "calculation_operands": [],
            },
            "evidence_items": [
                {
                    "evidence_id": "ev_driver",
                    "claim": "The acquisition integration improved commerce revenue growth.",
                    "text": "The acquisition integration improved commerce revenue growth.",
                }
            ],
        }

        answer = self.agent._late_runtime_numeric_answer(
            state,
            "The acquisition integration improved commerce revenue growth.",
        )

        self.assertEqual(answer, formatted_result)

    def test_late_numeric_refresh_keeps_clean_explicit_explanation_from_conflicting_summary_child(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": (
                        "2023년 서비스 매출액은 2,546,649 million이며, "
                        "2022년 1,801,079 million 대비 41.4% 증가했습니다."
                    ),
                    "planner_feedback": "",
                }
            )
        )
        self.agent._compose_growth_narrative_answer = lambda **_kwargs: None

        def _aligned_results(ordered_results, _state, _projection):
            aligned = []
            for row in ordered_results:
                if row.get("task_id") == "task_1":
                    aligned.append({**dict(row), "aligned_from_source_task_slots": True})
                else:
                    aligned.append(dict(row))
            return aligned

        self.agent._align_lookup_results_with_dependency_projection = _aligned_results
        state = {
            "query": "2023년 서비스 매출액 증가율을 계산하고, 그 원인을 요약해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_growth_rate", "operation_family": "growth_rate"},
                {"task_id": "task_2", "metric_family": "narrative_summary", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 1,
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "operation_family": "narrative_summary",
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "서비스 매출액 증가율",
                    "answer": "41.4%",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "41.4%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "서비스 매출액 증가율",
                                "period": "2023",
                                "normalized_value": 41.4,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "41.4%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "서비스 매출액",
                                "period": "2023",
                                "rendered_value": "2,546,649 million",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "서비스 매출액",
                                "period": "2022",
                                "rendered_value": "1,801,079 million",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "증가 원인",
                    "answer": (
                        "2023년 서비스 매출액은 2,540,000 million이며, "
                        "2022년 1,800,000 million 대비 40.9% 증가했습니다. "
                        "신규 채널 확장이 증가 원인입니다."
                    ),
                    "status": "ok",
                    "selected_claim_ids": ["ev_driver"],
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {"operation_family": "narrative_summary"},
                    },
                },
            ],
            "answer": "",
            "compressed_answer": "",
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("41.4%", updated["answer"])
        self.assertIn("2,546,649 million", updated["answer"])
        self.assertIn("1,801,079 million", updated["answer"])
        self.assertIn("신규 채널 확장", updated["answer"])
        self.assertNotIn("40.9%", updated["answer"])
        self.assertIn("ev_driver", updated["selected_claim_ids"])

    def test_late_source_surface_preservation_keeps_numeric_contract_with_explicit_explanation(self) -> None:
        self.agent.llm = None
        self.agent._compose_growth_narrative_answer = lambda **_kwargs: None
        self.agent._align_lookup_results_with_dependency_projection = (
            lambda ordered_results, _state, _projection: list(ordered_results)
        )
        self.agent._preserve_retrieved_narrative_source_surface = (
            lambda _answer, _evidence_items: "The acquisition improved commerce revenue growth by 41.4%."
        )
        state = {
            "query": "Calculate the 2023 commerce revenue growth rate and summarize the acquisition impact.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_growth_rate", "operation_family": "growth_rate"},
                {"task_id": "task_2", "metric_family": "narrative_summary", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 1,
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "operation_family": "narrative_summary",
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "commerce revenue growth rate",
                    "answer": "2023 commerce revenue was up 41.4%.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "41.4%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "commerce revenue growth rate",
                                "period": "2023",
                                "rendered_value": "41.4%",
                                "normalized_value": 41.4,
                                "normalized_unit": "PERCENT",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "commerce revenue",
                                "period": "2023",
                                "rendered_value": "2,546,649 million",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "commerce revenue",
                                "period": "2022",
                                "rendered_value": "1,801,079 million",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "acquisition impact summary",
                    "answer": "The acquisition improved commerce revenue growth by 41.4%.",
                    "status": "ok",
                    "selected_claim_ids": ["ev_driver"],
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {"operation_family": "narrative_summary"},
                    },
                },
            ],
            "answer": "The acquisition improved commerce revenue growth by 41.4%.",
            "compressed_answer": "The acquisition improved commerce revenue growth by 41.4%.",
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": ["ev_driver"],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("41.4%", updated["answer"])
        self.assertIn("2,546,649 million", updated["answer"])
        self.assertIn("1,801,079 million", updated["answer"])
        self.assertIn("acquisition improved commerce revenue growth", updated["answer"])

    def test_policy_required_realized_context_preserves_retrieved_aum_table(self) -> None:
        answer = (
            "2023년 순수수료이익은 3,673,524백만원이며, "
            "2022년 3,514,902백만원 대비 4.51% 증가했습니다. "
            "위탁/자산관리 부문의 영업이익은 전년 대비 1,162억원 증가한 2,654억원을 기록했습니다."
        )
        docs = [
            (
                Document(
                    page_content=(
                        "구 분 | 구 분 | 2023년 | 2023년 | 2022년 | 2021년 "
                        "총관리자산(AUM) 주1) | 총관리자산(AUM) 주1) | 1,216,729 | 70,039 | 1,146,691 | 1,117,859"
                    ),
                    metadata={
                        "block_type": "table",
                        "period_focus": "current",
                        "unit_hint": "억원",
                        "table_context": "* 계열사별 총관리자산(AUM) 현황",
                        "table_value_labels_text": (
                            "총관리자산(AUM) 주1) 1,216,729 "
                            "총관리자산(AUM) 주1) 70,039 "
                            "총관리자산(AUM) 주1) 1,146,691"
                        ),
                    },
                ),
                0.7,
            )
        ]

        preserved = self.agent._preserve_policy_required_realized_context(
            answer,
            query="2023년 순수수료이익 증가율을 계산하고, 자산관리(WM) 부문의 성과를 요약해 줘.",
            docs=docs,
        )

        self.assertIn("총관리자산(AUM)", preserved)
        self.assertIn("1,216,729억원", preserved)
        self.assertIn("70,039억원", preserved)

    def test_nonfocus_numeric_narrative_pruning_keeps_growth_and_policy_required_context(self) -> None:
        ordered_results = [
            {
                "task_id": "task_1",
                "metric_family": "concept_growth_rate",
                "metric_label": "net fee income growth",
                "operation_family": "growth_rate",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "4.51%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {
                            "status": "ok",
                            "label": "net fee income growth",
                            "period": "2023",
                            "rendered_value": "4.51%",
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "net fee income",
                            "period": "2023",
                            "rendered_value": "3,673,524 million",
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "net fee income",
                            "period": "2022",
                            "rendered_value": "3,514,902 million",
                        },
                    },
                },
            },
            {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "metric_label": "WM performance summary",
                "operation_family": "narrative_summary",
                "status": "ok",
                "answer": "WM operating profit was 2,654.",
            },
        ]
        answer = (
            "Non-interest income increased by 18,230 to 40,880. "
            "Net fee income was 3,673,524 million, up 4.51% from 3,514,902 million. "
            "Total managed assets (AUM) were 1,216,729."
        )

        pruned = self.agent._prune_nonfocus_numeric_narrative_sentences(
            answer,
            query="2023년 순수수료이익 증가율을 계산하고, 자산관리(WM) 부문의 성과를 요약해 줘.",
            ordered_results=ordered_results,
            evidence_items=[],
        )

        self.assertNotIn("Non-interest income", pruned)
        self.assertIn("3,673,524 million", pruned)
        self.assertIn("4.51%", pruned)
        self.assertIn("AUM", pruned)
        self.assertIn("1,216,729", pruned)

    def test_policy_required_context_updates_narrative_result_trace(self) -> None:
        ordered_results = [
            {
                "task_id": "task_1",
                "metric_family": "concept_growth_rate",
                "metric_label": "net fee income growth",
                "operation_family": "growth_rate",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "4.51%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {
                            "status": "ok",
                            "label": "net fee income growth",
                            "period": "2023",
                            "rendered_value": "4.51%",
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "net fee income",
                            "period": "2023",
                            "rendered_value": "3,673,524 million",
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "net fee income",
                            "period": "2022",
                            "rendered_value": "3,514,902 million",
                        },
                    },
                },
            },
            {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "metric_label": "WM performance summary",
                "operation_family": "narrative_summary",
                "status": "ok",
                "answer": "Non-interest income increased by 18,230 to 40,880. WM operating profit was 2,654.",
                "calculation_result": {
                    "status": "ok",
                    "formatted_result": "Non-interest income increased by 18,230 to 40,880. WM operating profit was 2,654.",
                    "rendered_value": "Non-interest income increased by 18,230 to 40,880. WM operating profit was 2,654.",
                },
            },
        ]
        docs = [
            (
                Document(
                    page_content="Total managed assets (AUM) | 1,216,729 | 70,039 | 1,146,691",
                    metadata={
                        "block_type": "table",
                        "period_focus": "current",
                        "unit_hint": "억원",
                        "table_context": "* 계열사별 총관리자산(AUM) 현황",
                        "table_value_labels_text": (
                            "총관리자산(AUM) 주1) 1,216,729 "
                            "총관리자산(AUM) 주1) 70,039 "
                            "총관리자산(AUM) 주1) 1,146,691"
                        ),
                    },
                ),
                0.7,
            )
        ]

        updated = self.agent._preserve_policy_required_context_in_narrative_results(
            ordered_results,
            query="2023년 순수수료이익 증가율을 계산하고, 자산관리(WM) 부문의 성과를 요약해 줘.",
            docs=docs,
            evidence_items=[],
        )

        narrative_answer = updated[1]["answer"]
        self.assertNotIn("Non-interest income", narrative_answer)
        self.assertIn("WM operating profit", narrative_answer)
        self.assertIn("총관리자산(AUM)", narrative_answer)
        self.assertIn("1,216,729억원", narrative_answer)
        self.assertEqual(updated[1]["calculation_result"]["formatted_result"], narrative_answer)

    def test_aggregate_subtasks_keeps_slot_based_difference_answer_when_numeric_locked(self) -> None:
        self.agent.llm = None
        state = {
            "query": "2023년 연결기준 영업이익을 확인하고, 세액공제 금액을 제외했을 때의 실질 영업이익을 계산해 줘.",
            "report_scope": {"company": "테스트회사", "consolidation_scope": "consolidated"},
            "calc_subtasks": [{"task_id": "task_1"}, {"task_id": "task_2"}],
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "adjusted_difference",
                    "metric_label": "실질 영업이익",
                    "answer": "1,486,334백만원",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "1,486,334백만원",
                        "answer_slots": {
                            "operation_family": "difference",
                            "primary_value": {
                                "status": "ok",
                                "label": "실질 영업이익",
                                "period": "2023",
                                "rendered_value": "1,486,334백만원",
                            },
                            "components_by_role": {
                                "minuend": [
                                    {
                                        "status": "ok",
                                        "label": "영업이익",
                                        "period": "2023",
                                        "rendered_value": "2,163,234백만원",
                                    }
                                ],
                                "subtrahend": [
                                    {
                                        "status": "ok",
                                        "label": "세액공제",
                                        "period": "2023",
                                        "rendered_value": "676,900백만원",
                                    }
                                ],
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "계산 배경",
                    "answer": "세액공제 금액은 영업이익에서 제외해 조정값을 산출합니다.",
                    "status": "ok",
                    "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                },
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertIn("영업이익", updated["answer"])
        self.assertIn("2,163,234백만원", updated["answer"])
        self.assertIn("세액공제", updated["answer"])
        self.assertIn("676,900백만원", updated["answer"])
        self.assertIn("실질 영업이익", updated["answer"])
        self.assertIn("1,486,334백만원", updated["answer"])

    def test_aggregate_subtasks_does_not_repair_growth_answer_without_narrative_material(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 커머스 부문 매출은 2조 5,466억원이고 전년 대비 41.4% 성장했습니다. 또한 Poshmark 인수는 커머스 실",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 커머스 부문 매출 성장률을 계산하고, Poshmark 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            "calc_subtasks": [{"task_id": "task_1"}],
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "커머스 부문 매출 성장률",
                    "answer": "커머스 부문 매출은 전년 대비 41.4% 성장했습니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "41.4%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {"status": "ok", "period": "2023", "rendered_value": "41.4%"},
                            "current_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출액",
                                "concept": "revenue",
                                "period": "2023",
                                "rendered_value": "2조 5,466억원",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출액",
                                "concept": "revenue",
                                "period": "2022",
                                "rendered_value": "1조 8,011억원",
                            },
                        },
                    },
                },
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["answer"], "2023년 커머스 부문 매출은 2조 5,466억원이고 전년 대비 41.4% 성장했습니다. 또한 Poshmark 인수는 커머스 실")

    def test_aggregate_subtasks_suppresses_growth_narrative_feedback_when_answer_is_complete(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 커머스 부문의 매출은 전년 대비 41.4% 성장했습니다. 이러한 성장은 Poshmark 인수와 연결 편입 효과가 커머스 실적에 기여한 결과입니다.",
                    "planner_feedback": "커머스 부문 매출 성장률 계산 결과가 누락되었습니다.",
                }
            )
        )
        state = {
            "query": "2023년 커머스 부문 매출 성장률을 계산하고, Poshmark 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1"},
                {"task_id": "task_2"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "커머스 부문 매출 성장률",
                    "answer": "커머스 부문 매출은 전년 대비 41.4% 성장했습니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "missing",
                                "label": "커머스 부문 매출 성장률",
                                "raw_unit": "%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출액",
                                "period": "2023",
                                "rendered_value": "2조 5,466억원",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출액",
                                "period": "2022",
                                "rendered_value": "1조 8,011억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "질문 관련 배경/영향 설명",
                    "answer": "Poshmark 연결 편입 효과가 커머스 성장에 기여했습니다.",
                    "status": "ok",
                    "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                },
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_feedback"], "")
        self.assertNotIn("완전히 확정할 수는 없습니다", updated["answer"])
        self.assertIn("41.4%", updated["answer"])
        self.assertIn("Poshmark", updated["answer"])

    def test_aggregate_subtasks_polishes_korean_conjunctive_particle_noise(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": (
                        "2023년 커머스 부문 매출액은 2조 5,466억원이며, 2022년 1조 8,011억원 대비 "
                        "41.4% 성장했습니다. 스마트스토어와 브랜드스토어의 성장와 연결 편입 효과도 "
                        "실적 성장에 기여했습니다."
                    ),
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 커머스 부문 매출 성장률을 계산하고, 커머스 실적 성장 배경을 요약해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1"},
                {"task_id": "task_2"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "커머스 부문 매출 성장률",
                    "answer": "커머스 부문 매출은 전년 대비 41.4% 성장했습니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "41.4%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출 성장률",
                                "period": "2023",
                                "normalized_value": 41.4,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "41.4%",
                            },
                            "current_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출액",
                                "period": "2023",
                                "rendered_value": "2조 5,466억원",
                            },
                            "prior_value": {
                                "status": "ok",
                                "label": "커머스 부문 매출액",
                                "period": "2022",
                                "rendered_value": "1조 8,011억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "질문 관련 배경/영향 설명",
                    "answer": "스마트스토어와 브랜드스토어의 성장, 연결 편입 효과가 실적 성장에 기여했습니다.",
                    "status": "ok",
                    "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                },
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)
        trace = _resolve_runtime_calculation_trace(updated)

        self.assertIn("스마트스토어와", updated["answer"])
        self.assertIn("성장과 연결 편입 효과", updated["answer"])
        self.assertNotIn("성장와", updated["answer"])
        self.assertEqual(trace["calculation_result"]["formatted_result"], updated["answer"])

    def test_aggregate_subtasks_repairs_growth_answer_omitting_operand_values(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 연결기준 시설투자(CAPEX) 총액 증감률은 0.0026% 감소했습니다.",
                    "planner_feedback": "",
                }
            )
        )
        state = {
            "query": "2023년 시설투자(CAPEX) 총액을 찾고, 전년(2022년) 대비 증감률을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1"},
                {"task_id": "task_2"},
                {"task_id": "task_3"},
                {"task_id": "task_4"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 시설투자(CAPEX) 총액",
                    "answer": "2023년 시설투자(CAPEX) 총액은 531,139억원입니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "period": "2023",
                                "label": "2023 시설투자(CAPEX)",
                                "rendered_value": "531,139억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022년 시설투자(CAPEX)",
                    "answer": "2022년 시설투자(CAPEX)는 531,153억원입니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "period": "2022",
                                "label": "시설투자(CAPEX)",
                                "rendered_value": "531,153억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "시설투자(CAPEX) 총액 증감률",
                    "answer": "2023년 연결기준 시설투자(CAPEX) 총액 증감률은 0.0026% 감소했습니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "0.0026%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "period": "2023",
                                "normalized_value": -0.0026357,
                                "rendered_value": "-0.0026%",
                            },
                            "current_value": {
                                "status": "ok",
                                "period": "2023",
                                "label": "시설투자(CAPEX) 총액",
                                "rendered_value": "53조 1,139억원",
                                "source_row_id": "task_output:task_1",
                            },
                            "prior_value": {
                                "status": "ok",
                                "period": "2022",
                                "label": "시설투자(CAPEX) 총액",
                                "rendered_value": "53조 1,153억원",
                                "source_row_id": "task_output:task_2",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_4",
                    "metric_family": "narrative_summary",
                    "metric_label": "질문 관련 배경",
                    "answer": "2023년 업황 악화에도 불구하고 시설투자가 집행되었습니다.",
                    "status": "ok",
                    "calculation_result": {"status": "ok", "answer_slots": {"operation_family": "narrative_summary"}},
                },
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_feedback"], "")
        self.assertIn("531,139억원", updated["answer"])
        self.assertIn("531,153억원", updated["answer"])
        self.assertIn("0.0026% 감소", updated["answer"])
        self.assertNotIn("53조 1,139억원", updated["answer"])

    def test_policy_growth_cases_do_not_use_case_specific_composer(self) -> None:
        self.assertFalse(hasattr(self.agent, "_compose_sales_growth_policy_answer"))


if __name__ == "__main__":
    unittest.main()
