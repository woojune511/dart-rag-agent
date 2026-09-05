from __future__ import annotations

import hashlib
import json
import unittest
from unittest.mock import patch

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import (
    _semantic_candidate_capacity,
    _semantic_candidate_cohorts,
)
from src.agent.financial_graph_models import SemanticCalculationProgram
from tests.semantic_program_test_support import (
    _StructuredQueueLLM,
    _candidate,
    _obligation,
    _scope,
)


def _table_bundle(prefix: str, count: int, *, segment: str = "") -> list[dict]:
    """One real physical row; expansion must keep every cell together."""
    row_label = f"{segment} quantity".strip()
    source_text = row_label + " " + " | ".join(str(index + 1) for index in range(count))
    return [
        {
            **_candidate(f"{prefix}-{index:03d}", index + 1, context=prefix, row_label=row_label),
            "physical_table_id": prefix,
            "physical_row_id": "row-1",
            "physical_cell_id": f"cell-{index}",
            "source_bundle_text": source_text,
            "segment": segment,
        }
        for index in range(count)
    ]


def _state(catalog: list[dict], obligations: list[dict]) -> dict:
    return {
        "query": "Return each requested quantity.",
        "answer_obligations": obligations,
        "semantic_plan": {"program_required": True, "answer_obligations": obligations},
        "semantic_candidate_catalog_prebuilt": True,
        "semantic_candidate_catalog": catalog,
        "semantic_source_candidates": [],
        "active_subtask": {"task_id": "task_1"},
        "tasks": [],
        "artifacts": [],
        "resolved_calculation_trace": {},
    }


def _agent(*responses: SemanticCalculationProgram) -> FinancialAgent:
    agent = object.__new__(FinancialAgent)
    agent.llm = _StructuredQueueLLM(*responses)
    agent.llm_routes = {}
    agent.llm_usage_callback = None
    return agent


def _diagnostics(compiled: dict) -> dict:
    return compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]


def _program_bytes(program: dict) -> bytes:
    return json.dumps(program, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class SemanticCapacityContractTests(unittest.TestCase):
    def test_capacity_counts_unique_selected_ids_at_exact_numeric_and_narrative_limits(self) -> None:
        numeric = [{"candidate_id": f"n-{index}", "kind": "numeric"} for index in range(97)]
        narrative = [{"candidate_id": f"p-{index}", "kind": "narrative"} for index in range(33)]
        catalog = [*numeric, *narrative]
        selected = [row["candidate_id"] for row in [*numeric[:96], *narrative[:32]]]

        result = _semantic_candidate_capacity(catalog, [*selected, *selected])
        self.assertEqual(result["status"], "ok")
        self.assertEqual((result["numeric"], result["narrative"]), (96, 32))
        for extra, counts in (("n-96", (97, 32)), ("p-32", (96, 33))):
            with self.subTest(extra=extra):
                result = _semantic_candidate_capacity(catalog, [*selected, extra, extra])
                self.assertEqual(result["status"], "capacity_exceeded")
                self.assertEqual((result["numeric"], result["narrative"]), counts)

    def test_many_owners_sharing_six_narratives_do_not_reserve_duplicate_capacity(self) -> None:
        catalog = [
            {
                **_candidate(f"summary-{index}", 0),
                "kind": "narrative",
                "candidate_kind": "narrative",
                "raw_value": "",
                "normalized_value": None,
                "source_text": "The activity summary describes product reliability.",
            }
            for index in range(6)
        ]
        obligations = [_obligation(f"ob-{index}", "narrative", "activity summary") for index in range(8)]
        cohorts = _semantic_candidate_cohorts(catalog, obligations)

        self.assertEqual(cohorts["status"], "ok")
        self.assertEqual(len(cohorts["candidate_ids_by_owner"]), 8)
        self.assertEqual({len(ids) for ids in cohorts["candidate_ids_by_owner"].values()}, {6})
        self.assertEqual(len(cohorts["visible_candidate_ids"]), 6)
        self.assertEqual(cohorts["reservation"]["narrative"], 6)
        self.assertEqual(cohorts["reservation"]["numeric"], 0)

    def test_atomic_row_expansion_to_97_blocks_every_compiler_call(self) -> None:
        catalog = _table_bundle("oversized-row", 97)
        obligations = [_obligation("ob-quantity", "direct_value", "quantity")]
        agent = _agent()

        compiled = agent._compile_semantic_calculation_program(_state(catalog, obligations))

        self.assertEqual(agent.llm.prompts, [])
        self.assertEqual(_diagnostics(compiled)["compiler_call_count"], 0)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "invalid")
        plan = compiled["resolved_calculation_trace"]["calculation_plan"]
        self.assertEqual(plan["candidate_cohort_status"], "capacity_exceeded")

    def test_retry_over_query_capacity_is_blocked_without_changing_accepted_island_bytes(self) -> None:
        catalog = [
            *_table_bundle("stable", 94, segment="stable"),
            *_table_bundle("retry-a", 1, segment="retry"),
            *_table_bundle("retry-b", 1, segment="retry"),
            *_table_bundle("retry-z", 2, segment="retry"),
        ]
        obligations = [
            _obligation("ob-stable", "direct_value", "quantity", scope=_scope(segment="stable")),
            _obligation("ob-retry", "direct_value", "quantity", scope=_scope(segment="retry")),
        ]
        initial = _semantic_candidate_cohorts(catalog, obligations)
        self.assertEqual(initial["reservation"]["numeric"], 96)
        self.assertEqual(set(initial["candidate_ids_by_owner"]["ob-retry"]), {"retry-a-000", "retry-b-000"})
        accepted = SemanticCalculationProgram.model_validate({
            "status": "ready",
            "direct_bindings": [{"obligation_id": "ob-stable", "candidate_id": "stable-000"}],
            "rationale": "Keep this already accepted island unchanged.",
        })
        accepted_bytes = _program_bytes(accepted.model_dump())
        failed = SemanticCalculationProgram.model_validate({
            "status": "incomplete", "missing_obligation_ids": ["ob-retry"],
        })
        agent = _agent(accepted, failed)

        # Capacity-boundary injection only: real validation marks the missing output
        # invalid; forced exclusions exercise expansion, not semantic error attribution.
        with patch(
            "src.agent.financial_graph_calculation._retry_candidate_exclusions",
            return_value={"ob-retry": ["retry-a-000"]},
        ) as exclusions:
            compiled = agent._compile_semantic_calculation_program(_state(catalog, obligations))

        exclusions.assert_called_once()
        diagnostics = _diagnostics(compiled)
        self.assertEqual(len(agent.llm.prompts), 2)
        self.assertEqual(diagnostics["compiler_call_count"], 2)
        self.assertEqual(diagnostics["compiler_retry_count"], 0)
        blocked_attempt = next(row for row in diagnostics["attempts"] if row.get("retry_blocked_reason"))
        self.assertEqual(blocked_attempt["retry_blocked_reason"], "capacity_exceeded")
        self.assertEqual(blocked_attempt["retry_capacity"]["numeric"], 97)
        stable = diagnostics["islands"][0]
        self.assertEqual(stable["obligation_ids"], ["ob-stable"])
        self.assertEqual(stable["accepted_program_bytes"], len(accepted_bytes))
        self.assertEqual(stable["accepted_program_fingerprint"], hashlib.sha256(accepted_bytes).hexdigest())
        self.assertEqual(_program_bytes(accepted.model_dump()), accepted_bytes)
        self.assertEqual(compiled["semantic_program"]["direct_bindings"], accepted.model_dump()["direct_bindings"])
        self.assertIn("ob-retry", compiled["semantic_program_validation"]["missing_obligation_ids"])

    def test_later_retry_accounts_for_an_earlier_islands_successful_bundle_expansion(self) -> None:
        catalog = [
            *_table_bundle("first-a", 1, segment="first"),
            *_table_bundle("first-b", 1, segment="first"),
            *_table_bundle("first-z", 93, segment="first"),
            *_table_bundle("second-a", 1, segment="second"),
            *_table_bundle("second-b", 1, segment="second"),
            *_table_bundle("second-z", 2, segment="second"),
        ]
        obligations = [
            _obligation("ob-first", "direct_value", "quantity", scope=_scope(segment="first")),
            _obligation("ob-second", "direct_value", "quantity", scope=_scope(segment="second")),
        ]
        self.assertEqual(_semantic_candidate_cohorts(catalog, obligations)["reservation"]["numeric"], 4)
        accepted = SemanticCalculationProgram.model_validate({
            "status": "ready",
            "direct_bindings": [{"obligation_id": "ob-first", "candidate_id": "first-b-000"}],
        })
        agent = _agent(
            SemanticCalculationProgram.model_validate({"missing_obligation_ids": ["ob-first"]}),
            accepted,
            SemanticCalculationProgram.model_validate({"missing_obligation_ids": ["ob-second"]}),
        )

        def force_bundle_replacement(**kwargs):
            # The real missing-output validator remains active. This injection only
            # forces a replacement so both retry capacity transitions are exercised.
            target = kwargs["target_obligation_ids"][0]
            prefix = "first" if target == "ob-first" else "second"
            return {target: [f"{prefix}-a-000"]}

        with patch(
            "src.agent.financial_graph_calculation._retry_candidate_exclusions",
            side_effect=force_bundle_replacement,
        ):
            compiled = agent._compile_semantic_calculation_program(_state(catalog, obligations))

        diagnostics = _diagnostics(compiled)
        self.assertEqual(len(agent.llm.prompts), 3)
        self.assertEqual(diagnostics["compiler_call_count"], 3)
        self.assertEqual(diagnostics["compiler_retry_count"], 1)
        self.assertEqual([item["retry_count"] for item in diagnostics["islands"]], [1, 0])
        attempts = diagnostics["attempts"]
        self.assertEqual([len(item["visible_candidate_ids"]) for item in attempts], [2, 94, 2])
        self.assertEqual(attempts[-1]["retry_blocked_reason"], "capacity_exceeded")
        self.assertEqual(attempts[-1]["retry_capacity"]["numeric"], 97)
        self.assertEqual(compiled["semantic_program"]["direct_bindings"], accepted.model_dump()["direct_bindings"])


if __name__ == "__main__":
    unittest.main()
