"""Replay reviewed real-question fixtures through current numeric contracts.

The corpus is a compact, source-derived test artifact.  It deliberately starts
after retrieval and compilation: candidates, owner visibility, and the semantic
program are reviewed fixture inputs.  The command normalizes the fixture's raw
numeric surfaces, then runs the current validator, immutable compilation
envelope, and executor without constructing a provider or touching a store.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program,
    validate_semantic_calculation_program,
)
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_reconciliation_candidates import (
    semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_runtime_contracts import (
    CandidateVisibilityV1,
    CompilationEnvelopeV2,
)
from src.agent.financial_runtime_normalization import _normalise_operand_value


CORPUS_SCHEMA_VERSION = "reviewed_runtime_replay_corpus_v1"
RECEIPT_SCHEMA_VERSION = "reviewed_runtime_replay_receipt_v1"
NUMERIC_EXPECTATION_FIELDS = frozenset(
    {
        "value",
        "normalized_value",
        "calculated_value",
        "display_value",
        "source_display_normalized_value",
        "formula_result_value",
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


def _schema_errors(error: ValidationError) -> list[dict[str, Any]]:
    return [
        {
            "type": str(item.get("type") or ""),
            "location": [str(part) for part in (item.get("loc") or ())],
            "message": str(item.get("msg") or ""),
        }
        for item in error.errors(include_url=False, include_input=False)
    ]


def _materialize_catalog(
    raw_candidates: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Use the real normalizer instead of trusting copied normalized numbers."""

    catalog: list[dict[str, Any]] = []
    normalization_checks: list[dict[str, Any]] = []
    for raw_candidate in raw_candidates:
        candidate = deepcopy(dict(raw_candidate))
        expected_value = candidate.pop("expected_normalized_value", None)
        expected_unit = str(
            candidate.pop("expected_normalized_unit", "") or ""
        )
        candidate_id = str(candidate.get("candidate_id") or "")
        if str(candidate.get("kind") or "") == "numeric":
            value, unit = _normalise_operand_value(
                str(candidate.get("raw_value") or ""),
                str(candidate.get("raw_unit") or ""),
            )
            candidate["normalized_value"] = value
            candidate["normalized_unit"] = unit
            value_matches = (
                expected_value is not None
                and value is not None
                and math.isclose(
                    float(value),
                    float(expected_value),
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            )
            unit_matches = bool(expected_unit) and unit == expected_unit
        else:
            candidate["normalized_value"] = None
            candidate["normalized_unit"] = "UNKNOWN"
            value_matches = expected_value is None
            unit_matches = expected_unit in {"", "UNKNOWN"}
        normalization_checks.append(
            {
                "candidate_id": candidate_id,
                "value_matches": value_matches,
                "unit_matches": unit_matches,
                "normalized_value": candidate.get("normalized_value"),
                "normalized_unit": candidate.get("normalized_unit"),
            }
        )
        catalog.append(candidate)
    return catalog, normalization_checks


def _source_provenance_complete(candidate: Mapping[str, Any]) -> bool:
    required = (
        "candidate_id",
        "source_candidate_id",
        "evidence_id",
        "source_anchor",
        "source_row_id",
        "source_text",
    )
    if any(not str(candidate.get(field) or "").strip() for field in required):
        return False
    if str(candidate.get("kind") or "") != "numeric":
        return True
    raw_value = str(candidate.get("raw_value") or "").strip()
    return bool(raw_value) and raw_value in str(candidate.get("source_text") or "")


def _output_matches(
    output: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    absolute_tolerance: float,
) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    for field, expected_value in expected.items():
        if field == "obligation_id":
            continue
        actual_value = output.get(field)
        if field in NUMERIC_EXPECTATION_FIELDS and expected_value is not None:
            try:
                matches = math.isclose(
                    float(actual_value),
                    float(expected_value),
                    rel_tol=0.0,
                    abs_tol=absolute_tolerance,
                )
            except (TypeError, ValueError):
                matches = False
        else:
            matches = actual_value == expected_value
        if not matches:
            mismatches.append(field)
    return not mismatches, mismatches


def _replay_case(raw_case: Mapping[str, Any]) -> dict[str, Any]:
    case = deepcopy(dict(raw_case))
    case_id = str(case.get("case_id") or "")
    question_id = str(case.get("question_id") or "")
    query = str(case.get("question") or "")
    obligations = [
        dict(item)
        for item in (case.get("obligations") or [])
        if isinstance(item, Mapping)
    ]
    catalog, normalization_checks = _materialize_catalog(
        [
            dict(item)
            for item in (case.get("candidate_catalog") or [])
            if isinstance(item, Mapping)
        ]
    )
    candidate_ids = [
        str(candidate.get("candidate_id") or "") for candidate in catalog
    ]
    review = dict(case.get("review") or {})
    base = {
        "case_id": case_id,
        "question_id": question_id,
        "fixture_fingerprint": _fingerprint(case),
        "review_basis": str(review.get("basis") or ""),
        "source_references": list(review.get("source_references") or []),
    }

    try:
        program = SemanticCalculationProgram.model_validate(
            dict(case.get("program") or {})
        ).model_dump(mode="json")
    except ValidationError as error:
        return {
            **base,
            "status": "failed",
            "reason": "program_schema_mismatch",
            "schema_errors": _schema_errors(error),
        }

    catalog_fingerprint = semantic_candidate_catalog_fingerprint(catalog)
    try:
        visibility = CandidateVisibilityV1.create(
            catalog_fingerprint=catalog_fingerprint,
            visible_candidate_ids=candidate_ids,
            candidate_ids_by_owner=dict(
                dict(case.get("visibility") or {}).get(
                    "candidate_ids_by_owner"
                )
                or {}
            ),
        )
    except (TypeError, ValueError) as error:
        return {
            **base,
            "status": "failed",
            "reason": "visibility_projection_mismatch",
            "detail": str(error),
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

    expected = dict(case.get("expected") or {})
    expected_outputs = [
        dict(item)
        for item in (expected.get("outputs") or [])
        if isinstance(item, Mapping)
    ]
    outputs_by_obligation = {
        str(item.get("obligation_id") or ""): dict(item)
        for item in (execution.get("outputs") or [])
        if isinstance(item, Mapping)
    }
    output_checks: list[dict[str, Any]] = []
    for expected_output in expected_outputs:
        obligation_id = str(expected_output.get("obligation_id") or "")
        actual_output = outputs_by_obligation.get(obligation_id, {})
        matches, mismatch_fields = _output_matches(
            actual_output,
            expected_output,
            absolute_tolerance=float(expected.get("absolute_tolerance") or 1e-9),
        )
        output_checks.append(
            {
                "obligation_id": obligation_id,
                "matches": matches,
                "mismatch_fields": mismatch_fields,
            }
        )

    selected_ids = list(execution.get("selected_candidate_ids") or [])
    checks = {
        "reviewed_source_basis": (
            str(review.get("status") or "") == "reviewed"
            and bool(review.get("source_references"))
        ),
        "question_identity_present": bool(case_id and question_id and query),
        "candidate_ids_unique": (
            bool(candidate_ids)
            and all(candidate_ids)
            and len(candidate_ids) == len(set(candidate_ids))
        ),
        "source_provenance_complete": all(
            _source_provenance_complete(candidate) for candidate in catalog
        ),
        "raw_normalization_matches_review": all(
            row["value_matches"] and row["unit_matches"]
            for row in normalization_checks
        ),
        "validation_status_expected": (
            str(validation.get("status") or "")
            == str(expected.get("validation_status") or "")
        ),
        "execution_status_expected": (
            str(execution.get("status") or "")
            == str(expected.get("execution_status") or "")
        ),
        "selected_candidate_ids_expected": (
            selected_ids == list(expected.get("selected_candidate_ids") or [])
        ),
        "expected_outputs_match": (
            bool(output_checks)
            and all(row["matches"] for row in output_checks)
        ),
        "execution_content_bound": envelope.matches_execution_content(
            candidate_catalog=catalog,
            obligations=obligations,
            query=query,
        ),
        "validation_recomputed_identically": (
            _canonical_bytes(validation)
            == _canonical_bytes(execution.get("validation") or {})
        ),
        "execution_errors_zero": not list(
            execution.get("execution_errors") or []
        ),
    }
    passed = all(checks.values())
    return {
        **base,
        "status": "passed" if passed else "failed",
        "reason": "" if passed else "runtime_contract_check_failed",
        "catalog_fingerprint": catalog_fingerprint,
        "visibility_fingerprint": visibility.cohort_fingerprint,
        "execution_content_fingerprint": envelope.execution_content_fingerprint,
        "normalization": normalization_checks,
        "validation": {
            "status": str(validation.get("status") or ""),
            "errors": list(validation.get("errors") or []),
            "selected_candidate_ids": list(
                validation.get("selected_candidate_ids") or []
            ),
        },
        "execution": {
            "status": str(execution.get("status") or ""),
            "errors": list(execution.get("execution_errors") or []),
            "selected_candidate_ids": selected_ids,
            "outputs": list(execution.get("outputs") or []),
        },
        "output_checks": output_checks,
        "checks": checks,
    }


def replay_reviewed_runtime_corpus(corpus_path: Path) -> dict[str, Any]:
    """Replay one immutable reviewed corpus with no provider or store access."""

    path = Path(corpus_path).resolve()
    raw_bytes = path.read_bytes()
    corpus = json.loads(raw_bytes.decode("utf-8"))
    if str(corpus.get("schema_version") or "") != CORPUS_SCHEMA_VERSION:
        raise ValueError("unsupported reviewed runtime corpus schema")
    raw_cases = [
        dict(item)
        for item in (corpus.get("cases") or [])
        if isinstance(item, Mapping)
    ]
    cases = [_replay_case(case) for case in raw_cases]
    question_ids = [str(case.get("question_id") or "") for case in raw_cases]
    distinct_questions = bool(question_ids) and len(question_ids) == len(
        set(question_ids)
    )
    passed_count = sum(case.get("status") == "passed" for case in cases)
    failed_count = len(cases) - passed_count
    status = (
        "passed"
        if cases and not failed_count and distinct_questions
        else "failed"
    )
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "status": status,
        "provider_calls": 0,
        "compiler_calls": 0,
        "retrieval_calls": 0,
        "source_store_writes": 0,
        "claim_boundary": str(corpus.get("claim_boundary") or ""),
        "corpus_path": path.as_posix(),
        "corpus_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "summary": {
            "case_count": len(cases),
            "unique_question_count": len(set(question_ids)),
            "distinct_question_ids": distinct_questions,
            "passed_case_count": passed_count,
            "failed_case_count": failed_count,
        },
        "cases": cases,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional new receipt; an existing file is never overwritten.",
    )
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        parser.error("output already exists; use a successor receipt path")
    result = replay_reviewed_runtime_corpus(args.corpus)
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
