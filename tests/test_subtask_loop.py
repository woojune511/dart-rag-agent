import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import AggregateSynthesisOutput


class _StubStructuredLLM:
    def __init__(self, response):
        self._response = response

    def invoke(self, _prompt_value):
        return self._response


class _StubLLM:
    def __init__(self, response):
        self._response = response

    def with_structured_output(self, _schema):
        return _StubStructuredLLM(self._response)


class SubtaskLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = FinancialAgent.__new__(FinancialAgent)

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
                    "calculation_operands": [
                        {"row_id": "debt", "label_kr": "부채총계", "value": "92228115"},
                        {"row_id": "equity", "label_kr": "자본총계", "value": "363677865"},
                    ],
                    "calculation_plan": {"status": "ok", "operation": "divide"},
                    "calculation_result": {"status": "ok", "rendered_value": "25.4%"},
                    "reconciliation_result": {"status": "ready"},
                }
            ],
            "answer": "2023년 연결기준 유동비율은 258.8%입니다.",
            "compressed_answer": "2023년 연결기준 유동비율은 258.8%입니다.",
            "selected_claim_ids": ["ev_002"],
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
        self.assertEqual(len(updated["calculation_operands"]), 4)
        self.assertEqual(updated["calculation_plan"]["mode"], "aggregate_subtasks")
        self.assertEqual(updated["calculation_plan"]["subtask_count"], 2)
        self.assertEqual(updated["calculation_result"]["formatted_result"], updated["answer"])
        self.assertEqual(
            updated["calculation_result"]["derived_metrics"]["subtask_ids"],
            ["task_1", "task_2"],
        )

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


if __name__ == "__main__":
    unittest.main()
