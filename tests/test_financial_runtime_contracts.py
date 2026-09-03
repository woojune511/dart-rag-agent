from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program,
    validate_semantic_calculation_program,
)
from src.agent.financial_reconciliation_candidates import (
    semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_graph import (
    FINANCIAL_GRAPH_PHASE_WRITERS,
    FinancialAgent,
    project_financial_phase_state,
)
from src.agent.financial_runtime_contracts import (
    CandidateVisibilityV1,
    CompilationEnvelopeV1,
)


def _scope(*, period: str = "") -> dict:
    return {
        "company": "",
        "period": period,
        "consolidation_scope": "unknown",
        "segment": "",
        "basis": "",
    }


def _obligation(obligation_id: str) -> dict:
    return {
        "obligation_id": obligation_id,
        "kind": "direct_value",
        "label": "reported value",
        "required": True,
        "display_unit": "",
        "display_format": "",
        "scope": _scope(),
        "retrieval_hints": [],
        "concept_hints": [],
        "evidence_requirements": [],
        "depends_on": [],
        "coupling_key": "",
    }


def _candidate(candidate_id: str, value: float, *, context: str = "table-a") -> dict:
    return {
        "candidate_id": candidate_id,
        "kind": "numeric",
        "source_candidate_id": f"source-{candidate_id}",
        "evidence_id": f"evidence-{candidate_id}",
        "source_anchor": "[sample | section]",
        "source_row_id": f"row-{candidate_id}",
        "table_source_id": context,
        "row_label": "reported value",
        "statement_type": "",
        "company": "",
        "year": 2024,
        "consolidation_scope": "unknown",
        "segment": "",
        "basis": "",
        "context_fingerprint": context,
        "source_text": f"reported value {value}",
        "candidate_kind": "structured_value",
        "raw_value": str(value),
        "raw_unit": "items",
        "normalized_value": float(value),
        "normalized_unit": "COUNT",
        "period": "",
        "column_headers": [],
        "value_role": "",
        "aggregation_stage": "",
        "aggregate_label": "",
    }


class FinancialRuntimeContractTests(unittest.TestCase):
    def _visibility(self, catalog: list[dict], owner_ids: list[str]):
        return CandidateVisibilityV1.create(
            catalog_fingerprint=semantic_candidate_catalog_fingerprint(catalog),
            visible_candidate_ids=[
                str(item["candidate_id"]) for item in catalog
            ],
            candidate_ids_by_owner={"ob_value": owner_ids},
        )

    def test_owner_visibility_is_preserved_by_executor(self) -> None:
        obligations = [_obligation("ob_value")]
        catalog = [_candidate("cand-visible", 10), _candidate("cand-hidden", 20)]
        program = {
            "status": "ready",
            "direct_bindings": [
                {"obligation_id": "ob_value", "candidate_id": "cand-hidden"}
            ],
        }
        visibility = self._visibility(catalog, ["cand-visible"])
        validation = validate_semantic_calculation_program(
            program=program,
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return the reported value.",
            candidate_visibility=visibility,
        )
        envelope = CompilationEnvelopeV1.create(
            visibility=visibility,
            program=program,
            validation=validation,
        )

        execution = execute_semantic_calculation_program(
            program=program,
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return the reported value.",
            compilation_envelope=envelope,
        )

        self.assertEqual(execution["status"], "incomplete")
        self.assertIn(
            "candidate_not_exposed_to_compiler",
            {item["code"] for item in execution["validation"]["errors"]},
        )
        self.assertEqual(execution["selected_candidate_ids"], [])

    def test_catalog_fingerprint_drift_fails_before_execution(self) -> None:
        obligations = [_obligation("ob_value")]
        catalog = [_candidate("cand-visible", 10)]
        program = {
            "status": "ready",
            "direct_bindings": [
                {"obligation_id": "ob_value", "candidate_id": "cand-visible"}
            ],
        }
        visibility = self._visibility(catalog, ["cand-visible"])
        validation = validate_semantic_calculation_program(
            program=program,
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return the reported value.",
            candidate_visibility=visibility,
        )
        envelope = CompilationEnvelopeV1.create(
            visibility=visibility,
            program=program,
            validation=validation,
        )
        changed_catalog = [{**catalog[0], "raw_value": "11"}]

        execution = execute_semantic_calculation_program(
            program=program,
            obligations=obligations,
            candidate_catalog=changed_catalog,
            query="Return the reported value.",
            compilation_envelope=envelope,
        )

        self.assertEqual(execution["outputs"], [])
        self.assertIn(
            "visibility_mismatch",
            {item["code"] for item in execution["validation"]["errors"]},
        )

    def test_program_or_validation_drift_fails_closed(self) -> None:
        obligations = [_obligation("ob_value")]
        catalog = [_candidate("cand-visible", 10)]
        program = {
            "status": "ready",
            "direct_bindings": [
                {"obligation_id": "ob_value", "candidate_id": "cand-visible"}
            ],
        }
        visibility = self._visibility(catalog, ["cand-visible"])
        validation = validate_semantic_calculation_program(
            program=program,
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return the reported value.",
            candidate_visibility=visibility,
        )
        envelope = CompilationEnvelopeV1.create(
            visibility=visibility,
            program=program,
            validation=validation,
        )

        execution = execute_semantic_calculation_program(
            program={**program, "rationale": "changed after validation"},
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return the reported value.",
            compilation_envelope=envelope,
        )

        self.assertEqual(execution["outputs"], [])
        self.assertIn(
            "validation_drift",
            {item["code"] for item in execution["validation"]["errors"]},
        )

    def test_one_derived_obligation_may_use_multiple_period_contexts(self) -> None:
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "semantic_program_contract_residuals.json"
        )
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        case = fixture["expression_compatibility"]["cases"][0]
        obligations = [
            {**dict(case["obligations"][0]), "coupling_key": "reported-series"}
        ]

        validation = validate_semantic_calculation_program(
            program=case["program"],
            obligations=obligations,
            candidate_catalog=case["candidate_catalog"],
            query=case["query"],
        )

        self.assertEqual(validation["status"], "ready")
        self.assertNotIn(
            "coupled_context_mismatch",
            {item["code"] for item in validation["errors"]},
        )

    def test_visibility_copies_mutable_inputs(self) -> None:
        catalog = [_candidate("cand-visible", 10)]
        visible_ids = ["cand-visible"]
        owner_map = {"ob_value": ["cand-visible"]}
        visibility = CandidateVisibilityV1.create(
            catalog_fingerprint=semantic_candidate_catalog_fingerprint(catalog),
            visible_candidate_ids=visible_ids,
            candidate_ids_by_owner=owner_map,
        )
        visible_ids.append("cand-late")
        owner_map["ob_value"].append("cand-late")

        self.assertEqual(visibility.visible_candidate_ids, ("cand-visible",))
        self.assertEqual(
            visibility.candidate_ids_by_owner(),
            {"ob_value": ["cand-visible"]},
        )

    def test_phase_projection_and_single_writer_ledger_are_deterministic(self) -> None:
        state = {
            "request": {"query": "return value", "report_scope": {}},
            "requirements": {
                "semantic_plan": {
                    "status": "ok",
                    "program_required": True,
                    "tasks": [
                        {
                            "task_id": "task_1",
                            "metric_family": "semantic_program",
                            "metric_label": "value",
                            "query": "return value",
                            "constraints": {},
                        }
                    ],
                },
                "retrieval_queries": ["return value"],
                "active_subtask": {
                    "task_id": "task_1",
                    "metric_family": "semantic_program",
                    "metric_label": "value",
                    "query": "return value",
                },
                "planner_feedback": "",
            },
            "numeric_result": {
                "answer": "value: 10 items",
                "selected_claim_ids": ["cand-visible"],
                "kept_claim_ids": ["cand-visible"],
                "structured_result": {
                    "status": "ok",
                    "answer": "value: 10 items",
                },
                "resolved_calculation_trace": {
                    "calculation_operands": [
                        {
                            "operand_id": "cand-visible",
                            "candidate_id": "cand-visible",
                            "evidence_id": "cand-visible",
                        }
                    ],
                    "calculation_plan": {
                        "status": "ok",
                        "mode": "semantic_program",
                        "operation": "semantic_program",
                    },
                    "calculation_result": {
                        "status": "ok",
                        "semantic_status": "ok",
                        "formatted_result": "value: 10 items",
                        "source_evidence_ids": ["cand-visible"],
                    },
                },
            },
        }
        agent = object.__new__(FinancialAgent)

        first = agent._assemble_ledger_phase(state)
        second = agent._assemble_ledger_phase(state)

        self.assertEqual(set(first), {"ledger"})
        self.assertEqual(first, second)
        self.assertEqual(
            first["ledger"]["task_artifact_trace"]["integrity_status"],
            "ok",
        )
        self.assertNotIn("tasks", state)
        self.assertEqual(project_financial_phase_state(state)["tasks"], [])
        self.assertEqual(len(set(FINANCIAL_GRAPH_PHASE_WRITERS.values())), 10)


if __name__ == "__main__":
    unittest.main()
