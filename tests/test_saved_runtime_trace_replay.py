from __future__ import annotations

from contextlib import redirect_stderr
from copy import deepcopy
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.agent.financial_reconciliation_candidates import (
    semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_runtime_contracts import CandidateVisibilityV1
from src.ops.replay_saved_runtime_traces import (
    main,
    replay_saved_runtime_traces,
)


def _scope() -> dict:
    return {
        "company": "",
        "period": "",
        "consolidation_scope": "unknown",
        "segment": "",
        "basis": "",
    }


def _obligation() -> dict:
    return {
        "obligation_id": "ob_value",
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


def _candidate() -> dict:
    return {
        "candidate_id": "cand-value",
        "kind": "numeric",
        "source_candidate_id": "source-cand-value",
        "evidence_id": "evidence-cand-value",
        "source_anchor": "[sample | section]",
        "source_row_id": "row-cand-value",
        "table_source_id": "table-a",
        "row_label": "reported value",
        "statement_type": "",
        "company": "",
        "year": 2024,
        "consolidation_scope": "unknown",
        "segment": "",
        "basis": "",
        "context_fingerprint": "table-a",
        "source_text": "reported value 10 items",
        "candidate_kind": "structured_value",
        "raw_value": "10",
        "raw_unit": "items",
        "normalized_value": 10.0,
        "normalized_unit": "COUNT",
        "period": "",
        "column_headers": [],
        "value_role": "",
        "aggregation_stage": "",
        "aggregate_label": "",
    }


def _plan(program: dict, catalog: list[dict]) -> dict:
    catalog_fingerprint = semantic_candidate_catalog_fingerprint(catalog)
    visibility = CandidateVisibilityV1.create(
        catalog_fingerprint=catalog_fingerprint,
        visible_candidate_ids=["cand-value"],
        candidate_ids_by_owner={"ob_value": ["cand-value"]},
    )
    return {
        "semantic_program": program,
        "answer_obligations": [_obligation()],
        "candidate_catalog_fingerprint": catalog_fingerprint,
        "candidate_visibility": visibility.to_projection(),
        "candidate_stage_diagnostics": {
            "schema": "semantic_candidate_stage_diagnostics_v9"
        },
    }


def _row(source_file: Path, *, question_id: str, plan: dict) -> dict:
    return {
        "question_id": question_id,
        "question": "Return the reported value.",
        "source_file": source_file.as_posix(),
        "plan": plan,
        "store": {},
    }


def _verified_catalog() -> dict:
    return {
        "status": "verified",
        "source": "provider_free_structure_graph_replay",
        "reason": "",
        "source_candidate_count": 1,
        "catalog_candidate_count": 1,
        "mismatch_fields": [],
    }


class SavedRuntimeTraceReplayTests(unittest.TestCase):
    def test_exact_current_trace_replays_without_provider_or_compiler(self) -> None:
        catalog = [_candidate()]
        program = {
            "status": "ready",
            "direct_bindings": [
                {"obligation_id": "ob_value", "candidate_id": "cand-value"}
            ],
        }
        with TemporaryDirectory() as directory:
            source_file = Path(directory) / "results.json"
            source_file.write_text("{}", encoding="utf-8")
            row = _row(
                source_file,
                question_id="sample-current",
                plan=_plan(program, catalog),
            )
            with (
                patch(
                    "src.ops.replay_saved_runtime_traces.load_saved_plans",
                    return_value=[row],
                ),
                patch(
                    "src.ops.replay_saved_runtime_traces.replay_verified_candidate_catalog",
                    return_value=(catalog, _verified_catalog()),
                ),
            ):
                first = replay_saved_runtime_traces([source_file])
                second = replay_saved_runtime_traces([source_file])

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "passed")
        self.assertEqual(first["provider_calls"], 0)
        self.assertEqual(first["compiler_calls"], 0)
        self.assertEqual(first["source_store_writes"], 0)
        self.assertTrue(first["immutable_inputs_unchanged"])
        self.assertEqual(
            first["summary"],
            {
                "loaded_plan_count": 1,
                "distinct_trace_count": 1,
                "eligible_trace_count": 1,
                "passed_trace_count": 1,
                "failed_trace_count": 0,
                "skipped_trace_count": 0,
                "duplicate_plan_count": 0,
                "unique_question_count": 1,
            },
        )
        case = first["cases"][0]
        self.assertEqual(case["validation"]["status"], "ready")
        self.assertEqual(case["execution"]["status"], "ok")
        self.assertEqual(
            case["execution"]["selected_candidate_ids"],
            ["cand-value"],
        )
        self.assertTrue(all(case["checks"].values()))

    def test_legacy_program_is_reported_as_skipped_without_migration(self) -> None:
        catalog = [_candidate()]
        current_program = {
            "status": "ready",
            "direct_bindings": [
                {"obligation_id": "ob_value", "candidate_id": "cand-value"}
            ],
        }
        legacy_program = {
            "status": "ready",
            "expressions": [
                {
                    "obligation_id": "ob_value",
                    "variable_bindings": [],
                    "formula": "1",
                    "result_unit": "COUNT",
                }
            ],
        }
        predecessor = deepcopy(legacy_program)
        with TemporaryDirectory() as directory:
            current_file = Path(directory) / "current.json"
            legacy_file = Path(directory) / "legacy.json"
            current_file.write_text("{}", encoding="utf-8")
            legacy_file.write_text("{}", encoding="utf-8")
            rows = [
                _row(
                    current_file,
                    question_id="sample-current",
                    plan=_plan(current_program, catalog),
                ),
                _row(
                    legacy_file,
                    question_id="sample-legacy",
                    plan=_plan(legacy_program, catalog),
                ),
            ]
            with (
                patch(
                    "src.ops.replay_saved_runtime_traces.load_saved_plans",
                    return_value=rows,
                ),
                patch(
                    "src.ops.replay_saved_runtime_traces.replay_verified_candidate_catalog",
                    return_value=(catalog, _verified_catalog()),
                ) as replay_catalog,
            ):
                result = replay_saved_runtime_traces(
                    [current_file, legacy_file]
                )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["summary"]["eligible_trace_count"], 1)
        self.assertEqual(result["summary"]["skipped_trace_count"], 1)
        self.assertEqual(replay_catalog.call_count, 1)
        skipped = next(
            case for case in result["cases"] if case["status"] == "skipped"
        )
        self.assertEqual(skipped["reason"], "program_schema_mismatch")
        self.assertTrue(skipped["schema_errors"])
        self.assertEqual(legacy_program, predecessor)

    def test_identical_runtime_inputs_are_counted_once(self) -> None:
        catalog = [_candidate()]
        plan = _plan(
            {
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_value",
                        "candidate_id": "cand-value",
                    }
                ],
            },
            catalog,
        )
        with TemporaryDirectory() as directory:
            first_file = Path(directory) / "first.json"
            second_file = Path(directory) / "second.json"
            first_file.write_text("{}", encoding="utf-8")
            second_file.write_text("{}", encoding="utf-8")
            rows = [
                _row(first_file, question_id="sample", plan=plan),
                _row(second_file, question_id="sample", plan=deepcopy(plan)),
            ]
            with (
                patch(
                    "src.ops.replay_saved_runtime_traces.load_saved_plans",
                    return_value=rows,
                ),
                patch(
                    "src.ops.replay_saved_runtime_traces.replay_verified_candidate_catalog",
                    return_value=(catalog, _verified_catalog()),
                ),
            ):
                result = replay_saved_runtime_traces(
                    [first_file, second_file]
                )

        self.assertEqual(result["summary"]["loaded_plan_count"], 2)
        self.assertEqual(result["summary"]["distinct_trace_count"], 1)
        self.assertEqual(result["summary"]["eligible_trace_count"], 1)
        self.assertEqual(result["summary"]["duplicate_plan_count"], 1)
        self.assertEqual(len(result["duplicates"]), 1)

    def test_result_paths_are_sorted_before_saved_plan_selection(self) -> None:
        catalog = [_candidate()]
        plan = _plan(
            {
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_value",
                        "candidate_id": "cand-value",
                    }
                ],
            },
            catalog,
        )
        with TemporaryDirectory() as directory:
            first_file = Path(directory) / "a.json"
            second_file = Path(directory) / "z.json"
            first_file.write_text("{}", encoding="utf-8")
            second_file.write_text("{}", encoding="utf-8")
            row = _row(first_file, question_id="sample", plan=plan)
            with (
                patch(
                    "src.ops.replay_saved_runtime_traces.load_saved_plans",
                    return_value=[row],
                ) as load_plans,
                patch(
                    "src.ops.replay_saved_runtime_traces.replay_verified_candidate_catalog",
                    return_value=(catalog, _verified_catalog()),
                ),
            ):
                result = replay_saved_runtime_traces(
                    [second_file, first_file]
                )

        self.assertEqual(result["status"], "passed")
        loaded_paths = load_plans.call_args.args[0]
        self.assertEqual(
            loaded_paths,
            [first_file.resolve(), second_file.resolve()],
        )

    def test_current_schema_with_unverified_catalog_fails(self) -> None:
        catalog = [_candidate()]
        plan = _plan(
            {
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_value",
                        "candidate_id": "cand-value",
                    }
                ],
            },
            catalog,
        )
        with TemporaryDirectory() as directory:
            source_file = Path(directory) / "results.json"
            source_file.write_text("{}", encoding="utf-8")
            row = _row(source_file, question_id="sample", plan=plan)
            with (
                patch(
                    "src.ops.replay_saved_runtime_traces.load_saved_plans",
                    return_value=[row],
                ),
                patch(
                    "src.ops.replay_saved_runtime_traces.replay_verified_candidate_catalog",
                    return_value=(
                        [],
                        {
                            "status": "mismatch",
                            "reason": "saved_fingerprint_mismatch",
                        },
                    ),
                ),
            ):
                result = replay_saved_runtime_traces([source_file])

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["summary"]["failed_trace_count"], 1)
        self.assertEqual(
            result["cases"][0]["reason"],
            "catalog_replay_not_verified",
        )

    def test_existing_receipt_is_not_overwritten_or_replayed(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"
            output.touch()
            with patch(
                "src.ops.replay_saved_runtime_traces.replay_saved_runtime_traces"
            ) as replay:
                with self.assertRaises(SystemExit) as raised, redirect_stderr(
                    StringIO()
                ):
                    main(
                        [
                            "--results",
                            "unused.json",
                            "--output",
                            str(output),
                        ]
                    )
            self.assertEqual(raised.exception.code, 2)
            replay.assert_not_called()
            self.assertEqual(output.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
