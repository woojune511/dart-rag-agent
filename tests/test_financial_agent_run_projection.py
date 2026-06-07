import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import FinancialAgentState


class _FakeGraph:
    def __init__(self, final_state):
        self._final_state = final_state
        self.initial_state = None

    def invoke(self, initial):
        self.initial_state = dict(initial)
        return dict(self._final_state)


class _FakeDoc:
    def __init__(self, page_content, metadata=None):
        self.page_content = page_content
        self.metadata = dict(metadata or {})


class FinancialAgentRunProjectionTests(unittest.TestCase):
    def test_state_typing_keeps_legacy_calculation_and_debug_surfaces_optional(self) -> None:
        self.assertIn("calculation_operands", FinancialAgentState.__optional_keys__)
        self.assertIn("calculation_plan", FinancialAgentState.__optional_keys__)
        self.assertIn("calculation_result", FinancialAgentState.__optional_keys__)
        self.assertIn("calculation_debug_trace", FinancialAgentState.__optional_keys__)
        self.assertIn("debug_traces", FinancialAgentState.__optional_keys__)
        self.assertIn("reflection_request", FinancialAgentState.__optional_keys__)
        self.assertIn("reflection_action", FinancialAgentState.__optional_keys__)
        self.assertIn("reflection_report", FinancialAgentState.__optional_keys__)
        self.assertNotIn("calculation_debug_trace", FinancialAgentState.__required_keys__)

    def _base_final_state(self):
        return {
            "query": "test question",
            "report_scope": {},
            "query_type": "comparison",
            "intent": "comparison",
            "planner_mode": "initial",
            "planner_feedback": "",
            "plan_loop_count": 0,
            "target_metric_family": "debt_ratio",
            "target_metric_family_hint": "debt_ratio",
            "planned_metric_families": ["debt_ratio"],
            "format_preference": "brief",
            "routing_source": "rule",
            "routing_confidence": 0.9,
            "routing_scores": {"comparison": 0.9},
            "companies": ["삼성전자"],
            "years": [2023],
            "answer": "25.4%",
            "citations": ["[1]"],
            "seed_retrieved_docs": [],
            "retrieved_docs": [],
            "retrieval_debug_trace": {"selected_count": 1},
            "retrieval_debug_trace_history": [],
            "evidence_items": [],
            "selected_claim_ids": [],
            "draft_points": [],
            "kept_claim_ids": [],
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "numeric_debug_trace": {},
            "calculation_operands": [{"label": "stale", "value": "999"}],
            "calculation_plan": {"status": "stale"},
            "calculation_result": {"status": "stale", "rendered_value": "999"},
            "calculation_debug_trace": {"source": "unit_test"},
            "planner_debug_trace": {},
            "missing_info": [],
            "reflection_count": 0,
            "retry_reason": "",
            "retry_queries": [],
            "reconciliation_retry_count": 0,
            "reflection_plan": {},
            "semantic_plan": {},
            "calc_subtasks": [],
            "retrieval_queries": [],
            "active_subtask_index": 0,
            "active_subtask": {},
            "subtask_results": [],
            "subtask_debug_trace": {},
            "subtask_loop_complete": False,
            "reconciliation_result": {},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {
                "calculation_operands": [{"label": "fresh", "value": "123"}],
                "calculation_plan": {"operation": "lookup"},
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "123",
                    "answer_slots": {"operation_family": "lookup"},
                },
            },
        }

    def test_run_prefers_resolved_trace_and_omits_flat_compatibility_mirrors(self) -> None:
        final_state = self._base_final_state()
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(result["structured_result"]["rendered_value"], "123")
        self.assertEqual(
            result["resolved_calculation_trace"]["calculation_plan"]["operation"],
            "lookup",
        )
        self.assertEqual(
            result["resolved_calculation_trace"]["calculation_operands"],
            [{"label": "fresh", "value": "123"}],
        )
        self.assertEqual(
            result["resolved_calculation_trace"]["runtime_projection"]["source"],
            "resolved_calculation_trace",
        )
        self.assertFalse(
            result["resolved_calculation_trace"]["runtime_projection"]["legacy_fallback"]
        )
        self.assertEqual(result["retrieval_debug_trace"], {"selected_count": 1})
        self.assertEqual(result["reflection_request"], {})
        self.assertEqual(result["reflection_action"], {})
        self.assertEqual(result["reflection_report"], {})
        self.assertNotIn("calculation_operands", result)
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)
        self.assertNotIn("legacy_calculation_projection", result)

    def test_run_initial_state_does_not_seed_optional_calculation_mirrors(self) -> None:
        final_state = self._base_final_state()
        fake_graph = _FakeGraph(final_state)
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = fake_graph
        agent.vsm = object()

        agent.run("test question")

        self.assertNotIn("calculation_operands", fake_graph.initial_state)
        self.assertNotIn("calculation_plan", fake_graph.initial_state)
        self.assertNotIn("calculation_result", fake_graph.initial_state)
        self.assertNotIn("calculation_debug_trace", fake_graph.initial_state)

    def test_run_projects_calculation_debug_trace_under_debug_traces(self) -> None:
        final_state = self._base_final_state()
        final_state["calculation_debug_trace"] = {
            "source": "structured_row_direct",
            "coverage": "sufficient",
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(
            result["debug_traces"]["calculation"],
            {"source": "structured_row_direct", "coverage": "sufficient"},
        )
        self.assertEqual(
            result["calculation_debug_trace"],
            result["debug_traces"]["calculation"],
        )

    def test_run_debug_trace_projection_tolerates_missing_calculation_debug_trace(self) -> None:
        final_state = self._base_final_state()
        final_state.pop("calculation_debug_trace", None)
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(result["debug_traces"]["calculation"], {})
        self.assertEqual(result["calculation_debug_trace"], {})

    def test_run_public_projection_adds_read_only_report_cache_candidate(self) -> None:
        final_state = self._base_final_state()
        final_state["report_scope"] = {
            "company": "ACME",
            "report_type": "annual",
            "rcept_no": "r1",
            "year": "2023",
        }
        final_state["active_subtask"] = {
            "metric_family": "metric_family",
            "metric_label": "metric label",
        }
        final_state["resolved_calculation_trace"]["calculation_operands"] = [
            {
                "label": "metric",
                "raw_value": "123",
                "period": "2023",
                "consolidation_scope": "consolidated",
                "statement_type": "statement",
                "source_section": "section",
                "table_source_id": "table-1",
                "source_row_id": "row-1",
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        candidate = result["resolved_calculation_trace"]["report_cache_candidate"]
        self.assertTrue(candidate["read_only"])
        self.assertEqual(candidate["status"], "reusable")
        self.assertEqual(candidate["key"]["company"], "ACME")
        self.assertEqual(candidate["key"]["metric_label"], "metric label")

    def test_run_public_projection_preserves_legacy_top_level_trace_without_flat_mirrors(self) -> None:
        final_state = self._base_final_state()
        final_state["resolved_calculation_trace"] = {}
        final_state["structured_result"] = {}
        final_state["calculation_operands"] = [{"label": "legacy", "value": "25.4"}]
        final_state["calculation_plan"] = {"status": "ok", "operation": "lookup"}
        final_state["calculation_result"] = {
            "status": "ok",
            "rendered_value": "25.4%",
            "answer_slots": {"operation_family": "lookup"},
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["resolved_calculation_trace"]
        self.assertEqual(trace["calculation_result"]["rendered_value"], "25.4%")
        self.assertEqual(trace["runtime_projection"]["source"], "legacy_top_level")
        self.assertTrue(trace["runtime_projection"]["legacy_fallback"])
        self.assertNotIn("calculation_operands", result)
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)

    def test_run_preserves_numeric_runtime_evidence_from_retrieved_docs_when_empty(self) -> None:
        final_state = self._base_final_state()
        final_state["resolved_calculation_trace"] = {}
        final_state["structured_result"] = {}
        final_state["calculation_operands"] = []
        final_state["calculation_plan"] = {}
        final_state["calculation_result"] = {}
        final_state["retrieved_docs"] = [
            _FakeDoc(
                "Metric table row shows current period value 25.4%.",
                {"section_path": "Financial review", "block_type": "table"},
            )
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(len(result["evidence_items"]), 1)
        self.assertEqual(result["evidence_items"][0]["evidence_id"], "retrieved::001")
        self.assertIn("25.4%", result["evidence_items"][0]["quote_span"])

    def test_run_keeps_existing_runtime_evidence(self) -> None:
        final_state = self._base_final_state()
        final_state["evidence_items"] = [
            {
                "evidence_id": "ev_existing",
                "source_anchor": "Existing section",
                "claim": "Existing claim",
                "quote_span": "Existing quote",
                "metadata": {},
            }
        ]
        final_state["retrieved_docs"] = [
            _FakeDoc("Metric table row shows current period value 25.4%.")
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual([item["evidence_id"] for item in result["evidence_items"]], ["ev_existing"])

    def test_run_filters_existing_runtime_evidence_with_trace_operand_support(self) -> None:
        final_state = self._base_final_state()
        final_state["answer"] = "The final ratio is 25.4%."
        final_state["evidence_items"] = [
            {
                "evidence_id": "ev_wrong",
                "source_anchor": "Segment table",
                "claim": "A context-dependent segment row shows 99.9%.",
                "quote_span": "A context-dependent segment row shows 99.9%.",
                "metadata": {},
            }
        ]
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [
                {
                    "operand_id": "ratio_operand",
                    "label": "final ratio",
                    "raw_value": "25.4",
                    "raw_unit": "%",
                    "normalized_value": 25.4,
                    "normalized_unit": "PERCENT",
                    "source_anchor": "Supported table",
                    "matched_operand_role": "primary_value",
                }
            ],
            "calculation_plan": {"operation": "lookup"},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "25.4%",
                "answer_slots": {"operation_family": "lookup"},
            },
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual([item["evidence_id"] for item in result["evidence_items"]], ["operand::ratio_operand"])
        self.assertIn("25.4%", result["evidence_items"][0]["quote_span"])

    def test_run_projects_operand_runtime_evidence_with_report_scope_metadata(self) -> None:
        final_state = self._base_final_state()
        final_state["report_scope"] = {"company": "NAVER", "year": 2023}
        final_state["companies"] = ["NAVER"]
        final_state["years"] = [2023]
        final_state["answer"] = (
            "네이버의 2023년 연결기준 잉여현금흐름은 1조 3,616억원입니다. "
            "이는 영업활동현금흐름 2조 22억원에서 유형자산 취득액 6,406억원을 "
            "차감하여 계산된 결과입니다."
        )
        final_state["citations"] = []
        final_state["evidence_items"] = []
        final_state["retrieved_docs"] = []
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [
                {
                    "operand_id": "operating_cash_flow",
                    "label": "2023 영업활동현금흐름",
                    "raw_value": "2,002,233,273,518",
                    "raw_unit": "원",
                    "rendered_value": "2조 22억원",
                    "normalized_unit": "KRW",
                    "matched_operand_role": "minuend",
                    "source_anchor": "III. 재무에 관한 사항 > 연결현금흐름표",
                    "source_quote": "영업활동현금흐름 2,002,233,273,518원",
                },
                {
                    "operand_id": "ppe_acquisition",
                    "label": "2023 유형자산 취득액",
                    "raw_value": "(640,623,697,250)",
                    "raw_unit": "원",
                    "rendered_value": "6,406억원",
                    "normalized_unit": "KRW",
                    "matched_operand_role": "subtrahend",
                    "source_anchor": "III. 재무에 관한 사항 > 연결현금흐름표",
                    "source_quote": "유형자산의 취득 (640,623,697,250)원",
                },
            ],
            "calculation_plan": {"operation": "subtract"},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "1조 3,616억원",
                "answer_slots": {"operation_family": "difference"},
            },
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        evidence_ids = [item["evidence_id"] for item in result["evidence_items"]]
        self.assertEqual(evidence_ids, ["operand::operating_cash_flow", "operand::ppe_acquisition"])
        self.assertTrue(all(item["metadata"]["company"] == "NAVER" for item in result["evidence_items"]))
        self.assertTrue(all(item["metadata"]["year"] == 2023 for item in result["evidence_items"]))
        self.assertTrue(any("NAVER | 2023 | III. 재무에 관한 사항" in item for item in result["citations"]))

    def test_run_projects_task_artifact_trace_for_callers(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_1",
                "kind": "calculation",
                "label": "ratio calculation",
                "status": "completed",
                "metric_family": "ratio",
                "artifact_ids": ["artifact_1", "artifact_missing"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_1",
                "task_id": "task_1",
                "kind": "calculation_result",
                "status": "ok",
                "summary": "25.4%",
                "payload": {"calculation_result": {"rendered_value": "25.4%"}},
                "evidence_refs": ["ev_001"],
            },
            {
                "artifact_id": "artifact_orphan",
                "task_id": "missing_task",
                "kind": "operand_set",
                "status": "ok",
                "summary": "unused",
                "payload": {"calculation_operands": []},
                "evidence_refs": [],
            },
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(result["tasks"], final_state["tasks"])
        self.assertEqual(result["artifacts"], final_state["artifacts"])
        trace = result["task_artifact_trace"]
        self.assertEqual(trace["task_count"], 1)
        self.assertEqual(trace["artifact_count"], 2)
        self.assertEqual(trace["tasks"][0]["latest_artifact_id"], "artifact_1")
        self.assertEqual(trace["tasks"][0]["latest_artifact_summary"], "25.4%")
        self.assertEqual(trace["artifacts"][0]["payload_keys"], ["calculation_result"])
        self.assertEqual(trace["orphan_artifact_ids"], ["artifact_orphan"])
        self.assertEqual(trace["missing_artifact_ids"], ["artifact_missing"])
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            [
                "missing_artifact_reference",
                "orphan_artifact",
                "missing_required_artifact_kind",
                "missing_required_artifact_kind",
            ],
        )
        self.assertEqual(
            [
                issue.get("artifact_kind")
                for issue in trace["integrity_issues"]
                if issue["type"] == "missing_required_artifact_kind"
            ],
            ["calculation_plan", "operand_set"],
        )

    def test_run_marks_completed_calculation_without_artifacts_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_1",
                "kind": "calculation",
                "label": "ratio calculation",
                "status": "completed",
                "metric_family": "ratio",
                "artifact_ids": [],
            }
        ]
        final_state["artifacts"] = []
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issue_count"], 5)
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            [
                "task_without_artifacts",
                "missing_required_artifact_kind",
                "missing_required_artifact_kind",
                "missing_required_artifact_kind",
                "missing_required_evidence_ref",
            ],
        )
        self.assertEqual(
            [
                issue.get("artifact_kind")
                for issue in trace["integrity_issues"]
                if issue["type"] == "missing_required_artifact_kind"
            ],
            ["calculation_plan", "calculation_result", "operand_set"],
        )

    def test_run_marks_completed_calculation_with_empty_payloads_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_1",
                "kind": "calculation",
                "label": "ratio calculation",
                "status": "completed",
                "metric_family": "ratio",
                "artifact_ids": ["artifact_operand", "artifact_plan", "artifact_result"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_operand",
                "task_id": "task_1",
                "kind": "operand_set",
                "status": "ok",
                "payload": {"calculation_operands": []},
            },
            {
                "artifact_id": "artifact_plan",
                "task_id": "task_1",
                "kind": "calculation_plan",
                "status": "ok",
                "payload": {"calculation_plan": {"status": "ok"}},
            },
            {
                "artifact_id": "artifact_result",
                "task_id": "task_1",
                "kind": "calculation_result",
                "status": "ok",
                "payload": {"calculation_result": {"status": "ok"}},
            },
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            [
                "missing_required_artifact_payload",
                "missing_required_artifact_payload",
                "missing_required_artifact_payload",
                "missing_required_evidence_ref",
            ],
        )
        self.assertEqual(
            [
                issue.get("payload_key")
                for issue in trace["integrity_issues"]
                if issue["type"] == "missing_required_artifact_payload"
            ],
            [
                "calculation_operands",
                "calculation_plan.operation",
                "calculation_result.rendered_value_or_answer_slots",
            ],
        )

    def test_run_marks_completed_reconciliation_without_result_artifact_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reconcile",
                "kind": "reconciliation",
                "label": "reconcile operands",
                "status": "completed",
                "artifact_ids": [],
            }
        ]
        final_state["artifacts"] = []
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["task_without_artifacts", "missing_required_artifact_kind"],
        )
        self.assertEqual(trace["integrity_issues"][1]["artifact_kind"], "reconciliation_result")

    def test_run_marks_reconciliation_result_without_status_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reconcile",
                "kind": "reconciliation",
                "label": "reconcile operands",
                "status": "completed",
                "artifact_ids": ["artifact_reconcile"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_reconcile",
                "task_id": "task_reconcile",
                "kind": "reconciliation_result",
                "status": "ok",
                "payload": {"reconciliation_result": {}},
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_artifact_payload")
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "reconciliation_result.status")

    def test_run_marks_ready_reconciliation_without_provenance_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reconcile",
                "kind": "reconciliation",
                "label": "reconcile operands",
                "status": "completed",
                "artifact_ids": ["artifact_reconcile"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_reconcile",
                "task_id": "task_reconcile",
                "kind": "reconciliation_result",
                "status": "ok",
                "payload": {"reconciliation_result": {"status": "ready", "matched_operands": []}},
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_evidence_ref")
        self.assertEqual(trace["integrity_issues"][0]["task_kind"], "reconciliation")

    def test_run_accepts_ready_reconciliation_with_candidate_provenance(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reconcile",
                "kind": "reconciliation",
                "label": "reconcile operands",
                "status": "completed",
                "artifact_ids": ["artifact_reconcile"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_reconcile",
                "task_id": "task_reconcile",
                "kind": "reconciliation_result",
                "status": "ok",
                "payload": {
                    "reconciliation_result": {
                        "status": "ready",
                        "matched_operands": [{"candidate_ids": ["ev_001"]}],
                    }
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])

    def test_run_marks_completed_retrieval_without_bundle_artifact_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_retrieve",
                "kind": "retrieval",
                "label": "retrieve evidence",
                "status": "completed",
                "artifact_ids": [],
            }
        ]
        final_state["artifacts"] = []
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["task_without_artifacts", "missing_required_artifact_kind", "missing_required_evidence_ref"],
        )
        self.assertEqual(trace["integrity_issues"][1]["artifact_kind"], "retrieval_bundle")

    def test_run_marks_empty_retrieval_bundle_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_retrieve",
                "kind": "retrieval",
                "label": "retrieve evidence",
                "status": "completed",
                "artifact_ids": ["artifact_retrieve"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_retrieve",
                "task_id": "task_retrieve",
                "kind": "retrieval_bundle",
                "status": "ok",
                "payload": {"retrieved_docs": []},
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["missing_required_artifact_payload", "missing_required_evidence_ref"],
        )
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "retrieval_bundle.items")

    def test_run_accepts_retrieval_bundle_with_chunk_provenance(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_retrieve",
                "kind": "retrieval",
                "label": "retrieve evidence",
                "status": "completed",
                "artifact_ids": ["artifact_retrieve"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_retrieve",
                "task_id": "task_retrieve",
                "kind": "retrieval_bundle",
                "status": "ok",
                "payload": {"retrieved_docs": [{"chunk_id": "chunk_001", "text": "supporting evidence"}]},
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])

    def test_run_marks_completed_synthesis_without_aggregated_answer_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_synthesis",
                "kind": "synthesis",
                "label": "final merge",
                "status": "completed",
                "artifact_ids": [],
            }
        ]
        final_state["artifacts"] = []
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["task_without_artifacts", "missing_required_artifact_kind", "missing_required_evidence_ref"],
        )
        self.assertEqual(trace["integrity_issues"][1]["artifact_kind"], "aggregated_answer")

    def test_run_marks_text_only_synthesis_answer_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_synthesis",
                "kind": "synthesis",
                "label": "final merge",
                "status": "completed",
                "artifact_ids": ["artifact_synthesis"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_synthesis",
                "task_id": "task_synthesis",
                "kind": "aggregated_answer",
                "status": "ok",
                "payload": {"final_answer": "최종 답변입니다."},
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["missing_required_artifact_payload", "missing_required_evidence_ref"],
        )
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "aggregated_answer.source_material")

    def test_run_accepts_synthesis_answer_with_source_and_evidence_refs(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_synthesis",
                "kind": "synthesis",
                "label": "final merge",
                "status": "completed",
                "artifact_ids": ["artifact_synthesis"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_synthesis",
                "task_id": "task_synthesis",
                "kind": "aggregated_answer",
                "status": "ok",
                "payload": {
                    "final_answer": "최종 답변입니다.",
                    "subtask_results": [{"task_id": "task_1", "answer": "근거 답변"}],
                },
                "evidence_refs": ["ev_001"],
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])

    def test_run_marks_completed_reflection_without_report_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reflection",
                "kind": "reflection",
                "label": "reflect retry",
                "status": "completed",
                "artifact_ids": [],
            }
        ]
        final_state["artifacts"] = []
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["task_without_artifacts", "missing_required_artifact_kind"],
        )
        self.assertEqual(trace["integrity_issues"][1]["artifact_kind"], "reflection_report")

    def test_run_accepts_reflection_report_handoff_without_evidence_refs(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reflection",
                "kind": "reflection",
                "label": "reflect retry",
                "status": "completed",
                "artifact_ids": ["artifact_reflection"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_reflection",
                "task_id": "task_reflection",
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
                    }
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])

    def test_run_marks_reflection_report_without_action_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reflection",
                "kind": "reflection",
                "label": "reflect retry",
                "status": "completed",
                "artifact_ids": ["artifact_reflection"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_reflection",
                "task_id": "task_reflection",
                "kind": "reflection_report",
                "status": "retry_prepared",
                "payload": {
                    "reflection_report": {
                        "outcome": "retry_prepared",
                        "budget_consumed": 1,
                    }
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_artifact_payload")
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "reflection_report.action_taken")

    def test_run_marks_completed_critic_without_report_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_critic",
                "kind": "critic",
                "label": "review outputs",
                "status": "completed",
                "artifact_ids": [],
            }
        ]
        final_state["artifacts"] = []
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["task_without_artifacts", "missing_required_artifact_kind", "missing_required_evidence_ref"],
        )
        self.assertEqual(trace["integrity_issues"][1]["artifact_kind"], "critic_report")

    def test_run_marks_critic_report_without_verdict_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_critic",
                "kind": "critic",
                "label": "review outputs",
                "status": "completed",
                "artifact_ids": ["artifact_critic"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_critic",
                "task_id": "task_critic",
                "kind": "critic_report",
                "status": "ok",
                "payload": {
                    "critic_report": {
                        "target_task_id": "task_synthesis",
                        "acceptance_reason": "grounded",
                    }
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_artifact_payload")
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "critic_report.verdict")

    def test_run_marks_critic_report_without_target_refs_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_critic",
                "kind": "critic",
                "label": "review outputs",
                "status": "completed",
                "artifact_ids": ["artifact_critic"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_critic",
                "task_id": "task_critic",
                "kind": "critic_report",
                "status": "ok",
                "payload": {
                    "critic_report": {
                        "passed": True,
                        "verdict": "passed",
                        "acceptance_reason": "grounded",
                    }
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_artifact_payload")
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "critic_report.target_refs")

    def test_run_marks_critic_report_without_reason_or_issues_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_critic",
                "kind": "critic",
                "label": "review outputs",
                "status": "completed",
                "artifact_ids": ["artifact_critic"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_critic",
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
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_artifact_payload")
        self.assertEqual(
            trace["integrity_issues"][0]["payload_key"],
            "critic_report.acceptance_reason_or_issues",
        )

    def test_run_accepts_critic_report_with_target_reason_and_provenance(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_critic",
                "kind": "critic",
                "label": "review outputs",
                "status": "completed",
                "artifact_ids": ["artifact_critic"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_critic",
                "task_id": "task_critic",
                "kind": "critic_report",
                "status": "ok",
                "payload": {
                    "critic_report": {
                        "passed": True,
                        "verdict": "passed",
                        "target_task_id": "task_synthesis",
                        "target_artifact_ids": ["artifact_synthesis"],
                        "acceptance_reason": "grounded",
                    }
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])

    def test_run_blocks_rejected_critic_report_even_with_high_score(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_1",
                "kind": "retrieval",
                "label": "retrieve evidence",
                "status": "completed",
                "artifact_ids": ["artifact_1"],
            },
            {
                "task_id": "task_critic",
                "kind": "critic",
                "label": "review outputs",
                "status": "completed",
                "artifact_ids": ["artifact_critic"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_1",
                "task_id": "task_1",
                "kind": "retrieval_bundle",
                "status": "ok",
                "payload": {"retrieval_bundle": {"retrieved_docs": [{"id": "doc_1"}]}},
                "evidence_refs": ["doc_1"],
            },
            {
                "artifact_id": "artifact_critic",
                "task_id": "task_critic",
                "kind": "critic_report",
                "status": "rejected",
                "payload": {
                    "critic_report": {
                        "passed": False,
                        "verdict": "rejected",
                        "target_task_id": "task_1",
                        "target_artifact_ids": ["artifact_1"],
                        "blocking_issues": ["missing evidence"],
                        "deterministic_score": 1.0,
                    }
                },
                "evidence_refs": ["artifact_1"],
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "critic_report_rejected")
        self.assertEqual(
            trace["integrity_issues"][0]["runtime_acceptance_status"],
            "blocked",
        )
        self.assertIn("critic_rejected", trace["integrity_issues"][0]["reasons"])
        self.assertEqual(trace["integrity_issues"][0]["target_task_ids"], ["task_1"])
        self.assertEqual(
            trace["integrity_issues"][0]["target_artifact_ids"],
            ["artifact_1"],
        )

    def test_run_keeps_orphan_artifact_warning_non_blocking_when_not_final_source(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_review",
                "kind": "verification",
                "label": "review",
                "status": "completed",
                "artifact_ids": ["artifact_review"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_review",
                "task_id": "task_review",
                "kind": "semantic_plan",
                "status": "ok",
                "payload": {"status": "ok"},
            },
            {
                "artifact_id": "artifact_orphan",
                "task_id": "missing_task",
                "kind": "semantic_plan",
                "status": "ok",
                "payload": {"status": "ok"},
            },
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "warning")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["orphan_artifact"],
        )

    def test_run_promotes_final_source_orphan_artifact_warning_to_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_synthesis",
                "kind": "synthesis",
                "label": "final merge",
                "status": "completed",
                "artifact_ids": ["artifact_synthesis"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_synthesis",
                "task_id": "task_synthesis",
                "kind": "aggregated_answer",
                "status": "ok",
                "payload": {
                    "final_answer": "최종 답변입니다.",
                    "source_artifact_ids": ["artifact_orphan"],
                },
                "evidence_refs": ["artifact_orphan"],
            },
            {
                "artifact_id": "artifact_orphan",
                "task_id": "missing_task",
                "kind": "semantic_plan",
                "status": "ok",
                "payload": {"status": "ok"},
            },
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["orphan_artifact", "final_source_orphan_artifact"],
        )
        self.assertEqual(trace["integrity_issues"][1]["artifact_id"], "artifact_orphan")

    def test_run_promotes_final_source_task_without_artifacts_warning_to_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_source",
                "kind": "verification",
                "label": "source review",
                "status": "completed",
                "artifact_ids": [],
            },
            {
                "task_id": "task_synthesis",
                "kind": "synthesis",
                "label": "final merge",
                "status": "completed",
                "artifact_ids": ["artifact_synthesis"],
            },
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_synthesis",
                "task_id": "task_synthesis",
                "kind": "aggregated_answer",
                "status": "ok",
                "payload": {
                    "final_answer": "최종 답변입니다.",
                    "source_task_ids": ["task_source"],
                },
                "evidence_refs": ["ev_001"],
            },
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["task_without_artifacts", "final_source_task_without_artifacts"],
        )
        self.assertEqual(trace["integrity_issues"][1]["task_id"], "task_source")


if __name__ == "__main__":
    unittest.main()
