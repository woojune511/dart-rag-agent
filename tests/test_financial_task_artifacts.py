from __future__ import annotations

import unittest

from src.agent.financial_task_artifacts import (
    calculation_plan_artifact_update,
    calculation_result_artifact_update,
    operand_set_artifact_update,
    project_task_artifact_trace,
)


class FinancialTaskArtifactTests(unittest.TestCase):
    def _operand_update(self):
        operands = [
            {
                "operand_id": "cand_a",
                "evidence_id": "cand_a",
                "normalized_value": 10.0,
                "normalized_unit": "COUNT",
            }
        ]
        return operand_set_artifact_update(
            tasks=[],
            artifacts=[],
            task_id="task_1",
            task_label="semantic outputs",
            query="return the value",
            metric_family="semantic_program",
            operand_rows=operands,
            status="sufficient",
            summary="one grounded operand",
            payload={"calculation_operands": operands},
            evidence_refs=["cand_a"],
        )

    def test_semantic_program_artifacts_preserve_order_and_candidate_refs(self) -> None:
        operand_update = self._operand_update()
        plan_update = calculation_plan_artifact_update(
            tasks=operand_update["tasks"],
            artifacts=operand_update["artifacts"],
            task_id="task_1",
            task_label="semantic outputs",
            query="return the value",
            metric_family="semantic_program",
            calculation_plan={
                "status": "ok",
                "mode": "semantic_program",
                "operation": "semantic_program",
                "semantic_program": {"status": "ready"},
            },
        )
        result_update = calculation_result_artifact_update(
            tasks=plan_update["tasks"],
            artifacts=plan_update["artifacts"],
            task_id="task_1",
            task_label="semantic outputs",
            query="return the value",
            metric_family="semantic_program",
            calculation_result={
                "status": "ok",
                "semantic_status": "ok",
                "ledger_integrity_status": "ok",
                "rendered_value": "10 items",
            },
            evidence_refs=["cand_a"],
        )
        self.assertEqual(
            [artifact["kind"] for artifact in result_update["artifacts"]],
            ["operand_set", "calculation_plan", "calculation_result"],
        )
        self.assertEqual(result_update["tasks"][0]["status"], "completed")
        self.assertEqual(result_update["artifacts"][-1]["evidence_refs"], ["cand_a"])
        trace = project_task_artifact_trace(result_update["tasks"], result_update["artifacts"])
        self.assertEqual(trace["integrity_status"], "ok")

    def test_partial_semantics_and_ledger_integrity_are_independent(self) -> None:
        operand_update = self._operand_update()
        plan_update = calculation_plan_artifact_update(
            tasks=operand_update["tasks"],
            artifacts=operand_update["artifacts"],
            task_id="task_1",
            task_label="semantic outputs",
            query="return the value and explanation",
            metric_family="semantic_program",
            calculation_plan={
                "status": "ok",
                "mode": "semantic_program",
                "operation": "semantic_program",
            },
        )
        result_update = calculation_result_artifact_update(
            tasks=plan_update["tasks"],
            artifacts=plan_update["artifacts"],
            task_id="task_1",
            task_label="semantic outputs",
            query="return the value and explanation",
            metric_family="semantic_program",
            calculation_result={
                "status": "insufficient_operands",
                "semantic_status": "partial",
                "ledger_integrity_status": "ok",
                "rendered_value": "10 items",
                "derived_metrics": {"missing_obligation_ids": ["ob_note"]},
            },
            evidence_refs=["cand_a"],
        )
        self.assertEqual(result_update["tasks"][0]["status"], "completed")
        self.assertEqual(result_update["artifacts"][-1]["status"], "partial")
        trace = project_task_artifact_trace(result_update["tasks"], result_update["artifacts"])
        self.assertEqual(trace["integrity_status"], "ok")

    def test_incomplete_semantics_with_empty_operand_payload_keeps_ledger_structurally_valid(self) -> None:
        operand_update = operand_set_artifact_update(
            tasks=[],
            artifacts=[],
            task_id="task_1",
            task_label="semantic outputs",
            query="return the unavailable value",
            metric_family="semantic_program",
            operand_rows=[],
            status="partial",
            summary="zero grounded operands",
            payload={
                "calculation_operands": [],
                "semantic_status": "invalid",
                "missing_obligation_ids": ["ob_001"],
            },
            evidence_refs=[],
        )
        plan_update = calculation_plan_artifact_update(
            tasks=operand_update["tasks"],
            artifacts=operand_update["artifacts"],
            task_id="task_1",
            task_label="semantic outputs",
            query="return the unavailable value",
            metric_family="semantic_program",
            calculation_plan={
                "status": "incomplete",
                "mode": "semantic_program",
                "operation": "semantic_program",
            },
        )
        result_update = calculation_result_artifact_update(
            tasks=plan_update["tasks"],
            artifacts=plan_update["artifacts"],
            task_id="task_1",
            task_label="semantic outputs",
            query="return the unavailable value",
            metric_family="semantic_program",
            calculation_result={
                "status": "insufficient_operands",
                "semantic_status": "incomplete",
                "ledger_integrity_status": "ok",
                "formatted_result": "required evidence is missing",
                "answer_slots": {},
                "source_row_ids": [],
                "derived_metrics": {
                    "semantic_outputs": [],
                    "missing_obligation_ids": ["ob_001"],
                },
            },
            evidence_refs=[],
        )
        trace = project_task_artifact_trace(
            result_update["tasks"],
            result_update["artifacts"],
        )
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])


if __name__ == "__main__":
    unittest.main()
