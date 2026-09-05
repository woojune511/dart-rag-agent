"""Provider-free integration replay of three immutable, reviewed source cases.

This is not a compiler or evaluator run. Two cases deliberately repair a copy of
the saved program to isolate runtime contracts; those counterfactuals do not
claim that a provider selected the repaired program. Source-store access is
limited to the existing read-only JSON catalog-replay helper. No FinancialAgent,
vector store, provider, ingestion, or benchmark runner is initialized.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.agent.financial_calculation_execution import (
    assemble_semantic_execution_result,
    execute_semantic_calculation_program,
    validate_semantic_calculation_program,
)
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_runtime_contracts import CandidateVisibilityV1, CompilationEnvelopeV2
from src.ops.audit_candidate_ambiguity import load_saved_plans, replay_verified_candidate_catalog


# Reviewed integration fixtures, never imported by runtime selection or ranking.
CASE_IDS = ("HYU_T2_010", "HYU_T3_072", "SAM_T2_078")
SOURCE_DISPLAY_ID = "cand_47bfc4cc05d682154cfa"
FIRST_DIRECT_ID = "cand_27da082cf5bcd0cb9f27"
FIRST_COMPATIBILITY_ID = "cand_b1928cbb468e083a8bd8"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _explicit_legacy_expression_decisions(program: Mapping[str, Any]) -> tuple[dict, list[dict]]:
    """Migrate a replay copy explicitly; no live structured-output fallback."""
    copied = deepcopy(dict(program))
    changes = []
    for expression in copied.get("expressions") or []:
        owner = str(expression.get("obligation_id") or "")
        if not expression.get("source_display_candidate_id"):
            old_value = expression.get("source_display_candidate_id")
            expression["source_display_candidate_id"] = None
            changes.append({"obligation_id": owner, "field": "source_display_candidate_id", "from": old_value, "to": None})
        if not str(expression.get("source_display_reason") or "").strip():
            expression["source_display_reason"] = (
                "Historical program did not select a source display; this replay preserves that decision."
                if expression["source_display_candidate_id"] is None
                else "Historical program explicitly selected this source display; this replay preserves that decision."
            )
            changes.append({"obligation_id": owner, "field": "source_display_reason", "to": expression["source_display_reason"]})
    # Validate the new schema, but do not project defaults into unchanged programs.
    SemanticCalculationProgram.model_validate(copied)
    return copied, changes


def _visibility(plan: Mapping[str, Any]) -> CandidateVisibilityV1:
    saved = dict(plan["candidate_visibility"])
    visibility = CandidateVisibilityV1.create(
        catalog_fingerprint=str(saved["catalog_fingerprint"]),
        visible_candidate_ids=saved["visible_candidate_ids"],
        candidate_ids_by_owner=saved["candidate_ids_by_owner"],
        evidence_bundle_constraints=saved.get("evidence_bundle_constraints") or [],
    )
    if visibility.cohort_fingerprint != saved["cohort_fingerprint"]:
        raise ValueError("saved owner visibility fingerprint does not round-trip")
    return visibility


def _first_attempt_visibility(plan: Mapping[str, Any]) -> CandidateVisibilityV1:
    """Restore recorded first-attempt authority, not newly ranked or invented IDs."""
    saved = _visibility(plan)
    initial_ids = list(dict.fromkeys(
        candidate_id
        for cohort in plan["candidate_cohorts"]
        if cohort["owner_id"] == "ob_001"
        for candidate_id in cohort["candidate_ids"]
    ))
    first_attempt = next(
        item for item in plan["program_validation_history"]
        if item["attempt"] == 1 and FIRST_DIRECT_ID in item.get("proposed_candidate_ids", [])
    )
    if set(initial_ids) != set(first_attempt["visible_candidate_ids"]):
        raise ValueError("initial owner cohort does not match saved first-attempt visibility")
    if not {FIRST_DIRECT_ID, FIRST_COMPATIBILITY_ID}.issubset(initial_ids):
        raise ValueError("reviewed first binding was not admitted in the saved first attempt")
    owners = saved.candidate_ids_by_owner()
    owners["ob_001"] = initial_ids
    visible = list(dict.fromkeys(candidate_id for ids in owners.values() for candidate_id in ids))
    return CandidateVisibilityV1.create(
        catalog_fingerprint=saved.catalog_fingerprint,
        visible_candidate_ids=visible,
        candidate_ids_by_owner=owners,
        evidence_bundle_constraints=saved.evidence_bundle_constraints,
    )


def _project_program_case(question_id: str, plan: Mapping[str, Any]) -> tuple[dict, CandidateVisibilityV1, str, list[dict]]:
    program, changes = _explicit_legacy_expression_decisions(plan["semantic_program"])
    visibility = _visibility(plan)
    mode = "saved_program_unchanged"
    if question_id == "HYU_T2_010":
        mode = "counterfactual_explicit_source_display"
        expression = next(item for item in program["expressions"] if item["obligation_id"] == "ob_001")
        if SOURCE_DISPLAY_ID not in visibility.candidate_ids_by_owner()["ob_001"]:
            raise ValueError("source display is outside saved owner visibility")
        assertion = next(
            item for item in program["source_assertions"]
            if "cand_7d5294a9fe110c3e987f" in item["candidate_ids"]
        )
        expression["source_display_candidate_id"] = SOURCE_DISPLAY_ID
        expression["source_display_reason"] = (
            "The exact source sentence explicitly reports the requested year-over-year growth as 11.5%; "
            "keep the formula calculation from the displayed period values separately."
        )
        assertion["candidate_ids"].append(SOURCE_DISPLAY_ID)
        changes.append({"obligation_id": "ob_001", "action": "select_previously_visible_source_display_and_cover_existing_exact_assertion", "candidate_id": SOURCE_DISPLAY_ID})
    elif question_id == "SAM_T2_078":
        mode = "counterfactual_restore_recorded_first_binding"
        visibility = _first_attempt_visibility(plan)
        program["direct_bindings"].insert(0, {
            "obligation_id": "ob_001", "candidate_id": FIRST_DIRECT_ID,
            "compatibility_candidate_ids": [FIRST_COMPATIBILITY_ID],
        })
        program["missing_obligation_ids"] = [item for item in program["missing_obligation_ids"] if item != "ob_001"]
        program["status"] = "ready"
        changes.append({"obligation_id": "ob_001", "action": "restore_recorded_first_attempt_binding_with_recorded_initial_owner_authority", "candidate_id": FIRST_DIRECT_ID, "compatibility_candidate_ids": [FIRST_COMPATIBILITY_ID]})
    elif question_id != "HYU_T3_072":
        raise ValueError(f"unsupported reviewed replay case: {question_id}")
    SemanticCalculationProgram.model_validate(program)
    return program, visibility, mode, changes


def _execute_copy(*, program: dict, visibility: CandidateVisibilityV1, catalog: Sequence[Mapping[str, Any]], obligations: Sequence[Mapping[str, Any]], query: str, plan: Mapping[str, Any]) -> dict:
    validation = validate_semantic_calculation_program(
        program=program, obligations=obligations, candidate_catalog=catalog,
        query=query, candidate_visibility=visibility,
    )
    envelope = CompilationEnvelopeV2.create(
        program=program, validation=validation, visibility=visibility,
        candidate_catalog=catalog, obligations=obligations, query=query,
    )
    execution = execute_semantic_calculation_program(
        program=program, obligations=obligations, candidate_catalog=catalog,
        query=query, compilation_envelope=envelope, require_compilation_envelope=True,
    )
    assembled = assemble_semantic_execution_result(
        execution=execution, obligations=obligations, calculation_plan={
            "answer_obligations": deepcopy(list(obligations)),
            "semantic_program": deepcopy(program),
            "candidate_catalog_fingerprint": plan["candidate_catalog_fingerprint"],
        }, query=query,
    )
    return {"validation": validation, "execution": execution, "assembled": assembled,
        "compilation_envelope": envelope.to_projection()}


def _case_checks(question_id: str, *, original: Mapping[str, Any], program: dict, execution: dict, assembled: dict, catalog: Sequence[Mapping[str, Any]]) -> dict[str, bool]:
    outputs = dict(execution.get("outputs_by_obligation") or {})
    checks = {
        "runtime_complete": execution.get("status") == "ok",
        "runtime_errors_zero": not execution.get("execution_errors"),
        "validation_ready": execution["validation"]["status"] == "ready",
        "narrative_program_bytes_preserved": _canonical_bytes(original.get("narrative_bindings") or []) == _canonical_bytes(program.get("narrative_bindings") or []),
    }
    if question_id == "HYU_T2_010":
        output = outputs.get("ob_001") or {}
        checks.update(
            source_display_is_11_5=output.get("source_display_candidate_id") == SOURCE_DISPLAY_ID and (output.get("answer_slot") or {}).get("normalized_value") == 11.5,
            formula_and_operands_preserved=program["expressions"][0]["formula"] == original["expressions"][0]["formula"] and program["expressions"][0]["variable_bindings"] == original["expressions"][0]["variable_bindings"],
            source_and_calculation_are_separate=output.get("normalized_value") != (output.get("answer_slot") or {}).get("normalized_value"),
            source_first_answer="11.5%" in assembled["answer"] and "재계산값" in assembled["answer"],
        )
    elif question_id == "HYU_T3_072":
        candidate_by_id = {item["candidate_id"]: item for item in catalog}
        rows = [candidate_by_id[binding["candidate_id"]] for binding in original["direct_bindings"]]
        checks.update(
            original_program_bytes_preserved=_canonical_bytes(original) == _canonical_bytes(program),
            numeric_outputs_share_original_physical_row=len({(row["physical_table_id"], row["physical_row_id"]) for row in rows}) == 1,
            original_numeric_candidate_ids_preserved=all(binding["candidate_id"] in outputs.get(binding["obligation_id"], {}).get("candidate_ids", []) for binding in original["direct_bindings"]),
        )
    else:
        output = outputs.get("ob_001") or {}
        checks.update(
            recorded_first_candidate_preserved=FIRST_DIRECT_ID in output.get("candidate_ids", []),
            normalized_krw_value_preserved=output.get("normalized_value") == 28_352_769_000_000.0,
            source_unit_preserved=(output.get("answer_slot") or {}).get("raw_unit") == "백만원",
        )
    return checks


def replay_reviewed_cases(results_path: Path) -> dict:
    rows = load_saved_plans([results_path], question_ids=set(CASE_IDS))
    by_id = {row["question_id"]: row for row in rows}
    if set(by_id) != set(CASE_IDS) or len(rows) != len(CASE_IDS):
        raise ValueError("replay requires exactly one saved plan for each of the three reviewed cases")
    inputs = {results_path.resolve()}
    for row in rows:
        store = Path(row["store"]["persist_directory"])
        inputs.update((store / "document_structure_graph.json", store / "table_payloads.json"))
    hashes = {path.as_posix(): _file_sha(path) for path in sorted(inputs)}
    cases = []
    for question_id in CASE_IDS:
        row = by_id[question_id]
        plan = row["plan"]
        original_program_sha = _sha(plan["semantic_program"])
        catalog, replay = replay_verified_candidate_catalog(plan, row["store"])
        if replay["status"] != "verified":
            cases.append({"question_id": question_id, "status": "blocked", "catalog_replay": replay})
            continue
        program, visibility, mode, changes = _project_program_case(question_id, plan)
        baseline_program, baseline_changes = _explicit_legacy_expression_decisions(plan["semantic_program"])
        baseline = _execute_copy(program=baseline_program, visibility=_visibility(plan), catalog=catalog,
            obligations=plan["answer_obligations"], query=row["question"], plan=plan)
        replayed = baseline if (
            program == baseline_program
            and visibility.cohort_fingerprint == _visibility(plan).cohort_fingerprint
        ) else _execute_copy(program=program, visibility=visibility, catalog=catalog,
            obligations=plan["answer_obligations"], query=row["question"], plan=plan)
        checks = _case_checks(question_id, original=plan["semantic_program"], program=program,
            execution=replayed["execution"], assembled=replayed["assembled"], catalog=catalog)
        checks["original_program_not_mutated"] = _sha(plan["semantic_program"]) == original_program_sha
        selected = set(replayed["execution"].get("selected_candidate_ids") or [])
        cases.append({"question_id": question_id, "status": "passed" if all(checks.values()) else "failed",
            "mode": mode, "catalog_replay": replay, "checks": checks, "copy_edits": changes,
            "saved_program_sha256": original_program_sha, "replay_program_sha256": _sha(program),
            "visibility_source": "recorded_first_attempt_owner_and_saved_other_owners" if question_id == "SAM_T2_078" else "saved_final_owner_visibility",
            "baseline_saved_program": {"copy_edits": baseline_changes,
                "validation_status": baseline["validation"]["status"], "validation_errors": baseline["validation"]["errors"],
                "runtime_status": baseline["execution"]["status"], "answer": baseline["assembled"]["answer"]},
            "selected_provenance": [{key: item.get(key) for key in ("candidate_id", "source_candidate_id", "source_row_id", "physical_table_id", "physical_row_id", "physical_cell_id", "raw_value", "raw_unit", "source_span", "source_bundle_value_span")} for item in catalog if item["candidate_id"] in selected],
            **replayed})
    unchanged = all(_file_sha(Path(path)) == digest for path, digest in hashes.items())
    return {"schema_version": "runtime_contract_reviewed_replay_v1",
        "provider_calls": 0, "compiler_calls": 0, "source_store_writes": 0,
        "claim_boundary": "Provider-free runtime contracts only. Counterfactual copied programs do not demonstrate compiler selection, evaluator acceptance, graph ledger, or release readiness.",
        "immutable_input_sha256": hashes, "immutable_inputs_unchanged": unchanged,
        "status": "passed" if unchanged and all(case["status"] == "passed" for case in cases) else "failed",
        "cases": cases}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="New successor receipt path; an existing file is never overwritten.")
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        parser.error("output already exists; use a new successor receipt path")
    result = replay_reviewed_cases(args.results)
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
        print(json.dumps({"status": result["status"], "output": args.output.as_posix(),
            "cases": [{"question_id": case["question_id"], "status": case["status"], "checks": case.get("checks"), "catalog_replay": case["catalog_replay"]} for case in result["cases"]]}, ensure_ascii=False, indent=2))
    else:
        print(serialized, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
