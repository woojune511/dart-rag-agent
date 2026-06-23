import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops import mas_analyst_smoke
from src.ops import debug_math_workflow as debug_math
from src.ops import debug_reference_note_workflow as debug_reference
from src.ops import replay_full_eval_from_results as replay_eval
from src.ops import retrospective_evaluator_ablation_eval as ablation_eval
from src.ops import retrospective_ontology_retrieval_eval as ontology_eval
from src.ops import retrospective_operand_grounding_eval as operand_eval


class OpsRuntimeProjectionModeTests(unittest.TestCase):
    def _ontology_fake_agent(self, calculation_update):
        class FakeAgent:
            def _classify_query(self, state):
                return {"query_type": "numeric_fact", "intent": "numeric_fact"}

            def _extract_entities(self, state):
                return {}

            def _retrieve(self, state):
                return {"retrieved_docs": [], "seed_retrieved_docs": []}

            def _expand_via_structure_graph(self, state):
                return {}

            def _extract_evidence(self, state):
                return {"evidence_items": []}

            def _extract_ratio_row_candidates(self, docs, query, topic):
                return []

            def _extract_ratio_component_candidates(self, docs, query, topic):
                return []

            def _extract_calculation_operands(self, state):
                return {}

            def _plan_formula_calculation(self, state):
                return {}

            def _execute_calculation(self, state):
                return dict(calculation_update)

        return FakeAgent()

    def test_debug_math_workflow_rejects_legacy_top_level_runtime_projection(self) -> None:
        agent = self._ontology_fake_agent(
            {
                "calculation_operands": [{"label": "legacy", "value": "999"}],
                "calculation_plan": {"status": "legacy"},
                "calculation_result": {"status": "ok", "rendered_value": "999"},
                "resolved_calculation_trace": {},
                "structured_result": {},
            }
        )

        result = debug_math.debug_question(agent, "question")

        self.assertEqual(result["resolved_calculation_trace"], {})
        self.assertEqual(result["structured_result"], {})
        self.assertEqual(result["calculation_operands"], None)
        self.assertEqual(result["calculation_plan"], None)
        self.assertEqual(result["calculation_result"], None)
        self.assertNotIn("999", str(result["structured_result"]))

    def test_debug_math_workflow_uses_canonical_runtime_projection(self) -> None:
        agent = self._ontology_fake_agent(
            {
                "calculation_operands": [{"label": "stale", "value": "999"}],
                "calculation_plan": {"status": "stale"},
                "calculation_result": {"status": "stale", "rendered_value": "999"},
                "resolved_calculation_trace": {
                    "calculation_operands": [{"label": "fresh", "value": "123"}],
                    "calculation_plan": {"status": "ok", "operation": "lookup"},
                    "calculation_result": {"status": "ok", "rendered_value": "123"},
                },
            }
        )

        result = debug_math.debug_question(agent, "question")

        self.assertEqual(result["calculation_operands"], [{"label": "fresh", "value": "123"}])
        self.assertEqual(result["calculation_plan"]["operation"], "lookup")
        self.assertEqual(result["calculation_result"]["rendered_value"], "123")
        self.assertEqual(result["structured_result"]["rendered_value"], "123")
        self.assertNotIn("999", str(result["resolved_calculation_trace"]))

    def test_debug_math_workflow_projects_calculation_debug_under_debug_traces(self) -> None:
        agent = self._ontology_fake_agent(
            {
                "calculation_debug_trace": {
                    "source": "structured_row_direct",
                    "coverage": "sufficient",
                },
                "resolved_calculation_trace": {},
                "structured_result": {},
            }
        )

        result = debug_math.debug_question(agent, "question")

        self.assertEqual(
            result["debug_traces"]["calculation"],
            {"source": "structured_row_direct", "coverage": "sufficient"},
        )
        self.assertNotIn("calculation_debug_trace", result)

    def test_debug_reference_graph_smoke_rejects_legacy_top_level_runtime_projection(self) -> None:
        class FakeAgent:
            def _classify_query(self, state):
                return {"intent": "qa"}

            def _extract_entities(self, state):
                return {}

            def _retrieve(self, state):
                return {"retrieved_docs": []}

            def _expand_via_structure_graph(self, state):
                return {"retrieved_docs": []}

            def run(self, query):
                return {
                    "answer": "answer",
                    "citations": [],
                    "calculation_operands": [{"label": "legacy", "value": "999"}],
                    "calculation_plan": {"status": "legacy"},
                    "calculation_result": {"status": "ok", "rendered_value": "999"},
                    "resolved_calculation_trace": {},
                    "structured_result": {},
                }

        result = debug_reference._graph_smoke(FakeAgent(), "question")

        self.assertEqual(result["resolved_calculation_trace"], {})
        self.assertEqual(result["structured_result"], {})

    def test_debug_reference_graph_smoke_uses_canonical_runtime_projection(self) -> None:
        class FakeAgent:
            def _classify_query(self, state):
                return {"intent": "qa"}

            def _extract_entities(self, state):
                return {}

            def _retrieve(self, state):
                return {"retrieved_docs": []}

            def _expand_via_structure_graph(self, state):
                return {"retrieved_docs": []}

            def run(self, query):
                return {
                    "answer": "answer",
                    "citations": [],
                    "calculation_operands": [{"label": "stale", "value": "999"}],
                    "calculation_plan": {"status": "stale"},
                    "calculation_result": {"status": "stale", "rendered_value": "999"},
                    "resolved_calculation_trace": {
                        "calculation_operands": [{"label": "fresh", "value": "123"}],
                        "calculation_plan": {"status": "ok", "operation": "lookup"},
                        "calculation_result": {"status": "ok", "rendered_value": "123"},
                    },
                }

        result = debug_reference._graph_smoke(FakeAgent(), "question")

        self.assertEqual(
            result["resolved_calculation_trace"]["calculation_operands"],
            [{"label": "fresh", "value": "123"}],
        )
        self.assertEqual(result["structured_result"]["rendered_value"], "123")
        self.assertNotIn("999", str(result["resolved_calculation_trace"]))

    def test_mas_smoke_direct_reader_requires_explicit_legacy_opt_in(self) -> None:
        legacy_payload = {
            "calculation_operands": [{"label": "legacy", "value": "999"}],
            "calculation_plan": {"mode": "legacy"},
            "calculation_result": {"status": "ok", "value": 999},
            "resolved_calculation_trace": {},
        }
        final_state = {
            "artifacts": {
                "task_1": {
                    "content": dict(legacy_payload),
                }
            }
        }

        self.assertEqual(mas_analyst_smoke._operand_count(legacy_payload), 0)
        self.assertEqual(mas_analyst_smoke._calc_payload(legacy_payload), {})
        self.assertEqual(
            mas_analyst_smoke._operand_count(legacy_payload, allow_legacy_top_level=True),
            1,
        )
        self.assertEqual(
            mas_analyst_smoke._calc_payload(legacy_payload, allow_legacy_top_level=True)["value"],
            999,
        )
        self.assertEqual(mas_analyst_smoke._artifact_operand_count(final_state), 0)
        self.assertEqual(mas_analyst_smoke._artifact_calc_payload(final_state), {})
        self.assertEqual(mas_analyst_smoke._artifact_calc_status(final_state), "")

    def test_mas_smoke_artifact_reader_prefers_canonical_trace_over_stale_top_level_payload(self) -> None:
        final_state = {
            "artifacts": {
                "task_1": {
                    "content": {
                        "calculation_operands": [{"label": "stale", "value": "999"}],
                        "calculation_plan": {"mode": "stale"},
                        "calculation_result": {"status": "stale", "rendered_value": "999"},
                        "resolved_calculation_trace": {
                            "calculation_operands": [{"label": "fresh", "value": "123"}],
                            "calculation_plan": {"status": "ok", "operation": "lookup"},
                            "calculation_result": {"status": "ok", "rendered_value": "123"},
                        },
                    },
                }
            }
        }

        self.assertEqual(mas_analyst_smoke._artifact_operand_count(final_state), 1)
        self.assertEqual(mas_analyst_smoke._artifact_calc_status(final_state), "ok")
        self.assertEqual(mas_analyst_smoke._artifact_calc_payload(final_state)["rendered_value"], "123")
        self.assertNotIn("999", str(mas_analyst_smoke._artifact_calc_payload(final_state)))

    def test_retrospective_ontology_rerun_rejects_legacy_top_level_runtime_projection(self) -> None:
        captured = {}
        agent = self._ontology_fake_agent(
            {
                "calculation_operands": [{"label": "legacy", "value": "999"}],
                "calculation_plan": {"status": "legacy"},
                "calculation_result": {"status": "ok", "rendered_value": "999"},
                "resolved_calculation_trace": {},
                "structured_result": {},
            }
        )
        example = SimpleNamespace(id="Q1", question="question")

        def fake_grounding_score(*, runtime_evidence, contexts, calculation_operands):
            captured["operands"] = list(calculation_operands)
            return None, {}

        with patch.object(ontology_eval, "_compute_retrieval_hit_at_k", return_value=0.0):
            with patch.object(ontology_eval, "_compute_section_match_rate", return_value=0.0):
                with patch.object(ontology_eval, "_compute_operand_grounding_score", side_effect=fake_grounding_score):
                    outcome = ontology_eval._run_question(agent, example)

        self.assertEqual(captured["operands"], [])
        self.assertEqual(outcome.operand_count, 0)
        self.assertEqual(outcome.calc_status, "")
        self.assertEqual(outcome.rendered_value, "")

    def test_retrospective_ontology_rerun_uses_canonical_runtime_projection(self) -> None:
        captured = {}
        agent = self._ontology_fake_agent(
            {
                "calculation_operands": [{"label": "stale", "value": "999"}],
                "calculation_plan": {"status": "stale"},
                "calculation_result": {"status": "stale", "rendered_value": "999"},
                "resolved_calculation_trace": {
                    "calculation_operands": [{"label": "fresh", "value": "123"}],
                    "calculation_plan": {"status": "ok", "operation": "lookup"},
                    "calculation_result": {"status": "ok", "rendered_value": "123"},
                },
            }
        )
        example = SimpleNamespace(id="Q1", question="question")

        def fake_grounding_score(*, runtime_evidence, contexts, calculation_operands):
            captured["operands"] = list(calculation_operands)
            return 1.0, {}

        with patch.object(ontology_eval, "_compute_retrieval_hit_at_k", return_value=0.0):
            with patch.object(ontology_eval, "_compute_section_match_rate", return_value=0.0):
                with patch.object(ontology_eval, "_compute_operand_grounding_score", side_effect=fake_grounding_score):
                    outcome = ontology_eval._run_question(agent, example)

        self.assertEqual(captured["operands"], [{"label": "fresh", "value": "123"}])
        self.assertEqual(outcome.operand_count, 1)
        self.assertEqual(outcome.calc_status, "ok")
        self.assertEqual(outcome.rendered_value, "123")
        self.assertNotIn("999", str(captured))

    def test_retrospective_operand_grounding_reader_accepts_historical_top_level_rows(self) -> None:
        captured = {}

        def fake_grounding_score(*, runtime_evidence, contexts, calculation_operands):
            captured["operands"] = list(calculation_operands)
            return 1.0, {"reason": "captured"}

        row = {
            "calculation_operands": [{"label": "legacy", "value": "999"}],
            "calculation_plan": {"mode": "legacy"},
            "calculation_result": {"status": "ok", "value": 999},
            "resolved_calculation_trace": {},
            "numeric_equivalence": 1.0,
            "numeric_grounding": 1.0,
        }

        with patch.object(operand_eval, "_compute_operand_grounding_score", side_effect=fake_grounding_score):
            with patch.object(operand_eval, "_resolve_numeric_judgement", return_value=("PASS", 1.0)):
                result = operand_eval._compute_new_judgement(row)

        self.assertEqual(captured["operands"], [{"label": "legacy", "value": "999"}])
        self.assertEqual(result["numeric_final_judgement"], "PASS")

    def test_retrospective_operand_grounding_prefers_canonical_trace_over_stale_top_level_rows(self) -> None:
        captured = {}

        def fake_grounding_score(*, runtime_evidence, contexts, calculation_operands):
            captured["operands"] = list(calculation_operands)
            return 1.0, {"reason": "captured"}

        row = {
            "calculation_operands": [{"label": "stale", "value": "999"}],
            "calculation_plan": {"mode": "stale"},
            "calculation_result": {"status": "stale", "value": 999},
            "resolved_calculation_trace": {
                "calculation_operands": [{"label": "fresh", "value": "123"}],
                "calculation_plan": {"status": "ok", "operation": "lookup"},
                "calculation_result": {"status": "ok", "rendered_value": "123"},
            },
            "numeric_equivalence": 1.0,
            "numeric_grounding": 1.0,
        }

        with patch.object(operand_eval, "_compute_operand_grounding_score", side_effect=fake_grounding_score):
            with patch.object(operand_eval, "_resolve_numeric_judgement", return_value=("PASS", 1.0)):
                result = operand_eval._compute_new_judgement(row)

        self.assertEqual(captured["operands"], [{"label": "fresh", "value": "123"}])
        self.assertEqual(result["numeric_final_judgement"], "PASS")

    def test_retrospective_ablation_reader_accepts_historical_top_level_rows(self) -> None:
        captured = {}

        def fake_operand_selection(*, example, calculation_operands):
            captured["operands"] = list(calculation_operands)
            return 1.0

        case = ablation_eval.AblationCase(
            decision_id="75",
            question_id="q1",
            title="test",
            note="test",
        )
        row = {
            "answer": "legacy answer",
            "calculation_operands": [{"label": "legacy", "value": "999"}],
            "calculation_plan": {"mode": "legacy"},
            "calculation_result": {"status": "ok", "value": 999},
            "resolved_calculation_trace": {},
        }
        example = SimpleNamespace(expected_operands=[], evidence=[])

        with patch.object(ablation_eval, "_compute_operand_selection_correctness", side_effect=fake_operand_selection):
            result = ablation_eval._score_case(case, row, example)

        self.assertEqual(captured["operands"], [{"label": "legacy", "value": "999"}])
        self.assertEqual(result["proposed_label"], "current_label_match")
        self.assertEqual(result["proposed_value"], 1.0)

    def test_retrospective_ablation_prefers_canonical_trace_operands_over_stale_top_level_rows(self) -> None:
        captured = {}

        def fake_operand_selection(*, example, calculation_operands):
            captured["operands"] = list(calculation_operands)
            return 1.0

        case = ablation_eval.AblationCase(
            decision_id="75",
            question_id="q1",
            title="test",
            note="test",
        )
        row = {
            "answer": "answer",
            "calculation_operands": [{"label": "stale", "value": "999"}],
            "calculation_plan": {"mode": "stale"},
            "calculation_result": {"status": "stale", "rendered_value": "999"},
            "resolved_calculation_trace": {
                "calculation_operands": [{"label": "fresh", "value": "123"}],
                "calculation_plan": {"status": "ok", "operation": "lookup"},
                "calculation_result": {"status": "ok", "rendered_value": "123"},
            },
        }
        example = SimpleNamespace(expected_operands=[], evidence=[])

        with patch.object(ablation_eval, "_compute_operand_selection_correctness", side_effect=fake_operand_selection):
            result = ablation_eval._score_case(case, row, example)

        self.assertEqual(captured["operands"], [{"label": "fresh", "value": "123"}])
        self.assertEqual(result["proposed_label"], "current_label_match")
        self.assertEqual(result["proposed_value"], 1.0)
        self.assertNotIn("999", str(captured))

    def test_retrospective_ablation_prefers_canonical_trace_result_over_stale_top_level_rows(self) -> None:
        captured = {}

        def fake_numeric_result(*, example, calculation_result):
            captured["calculation_result"] = dict(calculation_result)
            return 1.0

        def fake_operand_selection(*, example, calculation_operands):
            captured["operands"] = list(calculation_operands)
            return 0.5

        case = ablation_eval.AblationCase(
            decision_id="76",
            question_id="q1",
            title="test",
            note="test",
        )
        row = {
            "answer": "answer",
            "calculation_operands": [{"label": "stale", "value": "999"}],
            "calculation_plan": {"mode": "stale"},
            "calculation_result": {"status": "stale", "rendered_value": "999"},
            "resolved_calculation_trace": {
                "calculation_operands": [{"label": "fresh", "value": "123"}],
                "calculation_plan": {"status": "ok", "operation": "lookup"},
                "calculation_result": {"status": "ok", "rendered_value": "123"},
            },
            "numeric_grounding": 1.0,
        }
        example = SimpleNamespace(expected_operands=[], evidence=[])

        with patch.object(ablation_eval, "_compute_numeric_result_correctness", side_effect=fake_numeric_result):
            with patch.object(ablation_eval, "_compute_operand_selection_correctness", side_effect=fake_operand_selection):
                result = ablation_eval._score_case(case, row, example)

        self.assertEqual(captured["operands"], [{"label": "fresh", "value": "123"}])
        self.assertEqual(captured["calculation_result"]["rendered_value"], "123")
        self.assertEqual(result["baseline_label"], "before_operand_override")
        self.assertEqual(result["proposed_value"], 1.0)
        self.assertNotIn("999", str(captured))

    def test_replay_reader_accepts_historical_top_level_rows(self) -> None:
        captured = {}

        def fake_grounding_score(*, runtime_evidence, contexts, calculation_operands):
            captured["operands"] = list(calculation_operands)
            return 1.0, {"reason": "captured"}

        def fake_operand_selection(*, example, calculation_operands):
            captured["operand_selection"] = list(calculation_operands)
            return 1.0

        def fake_numeric_result(*, example, calculation_result):
            captured["calculation_result"] = dict(calculation_result)
            return 1.0

        row = {
            "id": "Q1",
            "answer": "answer",
            "calculation_operands": [{"label": "legacy", "value": "999"}],
            "calculation_plan": {"mode": "legacy"},
            "calculation_result": {"status": "ok", "rendered_value": "999"},
            "resolved_calculation_trace": {},
            "numeric_grounding": 1.0,
        }
        example = SimpleNamespace(canonical_answer_key="answer", evidence=[])

        with patch.object(replay_eval, "_compute_numeric_equivalence", return_value=(1.0, {})):
            with patch.object(replay_eval, "_compute_operand_grounding_score", side_effect=fake_grounding_score):
                with patch.object(replay_eval, "_compute_numeric_result_correctness", side_effect=fake_numeric_result):
                    with patch.object(replay_eval, "_compute_operand_selection_correctness", side_effect=fake_operand_selection):
                        with patch.object(replay_eval, "_compute_unit_consistency_pass", return_value=1.0):
                            with patch.object(replay_eval, "_compute_calculation_correctness", return_value=1.0):
                                with patch.object(replay_eval, "_resolve_numeric_judgement", return_value=("PASS", 1.0)):
                                    result = replay_eval._score_row(row, {"Q1": example})

        self.assertEqual(captured["operands"], [{"label": "legacy", "value": "999"}])
        self.assertEqual(captured["operand_selection"], [{"label": "legacy", "value": "999"}])
        self.assertEqual(captured["calculation_result"]["rendered_value"], "999")
        self.assertEqual(result["numeric_final_judgement"], "PASS")
        self.assertNotIn("source_calculation_operands_missing", result["source_warnings"])

    def test_replay_reader_prefers_canonical_trace_over_stale_top_level_rows(self) -> None:
        captured = {}

        def fake_grounding_score(*, runtime_evidence, contexts, calculation_operands):
            captured["operands"] = list(calculation_operands)
            return 1.0, {"reason": "captured"}

        def fake_operand_selection(*, example, calculation_operands):
            captured["operand_selection"] = list(calculation_operands)
            return 1.0

        def fake_numeric_result(*, example, calculation_result):
            captured["calculation_result"] = dict(calculation_result)
            return 1.0

        row = {
            "id": "Q1",
            "answer": "answer",
            "calculation_operands": [{"label": "stale", "value": "999"}],
            "calculation_plan": {"mode": "stale"},
            "calculation_result": {"status": "stale", "rendered_value": "999"},
            "resolved_calculation_trace": {
                "calculation_operands": [{"label": "fresh", "value": "123"}],
                "calculation_plan": {"status": "ok", "operation": "lookup"},
                "calculation_result": {"status": "ok", "rendered_value": "123"},
            },
            "numeric_grounding": 1.0,
        }
        example = SimpleNamespace(canonical_answer_key="answer", evidence=[])

        with patch.object(replay_eval, "_compute_numeric_equivalence", return_value=(1.0, {})):
            with patch.object(replay_eval, "_compute_operand_grounding_score", side_effect=fake_grounding_score):
                with patch.object(replay_eval, "_compute_numeric_result_correctness", side_effect=fake_numeric_result):
                    with patch.object(replay_eval, "_compute_operand_selection_correctness", side_effect=fake_operand_selection):
                        with patch.object(replay_eval, "_compute_unit_consistency_pass", return_value=1.0):
                            with patch.object(replay_eval, "_compute_calculation_correctness", return_value=1.0):
                                with patch.object(replay_eval, "_resolve_numeric_judgement", return_value=("PASS", 1.0)):
                                    result = replay_eval._score_row(row, {"Q1": example})

        self.assertEqual(captured["operands"], [{"label": "fresh", "value": "123"}])
        self.assertEqual(captured["operand_selection"], [{"label": "fresh", "value": "123"}])
        self.assertEqual(captured["calculation_result"]["rendered_value"], "123")
        self.assertEqual(result["numeric_final_judgement"], "PASS")
        self.assertNotIn("999", str(captured))


if __name__ == "__main__":
    unittest.main()
