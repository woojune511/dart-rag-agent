"""Replay saved semantic programs through current runtime contracts.

The command is deliberately provider-free and read-only.  It reconstructs each
saved candidate catalog from immutable structure artifacts, restores the exact
saved visibility authority, and then runs the current validator and executor.
It does not migrate historical structured output or invoke a compiler.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program,
    validate_semantic_calculation_program,
)
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_runtime_contracts import (
    CandidateVisibilityV1,
    CompilationEnvelopeV2,
)
from src.ops.audit_candidate_ambiguity import (
    load_saved_plans,
    replay_verified_candidate_catalog,
)


AUTHORITY_ERROR_CODES = frozenset(
    {
        "compilation_envelope_required",
        "execution_content_mismatch",
        "validation_drift",
        "visibility_mismatch",
    }
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _saved_visibility(plan: Mapping[str, Any]) -> CandidateVisibilityV1:
    projection = dict(plan.get("candidate_visibility") or {})
    visibility = CandidateVisibilityV1.create(
        catalog_fingerprint=str(projection.get("catalog_fingerprint") or ""),
        visible_candidate_ids=projection.get("visible_candidate_ids") or (),
        candidate_ids_by_owner=dict(
            projection.get("candidate_ids_by_owner") or {}
        ),
        evidence_bundle_constraints=(
            projection.get("evidence_bundle_constraints") or ()
        ),
    )
    if visibility.cohort_fingerprint != str(
        projection.get("cohort_fingerprint") or ""
    ):
        raise ValueError("saved owner visibility fingerprint does not round-trip")
    return visibility


def _trace_fingerprint(row: Mapping[str, Any]) -> str:
    plan = dict(row.get("plan") or {})
    return _fingerprint(
        {
            "question_id": str(row.get("question_id") or ""),
            "question": str(row.get("question") or ""),
            "semantic_program": plan.get("semantic_program"),
            "answer_obligations": plan.get("answer_obligations"),
            "candidate_visibility": plan.get("candidate_visibility"),
            "candidate_catalog_fingerprint": plan.get(
                "candidate_catalog_fingerprint"
            ),
        }
    )


def _saved_result_files(results_paths: Sequence[Path]) -> list[Path]:
    files: set[Path] = set()
    for raw_path in results_paths:
        path = Path(raw_path).resolve()
        if path.is_file():
            files.add(path)
        elif path.is_dir():
            files.update(item.resolve() for item in path.rglob("results.json"))
        else:
            raise FileNotFoundError(path)
    return sorted(files, key=lambda path: path.as_posix())


def _input_paths(
    rows: Sequence[Mapping[str, Any]],
    *,
    result_files: Sequence[Path],
) -> list[Path]:
    paths = set(result_files)
    for row in rows:
        source_file = Path(str(row.get("source_file") or ""))
        if source_file.is_file():
            paths.add(source_file.resolve())
        persist_directory = str(
            dict(row.get("store") or {}).get("persist_directory") or ""
        ).strip()
        if not persist_directory:
            continue
        store_path = Path(persist_directory)
        for name in ("document_structure_graph.json", "table_payloads.json"):
            path = store_path / name
            if path.is_file():
                paths.add(path.resolve())
    return sorted(paths, key=lambda path: path.as_posix())


def _schema_errors(error: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "type": str(item.get("type") or ""),
            "location": [str(part) for part in (item.get("loc") or ())],
            "message": str(item.get("msg") or ""),
        }
        for item in error.errors(include_url=False, include_input=False)
    ]


def _error_codes(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row.get("code") or "")
            for row in rows
            if str(row.get("code") or "")
        }
    )


def _replay_case(row: Mapping[str, Any], trace_fingerprint: str) -> dict[str, Any]:
    plan = dict(row.get("plan") or {})
    program = dict(plan.get("semantic_program") or {})
    obligations = [
        dict(item)
        for item in (plan.get("answer_obligations") or [])
        if isinstance(item, Mapping)
    ]
    query = str(row.get("question") or "")
    program_fingerprint = _fingerprint(program)
    base = {
        "trace_fingerprint": trace_fingerprint,
        "question_id": str(row.get("question_id") or "unknown"),
        "source_file": str(row.get("source_file") or ""),
        "diagnostic_schema": str(
            dict(plan.get("candidate_stage_diagnostics") or {}).get("schema")
            or ""
        ),
        "program_fingerprint": program_fingerprint,
    }

    try:
        SemanticCalculationProgram.model_validate(program)
    except ValidationError as error:
        return {
            **base,
            "status": "skipped",
            "reason": "program_schema_mismatch",
            "schema_errors": _schema_errors(error),
        }

    try:
        visibility = _saved_visibility(plan)
    except (KeyError, TypeError, ValueError) as error:
        return {
            **base,
            "status": "failed",
            "reason": "visibility_projection_mismatch",
            "detail": str(error),
        }

    catalog, catalog_replay = replay_verified_candidate_catalog(
        plan,
        dict(row.get("store") or {}),
    )
    if catalog_replay.get("status") != "verified":
        return {
            **base,
            "status": "failed",
            "reason": "catalog_replay_not_verified",
            "catalog_replay": catalog_replay,
            "visibility_fingerprint": visibility.cohort_fingerprint,
        }

    validation = validate_semantic_calculation_program(
        program=program,
        obligations=obligations,
        candidate_catalog=catalog,
        query=query,
        candidate_visibility=visibility,
    )
    envelope = CompilationEnvelopeV2.create(
        program=program,
        validation=validation,
        visibility=visibility,
        candidate_catalog=catalog,
        obligations=obligations,
        query=query,
    )
    execution = execute_semantic_calculation_program(
        program=program,
        obligations=obligations,
        candidate_catalog=catalog,
        query=query,
        compilation_envelope=envelope,
        require_compilation_envelope=True,
    )

    validation_errors = [
        dict(item)
        for item in (validation.get("errors") or [])
        if isinstance(item, Mapping)
    ]
    runtime_validation_errors = [
        dict(item)
        for item in (dict(execution.get("validation") or {}).get("errors") or [])
        if isinstance(item, Mapping)
    ]
    execution_errors = [
        dict(item)
        for item in (execution.get("execution_errors") or [])
        if isinstance(item, Mapping)
    ]
    validation_status = str(validation.get("status") or "")
    execution_status = str(execution.get("status") or "")
    expected_execution_status = {
        "ready": "ok",
        "partial": "partial",
    }.get(validation_status)
    selected_by_validation = list(
        validation.get("selected_candidate_ids") or []
    )
    selected_by_execution = list(
        execution.get("selected_candidate_ids") or []
    )
    authority_codes = AUTHORITY_ERROR_CODES.intersection(
        _error_codes(runtime_validation_errors)
    )
    checks = {
        "program_bytes_unchanged": _fingerprint(program) == program_fingerprint,
        "catalog_replay_verified": catalog_replay.get("status") == "verified",
        "catalog_fingerprint_preserved": (
            visibility.catalog_fingerprint
            == str(plan.get("candidate_catalog_fingerprint") or "")
        ),
        "visibility_fingerprint_preserved": (
            visibility.cohort_fingerprint
            == str(
                dict(plan.get("candidate_visibility") or {}).get(
                    "cohort_fingerprint"
                )
                or ""
            )
        ),
        "validation_recomputed_identically": (
            _canonical_bytes(validation)
            == _canonical_bytes(execution.get("validation") or {})
        ),
        "selected_candidate_set_preserved": (
            set(selected_by_validation) == set(selected_by_execution)
        ),
        "selected_candidate_ids_unique": (
            len(selected_by_validation) == len(set(selected_by_validation))
            and len(selected_by_execution) == len(set(selected_by_execution))
        ),
        "selected_candidates_visible": set(selected_by_execution).issubset(
            visibility.visible_candidate_ids
        ),
        "accepted_validation_status": validation_status in {"ready", "partial"},
        "execution_status_consistent": (
            expected_execution_status == execution_status
        ),
        "authority_errors_zero": not authority_codes,
        "execution_errors_zero": not execution_errors,
    }
    return {
        **base,
        "status": "passed" if all(checks.values()) else "failed",
        "reason": "" if all(checks.values()) else "runtime_contract_check_failed",
        "catalog_replay": catalog_replay,
        "catalog_fingerprint": visibility.catalog_fingerprint,
        "visibility_fingerprint": visibility.cohort_fingerprint,
        "execution_content_fingerprint": (
            envelope.execution_content_fingerprint
        ),
        "validation": {
            "status": validation_status,
            "fingerprint": _fingerprint(validation),
            "error_codes": _error_codes(validation_errors),
            "missing_obligation_ids": list(
                validation.get("missing_obligation_ids") or []
            ),
            "selected_candidate_ids": selected_by_validation,
        },
        "execution": {
            "status": execution_status,
            "fingerprint": _fingerprint(execution),
            "error_codes": _error_codes(execution_errors),
            "missing_obligation_ids": list(
                execution.get("missing_obligation_ids") or []
            ),
            "selected_candidate_ids": selected_by_execution,
        },
        "checks": checks,
    }


def replay_saved_runtime_traces(
    results_paths: Sequence[Path],
    *,
    question_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Replay distinct exact saved traces without changing any input artifact."""

    result_files = _saved_result_files(results_paths)
    rows = load_saved_plans(
        result_files,
        question_ids=question_ids,
    )
    input_paths = _input_paths(rows, result_files=result_files)
    input_hashes = {
        path.as_posix(): _file_sha256(path)
        for path in input_paths
    }

    distinct_rows: list[tuple[Mapping[str, Any], str]] = []
    first_source_by_fingerprint: dict[str, str] = {}
    duplicates: list[dict[str, str]] = []
    for row in rows:
        trace_fingerprint = _trace_fingerprint(row)
        source_file = str(row.get("source_file") or "")
        if trace_fingerprint in first_source_by_fingerprint:
            duplicates.append(
                {
                    "trace_fingerprint": trace_fingerprint,
                    "source_file": source_file,
                    "duplicate_of_source_file": first_source_by_fingerprint[
                        trace_fingerprint
                    ],
                }
            )
            continue
        first_source_by_fingerprint[trace_fingerprint] = source_file
        distinct_rows.append((row, trace_fingerprint))

    cases = [
        _replay_case(row, trace_fingerprint)
        for row, trace_fingerprint in distinct_rows
    ]
    eligible_cases = [case for case in cases if case["status"] != "skipped"]
    passed_cases = [case for case in eligible_cases if case["status"] == "passed"]
    failed_cases = [case for case in eligible_cases if case["status"] == "failed"]
    skipped_cases = [case for case in cases if case["status"] == "skipped"]
    inputs_unchanged = all(
        path.is_file() and _file_sha256(path) == input_hashes[path.as_posix()]
        for path in input_paths
    )
    unique_questions = {
        _fingerprint(
            {
                "question_id": str(row.get("question_id") or ""),
                "question": str(row.get("question") or ""),
            }
        )
        for row, _trace_fingerprint_value in distinct_rows
    }
    status = (
        "passed"
        if eligible_cases and not failed_cases and inputs_unchanged
        else "failed"
    )
    return {
        "schema_version": "exact_saved_runtime_trace_replay_v1",
        "status": status,
        "provider_calls": 0,
        "compiler_calls": 0,
        "source_store_writes": 0,
        "claim_boundary": (
            "Exact saved compiler decisions are replayed through the current "
            "catalog, visibility, validator, envelope, and executor contracts. "
            "This does not test new compiler selection, retrieval, provider "
            "behavior, evaluator acceptance, or release readiness."
        ),
        "summary": {
            "loaded_plan_count": len(rows),
            "distinct_trace_count": len(distinct_rows),
            "eligible_trace_count": len(eligible_cases),
            "passed_trace_count": len(passed_cases),
            "failed_trace_count": len(failed_cases),
            "skipped_trace_count": len(skipped_cases),
            "duplicate_plan_count": len(duplicates),
            "unique_question_count": len(unique_questions),
        },
        "immutable_input_sha256": input_hashes,
        "immutable_inputs_unchanged": inputs_unchanged,
        "cases": cases,
        "duplicates": duplicates,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        nargs="+",
        required=True,
        help="Saved results.json file or directory tree.",
    )
    parser.add_argument(
        "--question-id",
        action="append",
        dest="question_ids",
        help="Optional exact question ID filter; repeat for multiple IDs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="New receipt path; an existing file is never overwritten.",
    )
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        parser.error("output already exists; use a new successor receipt path")

    result = replay_saved_runtime_traces(
        args.results,
        question_ids=set(args.question_ids) if args.question_ids else None,
    )
    serialized = json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "output": args.output.as_posix(),
                    "summary": result["summary"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(serialized, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
